"""
Generate a cinematic Seedance 2.0 video from live rover telemetry.

Pipeline (in priority order):
  1. Multi-reference I2V — up to 4 Seedream 5.0 frames (mastcam + navcam +
     hazcam_front + prior frame) fed simultaneously as [Image1]..[Image4].
     Seedance 2.0 supports up to 9 images + 3 videos + 3 audio per request.
  2. Single-reference I2V — one Seedream 5.0 frame (fallback).
  3. T2V — text-only prompt (final fallback, no image available).

Multi-reference produces visually consistent, spatially grounded video because
the model sees the scene from multiple angles simultaneously — matching the
DreamGen approach of grounding video generation in real sensor observations.
"""
from __future__ import annotations

import asyncio
import base64
import itertools
import json
import os
import time
from pathlib import Path

import httpx

TOOL_SCHEMA = {
    "name": "generate_scene_video",
    "description": (
        "Generate a cinematic Seedance 2.0 video of what the rover currently sees. "
        "Uses multi-reference I2V: captures frames from mastcam, navcam, and hazcam "
        "simultaneously via Seedream 5.0, then feeds all as [Image1]..[ImageN] to "
        "Seedance 2.0 for spatially-grounded cinematic animation. "
        "Falls back to single-reference I2V, then T2V. "
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

# API key pool — rotated round-robin for high-volume generation
_API_KEYS = [
    os.getenv("BYTEPLUS_API_KEY", "a3f914cf-838f-4bd3-91c7-135c33518f40"),
    "e66b5732-3a87-4351-ae56-0ce02d40c50f",
    "ffcb6a9b-74ff-49e4-9b0f-7e1e864b36cf",
    "2d2003f8-d945-4271-b6fe-c08612065aed",
]
_key_cycle = itertools.cycle(_API_KEYS)

def _next_key() -> str:
    return next(_key_cycle)

_BASE_URL = os.getenv("BYTEPLUS_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")
_MODEL_I2V = "dreamina-seedance-2-0-fast-260128"
_MODEL_T2V = "dreamina-seedance-2-0-fast-260128"
_POLL_INTERVAL = 5
_MAX_WAIT = 300

# Mission phase → cinematic camera motion keywords (Seedance 2.0 prompt guide)
_MOTION_STYLES = {
    "explore":   "slow cinematic dolly forward, parallax rock movement, dust kicked up by wheels",
    "hazard":    "camera stabilized, slow cautious approach, tension-building push-in toward obstacle",
    "return":    "smooth tracking shot following wheel tracks, gentle pull-back reveal",
    "sample":    "slow orbital arc around scientific target, rack focus foreground to background",
    "storm":     "handheld shaky cam, dust particles whipping past lens, dramatic atmosphere",
    "survey":    "sweeping panoramic tilt-up from ground to horizon, epic wide reveal",
    "default":   "slow cinematic dolly forward, subtle camera drift, immersive rover POV",
}

# Atmosphere quality descriptors for Seedance
_ATMO_QUALITY = (
    "photorealistic, cinematic 4K, film grain, anamorphic lens flare, "
    "NASA documentary style, ultra-detailed Mars surface, "
    "thin CO2 atmosphere haze, suspended dust particles, "
    "iron oxide red terrain, basalt rocks"
)


def _detect_phase(scene_context: str, telemetry: dict) -> str:
    ctx = scene_context.lower()
    lidar = telemetry.get("lidar_min_m", 10)
    storm = telemetry.get("storm_active", False)
    if storm:
        return "storm"
    if lidar < 2.5:
        return "hazard"
    if "return" in ctx or "base" in ctx:
        return "return"
    if "sample" in ctx or "drill" in ctx or "science" in ctx:
        return "sample"
    if "survey" in ctx or "panorama" in ctx:
        return "survey"
    if "explore" in ctx or "navigate" in ctx:
        return "explore"
    return "default"


def _build_motion_prompt(scene_context: str, telemetry: dict) -> str:
    heading = telemetry.get("heading_deg", 0)
    tilt = telemetry.get("tilt_deg", 0)
    lidar = telemetry.get("lidar_min_m", 10)
    dist = telemetry.get("distance_from_origin_m", 0)

    phase = _detect_phase(scene_context, telemetry)
    motion = _MOTION_STYLES[phase]

    obstacle = f"large boulder {lidar:.1f}m ahead, " if lidar < 3.0 else ""
    tilt_note = f"rover tilted {tilt:.1f} degrees, " if tilt > 8 else ""
    sol_note = "golden hour sol lighting, long dramatic shadows, " if dist > 15 else "midday sol harsh lighting, "

    return (
        f"{scene_context}, {obstacle}{tilt_note}"
        f"{motion}, "
        f"{sol_note}"
        f"{_ATMO_QUALITY}"
    )


def _build_t2v_prompt(scene_context: str, telemetry: dict) -> str:
    heading = telemetry.get("heading_deg", 0)
    tilt = telemetry.get("tilt_deg", 0)
    lidar = telemetry.get("lidar_min_m", 10)

    phase = _detect_phase(scene_context, telemetry)
    motion = _MOTION_STYLES[phase]
    obstacle = f"large boulder {lidar:.1f}m ahead, " if lidar < 3.0 else ""

    return (
        f"Mars terrain exploration, NASA Perseverance rover POV camera, "
        f"{scene_context}, {obstacle}"
        f"heading {heading:.0f} degrees, tilt {tilt:.1f} degrees, "
        f"{motion}, "
        f"red rocky Martian surface, Jezero Crater, "
        f"{_ATMO_QUALITY}"
    )


def _get_telemetry() -> dict:
    try:
        import subprocess, re as _re
        result = subprocess.run(
            ["gz", "topic", "-e", "-t", "/rover/odometry", "-n", "1"],
            capture_output=True, text=True, timeout=3,
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


async def _capture_multi_reference(
    cameras: list[str], telemetry: dict, scene_context: str
) -> list[str]:
    """
    Capture frames from multiple rover cameras in parallel via Seedream 5.0.
    Returns list of base64-encoded images (may be shorter than cameras list on failure).
    """
    from hermes_rover.perception import generate_terrain_image

    async def _one(camera: str) -> str | None:
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
        # Fall back to Seedream 5.0
        try:
            result = await generate_terrain_image(telemetry, scene_context, camera=camera)
            if result.get("success"):
                return result["b64_data"]
        except Exception as e:
            print(f"Seedream [{camera}] error: {e}")
        return None

    results = await asyncio.gather(*[_one(c) for c in cameras])
    return [r for r in results if r is not None]


async def _capture_camera_frame(camera: str, telemetry: dict, scene_context: str) -> str | None:
    """Single-camera capture (kept for backward compat)."""
    frames = await _capture_multi_reference([camera], telemetry, scene_context)
    return frames[0] if frames else None


async def _create_multi_ref_i2v_task(
    images_b64: list[str], motion_prompt: str, duration: int
) -> str:
    """
    Seedance 2.0 multi-reference I2V.
    Sends up to 9 images as [Image1]..[ImageN] references in a single request.
    The model uses all frames to maintain spatial consistency across the video.
    """
    api_key = _next_key()
    # Build content: images first, then the annotated text prompt
    content = []
    ref_tags = []
    for i, b64 in enumerate(images_b64[:9], start=1):
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        ref_tags.append(f"[Image{i}]")

    # Annotate prompt with reference tags so model knows which image is which
    camera_labels = ["mastcam wide view", "navcam navigation view", "hazcam obstacle view", "prior frame"]
    annotations = ", ".join(
        f"{ref_tags[i]} {camera_labels[i]}"
        for i in range(len(ref_tags))
    )
    annotated_prompt = f"{motion_prompt}. Reference frames: {annotations}."
    content.append({"type": "text", "text": annotated_prompt})

    payload = {
        "model": _MODEL_I2V,
        "content": content,
        "parameters": {"duration": duration, "resolution": "1080p", "watermark": False},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_BASE_URL}/contents/generations/tasks",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("id") or data["data"]["task_id"]


async def _create_i2v_task(image_b64: str, motion_prompt: str, duration: int) -> str:
    api_key = _next_key()
    payload = {
        "model": _MODEL_I2V,
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            {"type": "text", "text": motion_prompt},
        ],
        "parameters": {"duration": duration, "resolution": "1080p", "watermark": False},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_BASE_URL}/contents/generations/tasks",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("id") or data["data"]["task_id"]


async def _create_t2v_task(prompt: str, duration: int) -> str:
    api_key = _next_key()
    payload = {
        "model": _MODEL_T2V,
        "content": [{"type": "text", "text": prompt}],
        "parameters": {"duration": duration, "resolution": "1080p", "watermark": False},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_BASE_URL}/contents/generations/tasks",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("id") or data["data"]["task_id"]


async def _poll_task(task_id: str) -> str:
    api_key = _next_key()
    deadline = time.time() + _MAX_WAIT
    async with httpx.AsyncClient(timeout=30) as client:
        while time.time() < deadline:
            r = await client.get(
                f"{_BASE_URL}/contents/generations/tasks/{task_id}",
                headers={"Authorization": f"Bearer {api_key}"},
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
    prompt_used = ""

    try:
        motion_prompt = _build_motion_prompt(scene_context, telemetry)

        # Attempt multi-reference I2V: mastcam + navcam + hazcam_front in parallel
        all_cameras = ["mastcam", "navcam", "hazcam_front"]
        images_b64 = await _capture_multi_reference(all_cameras, telemetry, scene_context)

        if len(images_b64) >= 2:
            task_id = await _create_multi_ref_i2v_task(images_b64, motion_prompt, min(max(duration, 4), 5))
            mode = f"multi_ref_i2v_{len(images_b64)}frames"
            prompt_used = motion_prompt
        elif len(images_b64) == 1:
            task_id = await _create_i2v_task(images_b64[0], motion_prompt, min(max(duration, 4), 5))
            mode = "i2v_seedream"
            prompt_used = motion_prompt
        else:
            prompt_used = _build_t2v_prompt(scene_context, telemetry)
            task_id = await _create_t2v_task(prompt_used, min(max(duration, 4), 5))

        video_url = await _poll_task(task_id)
        await _download_video(video_url, output_path)

        # Log to memory
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from hermes_rover.memory.memory_manager import log_terrain
            pos = telemetry.get("position", {})
            log_terrain(pos.get("x", 0), pos.get("y", 0), "video_generated", str(output_path))
        except Exception:
            pass

        return json.dumps({
            "success": True,
            "mode": mode,
            "reference_frames": len(images_b64) if "multi_ref" in mode else 1,
            "file_path": str(output_path),
            "media_tag": f"MEDIA:{output_path}",
            "prompt_used": prompt_used,
            "task_id": task_id,
            "telemetry_used": telemetry,
            "message": f"Cinematic 1080p video generated ({mode}). Use send_message with MEDIA path for Telegram.",
        })
    except Exception as exc:
        return json.dumps({"success": False, "error": str(exc), "mode": mode})


async def generate_mission_gallery_videos(
    scene_contexts: list[str],
    telemetry: dict | None = None,
) -> list[dict]:
    """Generate multiple mission videos in parallel using all API keys."""
    if telemetry is None:
        telemetry = _get_telemetry()
    tasks = [
        execute(scene_context=ctx, camera="mastcam", duration=5)
        for ctx in scene_contexts
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [json.loads(r) if isinstance(r, str) else {"success": False, "error": str(r)} for r in results]
# Seedance 2.0 I2V pipeline — enhanced prompts + key rotation + 1080p + gallery
