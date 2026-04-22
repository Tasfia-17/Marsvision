"""
MarsVision FastAPI backend.
Handles mission commands, telemetry, and video generation.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bridge.mock_sensors import get_snapshot, drive, navigate_to, get_state_for_video
from hermes_rover.tools.scene_video_tool import execute as generate_video, generate_mission_gallery_videos
from hermes_rover.perception import generate_terrain_image, generate_terrain_gallery
from hermes_rover.autonomous_agent import run_mission, get_trace
from hermes_rover.memory import memory_manager as mm

app = FastAPI(title="MarsVision API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── In-memory mission log ──────────────────────────────────────────────────
_mission_log: list[dict] = []
_current_mission: str | None = None


def _log(event: str, data: dict = {}):
    entry = {"timestamp": time.time(), "event": event, **data}
    _mission_log.append(entry)
    print(f"[{event}] {data}")


# ── Models ─────────────────────────────────────────────────────────────────
class MissionCommand(BaseModel):
    goal: str

class DriveCommand(BaseModel):
    linear_ms: float = 0.5
    angular_rads: float = 0.0
    duration_s: float = 2.0

class NavigateCommand(BaseModel):
    x: float
    y: float

class VideoCommand(BaseModel):
    scene_context: str
    duration: int = 5

class GalleryCommand(BaseModel):
    scene_context: str
    image_count: int = 4
    video_count: int = 2


# ── Routes ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "time": time.time()}


# Alias for original dashboard compatibility
@app.get("/status")
def status():
    snap = get_snapshot()
    state = get_state_for_video()
    return {
        "position": {"x": state["position"]["x"], "y": state["position"]["y"], "z": 0},
        "orientation": {
            "roll": snap["imu"].get("roll_deg", 0) * 3.14159 / 180,
            "pitch": snap["imu"]["pitch_deg"] * 3.14159 / 180,
            "yaw": snap["imu"]["yaw_deg"] * 3.14159 / 180,
        },
        "velocity": {"linear": snap["odometry"]["speed_ms"], "angular": 0},
        "hazard_detected": snap["lidar"]["min_distance_m"] < 1.5,
        "uptime_seconds": snap["mission_elapsed_s"],
        "sim_connected": True,
        # MarsVision extras
        "imu": snap["imu"],
        "odometry": snap["odometry"],
        "lidar": snap["lidar"],
        "battery_pct": snap["battery_pct"],
        "sol": snap["sol"],
        "mission_elapsed_s": snap["mission_elapsed_s"],
    }


@app.get("/hazards")
def get_hazards():
    try:
        hazards = mm.get_nearby_hazards(0, 0, radius=100)
        return {"hazards": hazards}
    except Exception:
        return {"hazards": []}


@app.get("/sessions")
def get_sessions():
    try:
        sessions = mm.get_sessions(limit=20)
        return {"sessions": sessions}
    except Exception:
        return {"sessions": []}


@app.post("/command")
async def command(cmd: MissionCommand):
    def on_event(phase, detail, data):
        _mission_log.append({"timestamp": time.time(), "event": phase, "detail": detail, **data})
    asyncio.create_task(run_mission(cmd.goal, on_event=on_event))
    return {"response": f"Mission started: {cmd.goal}", "status": "ok"}


# WebSocket for live telemetry
_ws_clients: list[WebSocket] = []

@app.websocket("/ws/telemetry")
async def ws_telemetry(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    try:
        while True:
            snap = get_snapshot()
            state = get_state_for_video()
            payload = {
                "position": {"x": state["position"]["x"], "y": state["position"]["y"], "z": 0},
                "orientation": {
                    "roll": snap["imu"].get("roll_deg", 0) * 3.14159 / 180,
                    "pitch": snap["imu"]["pitch_deg"] * 3.14159 / 180,
                    "yaw": snap["imu"]["yaw_deg"] * 3.14159 / 180,
                },
                "velocity": {"linear": snap["odometry"]["speed_ms"], "angular": 0},
                "hazard_detected": snap["lidar"]["min_distance_m"] < 1.5,
                "uptime_seconds": snap["mission_elapsed_s"],
                "sim_connected": True,
                "imu": snap["imu"],
                "odometry": snap["odometry"],
                "lidar": snap["lidar"],
                "battery_pct": snap["battery_pct"],
                "sol": snap["sol"],
            }
            await ws.send_text(json.dumps(payload))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        _ws_clients.remove(ws)


@app.get("/telemetry")
def telemetry():
    return get_snapshot()


@app.get("/telemetry/video-state")
def telemetry_video_state():
    return get_state_for_video()


@app.post("/drive")
def drive_rover(cmd: DriveCommand):
    result = drive(cmd.linear_ms, cmd.angular_rads, cmd.duration_s)
    _log("drive", result)
    return result


@app.post("/navigate")
def navigate(cmd: NavigateCommand):
    result = navigate_to(cmd.x, cmd.y)
    _log("navigate", result)
    return result


@app.post("/video/generate")
async def generate_scene_video(cmd: VideoCommand):
    _log("video_start", {"scene": cmd.scene_context})
    result_json = await generate_video(scene_context=cmd.scene_context, duration=cmd.duration)
    result = json.loads(result_json)
    _log("video_done", {"success": result.get("success"), "file": result.get("file_path")})
    return result


@app.get("/terrain/latest")
def get_latest_terrain():
    img_dir = Path("~/rover_images").expanduser()
    if not img_dir.exists():
        raise HTTPException(404, "No terrain images yet")
    images = sorted(img_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not images:
        raise HTTPException(404, "No terrain images yet")
    return FileResponse(images[0], media_type="image/jpeg")


@app.get("/terrain/gallery")
def get_terrain_gallery(limit: int = 12):
    """Return metadata for the latest N terrain images."""
    img_dir = Path("~/rover_images").expanduser()
    if not img_dir.exists():
        return {"images": []}
    images = sorted(img_dir.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    return {
        "images": [
            {"file": p.name, "path": str(p), "size_kb": p.stat().st_size // 1024, "ts": p.stat().st_mtime}
            for p in images
        ]
    }


@app.get("/terrain/gallery/{filename}")
def get_terrain_image(filename: str):
    img_path = Path("~/rover_images").expanduser() / filename
    if not img_path.exists():
        raise HTTPException(404, "Image not found")
    return FileResponse(img_path, media_type="image/jpeg")


@app.post("/terrain/generate")
async def generate_terrain(cmd: VideoCommand):
    """Generate a single high-quality terrain image via Seedream 5.0."""
    telemetry = get_state_for_video()
    result = await generate_terrain_image(telemetry, cmd.scene_context)
    return result


@app.post("/gallery/generate")
async def generate_gallery(cmd: GalleryCommand):
    """Generate a full mission gallery: multiple images + videos in parallel."""
    telemetry = get_state_for_video()

    # Build varied scene contexts for richer gallery
    image_contexts = [
        cmd.scene_context,
        cmd.scene_context + " wide panoramic survey",
        cmd.scene_context + " close-up scientific target",
        cmd.scene_context + " hazard assessment",
    ][:cmd.image_count]

    video_contexts = [
        cmd.scene_context,
        cmd.scene_context + " cinematic exploration",
    ][:cmd.video_count]

    images_task = generate_terrain_gallery(telemetry, cmd.scene_context, count=cmd.image_count)
    videos_task = generate_mission_gallery_videos(video_contexts, telemetry)

    images, videos = await asyncio.gather(images_task, videos_task)

    return {
        "images": images,
        "videos": videos,
        "total_generated": len(images) + len(videos),
    }


@app.get("/video/gallery")
def get_video_gallery(limit: int = 8):
    """Return metadata for the latest N generated videos."""
    video_dir = Path("~/rover_videos").expanduser()
    if not video_dir.exists():
        return {"videos": []}
    videos = sorted(video_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    return {
        "videos": [
            {"file": p.name, "path": str(p), "size_kb": p.stat().st_size // 1024, "ts": p.stat().st_mtime}
            for p in videos
        ]
    }


@app.get("/video/gallery/{filename}")
def get_video_file(filename: str):
    video_path = Path("~/rover_videos").expanduser() / filename
    if not video_path.exists():
        raise HTTPException(404, "Video not found")
    return FileResponse(video_path, media_type="video/mp4")


@app.get("/video/latest")
def get_latest_video():
    video_dir = Path("~/rover_videos").expanduser()
    if not video_dir.exists():
        raise HTTPException(404, "No videos yet")
    videos = sorted(video_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not videos:
        raise HTTPException(404, "No videos yet")
    return FileResponse(videos[0], media_type="video/mp4")


@app.post("/mission/start")
async def start_mission(cmd: MissionCommand):
    global _current_mission
    _current_mission = cmd.goal
    _log("mission_start", {"goal": cmd.goal})

    def on_event(phase, detail, data):
        _mission_log.append({"timestamp": time.time(), "event": phase, "detail": detail, **data})

    asyncio.create_task(run_mission(cmd.goal, on_event=on_event))
    return {"status": "started", "goal": cmd.goal}


@app.get("/mission/trace")
def mission_trace():
    return {"trace": get_trace()}


@app.get("/mission/log")
def mission_log():
    return {"log": _mission_log[-50:], "current_mission": _current_mission}


@app.get("/mission/log/stream")
async def mission_log_stream():
    """Server-sent events for live dashboard updates."""
    from fastapi.responses import StreamingResponse

    async def event_stream():
        last_idx = 0
        while True:
            if len(_mission_log) > last_idx:
                for entry in _mission_log[last_idx:]:
                    yield f"data: {json.dumps(entry)}\n\n"
                last_idx = len(_mission_log)
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
# FastAPI backend
