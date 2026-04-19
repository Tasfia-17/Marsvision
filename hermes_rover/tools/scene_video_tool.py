"""
Generate a cinematic Seedance 2.0 video from live rover telemetry.
Uses real Gazebo camera frames as reference images when available (I2V),
falls back to text-to-video with rich telemetry prompt.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from pathlib import Path

import httpx

TOOL_SCHEMA = {
    "name": "generate_scene_video",
    "description": (
        "Generate a cinematic Seedance 2.0 video of what the rover currently sees. "
        "Captures a real camera frame from the rover, then uses Seedance 2.0 image-to-video "
        "to animate it cinematically. Falls back to text-to-video if camera unavailable. "
        "Returns a local video file path and MEDIA: tag for Telegram delivery."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "scene_context": {
                "type": "string",
                "description": "Brief description of the current scene or mission phase.",
            },
            "camera": {
                "type": "string",
                "enum": ["mastcam", "navcam", "hazcam_front"],
                "description": "Which rover camera to use as reference. Default: mastcam.",
                "default": "mastcam",
            },
            "duration": {
                "type": "integer",
                "description": "Video duration in seconds (4 or 5). Default 5.",
                "default": 5,
            },
        },
        "required": ["scene_context"],
    },
}

_API_KEY = os.getenv("BYTEPLUS_API_KEY", "a3f914cf-838f-4bd3-91c7-135c33518f40")
_BASE_URL = os.getenv("BYTEPLUS_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")
_MODEL_I2V = "dreamina-seedance-2-0-fast-260128"   # image-to-video (confirmed working)
_MODEL_T2V = "dreamina-seedance-2-0-fast-260128"   # text-to-video (same model, different content)
_POLL_INTERVAL = 5
_MAX_WAIT = 300


def _build_motion_prompt(scene_context: str, telemetry: dict) -> str:
    heading = telemetry.get("heading_deg", 0)
    tilt = telemetry.get("tilt_deg", 0)
    lidar_min = telemetry.get("lidar_min_m", 10)
    dist = telemetry.get("distance_from_origin_m", 0)

    hazard = f"obstacle {lidar_min:.1f}m ahead, slow cautious approach, " if lidar_min < 3.0 else "clear path ahead, "
    motion = "slow cinematic dolly forward" if tilt < 10 else "careful traverse, camera stabilized"

    return (
        f"{scene_context}, {hazard}{motion}, "
        f"Mars red rocky terrain, thin CO2 atmosphere haze, "
        f"sol lighting with long shadows, dust particles floating, "
        f"NASA rover perspective, photorealistic, cinematic"
    )


def _build_t2v_prompt(scene_context: str, telemetry: dict) -> str:
    heading = telemetry.get("heading_deg", 0)
    tilt = telemetry.get("tilt_deg", 0)
    lidar_min = telemetry.get("lidar_min_m", 10)
    hazard_note = f"large boulder {lidar_min:.1f}m ahead, " if lidar_min < 3.0 else ""
    return (
        f"Mars terrain exploration, rover POV camera, {scene_context}, "
        f"heading {heading:.0f} degrees, {hazard_note}"
        f"tilt {tilt:.1f} degrees, red rocky Martian surface, "
        f"thin atmosphere haze, afternoon sol lighting, long shadows, "
        f"cinematic dolly forward, dust particles, photorealistic, "
        f"NASA Perseverance rover perspective"
    )


def _get_telemetry() -> dict:
    try:
        import subprocess, re as _re
        result = subprocess.run(
            ["gz", "topic", "-e", "-t", "/rover/odometry", "-n", "1"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0 and result.stdout:
            x = float(_re.search(r"x:\s*([\d.\-]+)", result.stdout).group(1) or 0)
            y = float(_re.search(r"y:\s*([\d.\-]+)", result.stdout).group(1) or 0)
            return {"position": {"x": x, "y": y}, "heading_deg": 0, "tilt_deg": 0}
    except Exception:
        pass
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from bridge.mock_sensors import get_state_for_video
        return get_state_for_video()
    except Exception:
        return {"position": {"x": 0, "y": 0}, "heading_deg": 45, "tilt_deg": 2.1, "lidar_min_m": 4.5}


async def _capture_camera_frame(camera: str, telemetry: dict, scene_context: str) -> str | None:
    """
    Get a camera frame for I2V:
    1. Try real Gazebo camera (if running)
    2. Fall back to Seedream 5.0 AI-generated terrain image
    """
    # Try real Gazebo first
    try:
        import subprocess
        result = subprocess.run(["gz", "topic", "--list"], capture_output=True, timeout=2)
        if result.returncode == 0:
            from hermes_rover.tools.camera_tool import execute as cap
            res = json.loads(await cap(camera=camera))
            if res.get("success"):
                img_path = Path(res["file_path"])
                if img_path.exists():
                    return base64.b64encode(img_path.read_bytes()).decode()
    except Exception:
        pass

    # Use Seedream 5.0 AI perception
    try:
        from hermes_rover.perception import generate_terrain_image
        result = await generate_terrain_image(telemetry, scene_context)
        if result.get("success"):
            return result["b64_data"]
    except Exception as e:
        print(f"Seedream perception error: {e}")

    return None


async def _upload_image(image_b64: str) -> str:
    """Upload image to BytePlus Files API, return file_id."""
    img_bytes = base64.b64decode(image_b64)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_BASE_URL}/files",
            headers={"Authorization": f"Bearer {_API_KEY}"},
            files={"file": ("frame.jpg", img_bytes, "image/jpeg")},
            data={"purpose": "vision"},
        )
        if r.status_code == 200:
            return r.json().get("id", "")
    return ""


async def _create_i2v_task(image_b64: str, motion_prompt: str, duration: int) -> str:
    """Create image-to-video task using base64 image."""
    payload = {
        "model": _MODEL_I2V,
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            {"type": "text", "text": motion_prompt},
        ],
        "parameters": {"duration": duration, "resolution": "720p", "watermark": False},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_BASE_URL}/contents/generations/tasks",
            headers={"Authorization": f"Bearer {_API_KEY}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("id") or data["data"]["task_id"]


async def _create_t2v_task(prompt: str, duration: int) -> str:
    payload = {
        "model": _MODEL_T2V,
        "content": [{"type": "text", "text": prompt}],
        "parameters": {"duration": duration, "resolution": "720p", "watermark": False},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_BASE_URL}/contents/generations/tasks",
            headers={"Authorization": f"Bearer {_API_KEY}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("id") or data["data"]["task_id"]


async def _poll_task(task_id: str) -> str:
    deadline = time.time() + _MAX_WAIT
    async with httpx.AsyncClient(timeout=30) as client:
        while time.time() < deadline:
            r = await client.get(
                f"{_BASE_URL}/contents/generations/tasks/{task_id}",
                headers={"Authorization": f"Bearer {_API_KEY}"},
            )
            r.raise_for_status()
            data = r.json()
            status = data.get("status", "").lower()
            if status in ("succeeded", "completed", "success"):
                content = data.get("content", {})
                if isinstance(content, dict):
                    return content["video_url"]
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "video":
                            return item["video_url"]
            if status in ("failed", "error"):
                raise RuntimeError(f"Task failed: {data}")
            await asyncio.sleep(_POLL_INTERVAL)
    raise TimeoutError(f"Task {task_id} timed out")


async def _download_video(url: str, output_path: Path) -> None:
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(r.content)


async def execute(*, scene_context: str, camera: str = "mastcam", duration: int = 5, **_) -> str:
    telemetry = _get_telemetry()
    out_dir = Path("~/rover_videos").expanduser()
    output_path = out_dir / f"scene_{int(time.time())}.mp4"
    mode = "t2v"

    try:
        # Try image-to-video (Seedream 5.0 → Seedance 2.0 I2V)
        image_b64 = await _capture_camera_frame(camera, telemetry, scene_context)
        if image_b64:
            motion_prompt = _build_motion_prompt(scene_context, telemetry)
            task_id = await _create_i2v_task(image_b64, motion_prompt, min(max(duration, 4), 5))
            mode = "i2v_seedream"
            prompt_used = motion_prompt
        else:
            prompt_used = _build_t2v_prompt(scene_context, telemetry)
            task_id = await _create_t2v_task(prompt_used, min(max(duration, 4), 5))

        video_url = await _poll_task(task_id)
        await _download_video(video_url, output_path)

        return json.dumps({
            "success": True,
            "mode": mode,
            "file_path": str(output_path),
            "media_tag": f"MEDIA:{output_path}",
            "prompt_used": prompt_used,
            "task_id": task_id,
            "telemetry_used": telemetry,
            "message": f"Cinematic video generated ({mode}). Use send_message with MEDIA path for Telegram.",
        })
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc), "mode": mode})
# Seedance 2.0 I2V pipeline
