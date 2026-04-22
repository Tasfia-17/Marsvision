"""
Mars Terrain Perception — AI-native camera replacement.
Uses Seedream 5.0 to generate photorealistic Mars terrain images
from rover telemetry (position, heading, terrain type, hazards).
This is the rover's "eyes" — no Gazebo needed.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from pathlib import Path

import httpx

_API_KEY = os.getenv("BYTEPLUS_API_KEY", "a3f914cf-838f-4bd3-91c7-135c33518f40")
_BASE_URL = os.getenv("BYTEPLUS_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")
_MODEL = "seedream-5-0-260128"

# Rich terrain base descriptions per type
_TERRAIN_BASES = {
    "crater_rim": (
        "Mars crater rim, jagged volcanic basalt edge, steep 30-meter drop into ancient impact basin, "
        "layered sedimentary rock strata visible on crater walls, iron oxide red and ochre tones, "
        "NASA Perseverance rover mastcam wide-angle perspective"
    ),
    "flat_plains": (
        "Mars Jezero Crater floor, ancient dried lakebed, smooth wind-polished regolith, "
        "faint rover wheel tracks stretching to horizon, distant Isidis Planitia rim mountains, "
        "scattered pebbles and ventifacts, NASA Perseverance rover navcam perspective"
    ),
    "rocky_field": (
        "Mars rocky terrain, dense field of angular basalt boulders 0.3 to 2 meters diameter, "
        "fine red iron oxide dust coating every surface, uneven treacherous ground, "
        "NASA Perseverance rover hazcam perspective, extreme detail"
    ),
    "return_base": (
        "Mars surface, clear rover wheel tracks pressed into regolith leading back toward lander, "
        "flat traversable ground, distant glint of rover lander hardware on horizon, "
        "NASA Perseverance rover navcam rear perspective"
    ),
    "hazard": (
        "Mars terrain, massive 1.5-meter basalt boulder directly in rover path 2 meters ahead, "
        "sharp jagged edges, rover must navigate around obstacle, "
        "NASA Perseverance rover hazcam front perspective, urgent close-up"
    ),
    "sand_dunes": (
        "Mars aeolian sand dunes, rippled fine dark basaltic sand, "
        "wind-sculpted barchan dune forms, soft traversable surface, "
        "NASA Perseverance rover mastcam perspective"
    ),
    "bedrock": (
        "Mars exposed bedrock outcrop, ancient Noachian-era layered mudstone, "
        "drill target candidate, fine laminated sedimentary layers, "
        "NASA Perseverance rover mastcam close-up scientific perspective"
    ),
    "default": (
        "Mars surface terrain, red iron oxide regolith, scattered basalt rocks, "
        "NASA Perseverance rover mastcam perspective"
    ),
}

# Sol lighting conditions
_SOL_LIGHTING = {
    "dawn": "pre-dawn blue-pink twilight, very long shadows stretching west, low 5-degree sun angle, cold blue atmosphere",
    "morning": "early morning golden sol light, long warm shadows, 20-degree sun elevation, crisp clear atmosphere",
    "midday": "harsh midday sol overhead, short stark shadows, bright 1000W/m2 illumination, bleached highlights",
    "afternoon": "warm afternoon sol light, 40-degree sun angle, medium-length shadows eastward, golden hour beginning",
    "dusk": "dramatic dusk, deep orange-red sky, sun touching horizon, extreme long shadows, dust scattering blue sunset",
}

# Mars weather/atmosphere states
_WEATHER = {
    "clear": "crystal clear thin CO2 atmosphere, 7mbar pressure, visibility 100km, faint blue sky at zenith",
    "dusty": "regional dust event, reduced visibility 20km, orange-brown haze, dust particles suspended in atmosphere",
    "storm": "global dust storm, visibility under 1km, thick orange-brown dust wall approaching, dramatic dark sky",
    "dust_devil": "clear atmosphere with active dust devil 500m to the east, swirling red dust column 50m tall",
    "frosty": "early morning CO2 frost on rocks and regolith, thin white crystalline coating, sublimating in sunlight",
}

# Camera lens characteristics
_CAMERAS = {
    "mastcam": "Mastcam-Z telephoto zoom lens, 110mm equivalent, shallow depth of field, sharp foreground rocks",
    "navcam": "Navigation camera wide-angle 120-degree FOV, fisheye distortion at edges, full terrain context",
    "hazcam_front": "Front hazard camera ultra-wide 180-degree fisheye, extreme barrel distortion, close obstacle detail",
    "hazcam_rear": "Rear hazard camera ultra-wide fisheye, wheel tracks visible, rear terrain context",
}


def _get_sol_time(dist: float, mission_time: float | None = None) -> str:
    """Estimate sol time from distance traveled (proxy for mission phase)."""
    t = mission_time or (time.time() % 88775)  # Mars sol = 88775 seconds
    fraction = t / 88775
    if fraction < 0.1:
        return "dawn"
    elif fraction < 0.3:
        return "morning"
    elif fraction < 0.6:
        return "midday"
    elif fraction < 0.85:
        return "afternoon"
    else:
        return "dusk"


def _build_image_prompt(telemetry: dict, scene_context: str, camera: str = "mastcam") -> str:
    heading = telemetry.get("heading_deg", 0)
    tilt = telemetry.get("tilt_deg", 0)
    lidar = telemetry.get("lidar_min_m", 10)
    dist = telemetry.get("distance_from_origin_m", 0)
    storm = telemetry.get("storm_active", False)

    # Terrain type selection
    ctx = scene_context.lower()
    if "crater" in ctx:
        terrain = _TERRAIN_BASES["crater_rim"]
    elif "return" in ctx or "base" in ctx or "lander" in ctx:
        terrain = _TERRAIN_BASES["return_base"]
    elif lidar < 2.0:
        terrain = _TERRAIN_BASES["hazard"]
    elif "sand" in ctx or "dune" in ctx:
        terrain = _TERRAIN_BASES["sand_dunes"]
    elif "bedrock" in ctx or "drill" in ctx or "sample" in ctx:
        terrain = _TERRAIN_BASES["bedrock"]
    elif "plain" in ctx or "flat" in ctx or "lake" in ctx:
        terrain = _TERRAIN_BASES["flat_plains"]
    elif "rock" in ctx or "boulder" in ctx:
        terrain = _TERRAIN_BASES["rocky_field"]
    else:
        terrain = _TERRAIN_BASES["default"]

    # Sol lighting
    sol_time = _get_sol_time(dist)
    lighting = _SOL_LIGHTING[sol_time]

    # Weather
    if storm:
        weather = _WEATHER["storm"]
    elif lidar < 3.0 and tilt > 15:
        weather = _WEATHER["dusty"]
    elif dist < 2 and sol_time == "morning":
        weather = _WEATHER["frosty"]
    else:
        weather = _WEATHER["clear"]

    # Camera
    cam_desc = _CAMERAS.get(camera, _CAMERAS["mastcam"])

    # Tilt note
    tilt_note = f"camera tilted {tilt:.1f} degrees, " if tilt > 5 else ""

    return (
        f"{terrain}, "
        f"{lighting}, "
        f"{weather}, "
        f"{tilt_note}"
        f"dust particles floating in atmosphere, "
        f"{cam_desc}, "
        f"photorealistic, ultra-detailed, 8K resolution, "
        f"NASA Mars photography style, RAW photo quality, "
        f"no text, no watermark, no UI elements"
    )


async def generate_terrain_image(
    telemetry: dict,
    scene_context: str,
    output_dir: Path | None = None,
    camera: str = "mastcam",
) -> dict:
    """
    Generate a photorealistic Mars terrain image using Seedream 5.0.
    Returns: {success, file_path, b64_data, prompt_used}
    """
    prompt = _build_image_prompt(telemetry, scene_context, camera)
    out_dir = output_dir or Path("~/rover_images").expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"terrain_{int(time.time())}.jpg"

    payload = {
        "model": _MODEL,
        "prompt": prompt,
        "size": "1920x1080",
        "response_format": "b64_json",
        "n": 1,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{_BASE_URL}/images/generations",
            headers={"Authorization": f"Bearer {_API_KEY}", "Content-Type": "application/json"},
            json=payload,
        )

        if r.status_code != 200:
            payload["size"] = "2048x2048"
            r = await client.post(
                f"{_BASE_URL}/images/generations",
                headers={"Authorization": f"Bearer {_API_KEY}", "Content-Type": "application/json"},
                json=payload,
            )

        if r.status_code != 200:
            return {"success": False, "error": r.text[:200], "prompt_used": prompt}

        data = r.json()
        b64 = None
        if "data" in data and data["data"]:
            item = data["data"][0]
            b64 = item.get("b64_json") or item.get("b64")
        if not b64:
            url = data.get("data", [{}])[0].get("url")
            if url:
                img_r = await client.get(url)
                b64 = base64.b64encode(img_r.content).decode()

        if not b64:
            return {"success": False, "error": "No image data in response", "raw": str(data)[:300]}

        img_bytes = base64.b64decode(b64)
        output_path.write_bytes(img_bytes)

        return {
            "success": True,
            "file_path": str(output_path),
            "b64_data": b64,
            "prompt_used": prompt,
            "sol_time": _get_sol_time(telemetry.get("distance_from_origin_m", 0)),
            "size_kb": len(img_bytes) // 1024,
        }


async def generate_terrain_gallery(
    telemetry: dict,
    scene_context: str,
    count: int = 4,
    output_dir: Path | None = None,
) -> list[dict]:
    """Generate multiple terrain images in parallel for a mission gallery."""
    cameras = ["mastcam", "navcam", "hazcam_front", "mastcam"]
    contexts = [
        scene_context,
        scene_context + " wide survey",
        scene_context + " obstacle check",
        scene_context + " scientific target",
    ]
    tasks = [
        generate_terrain_image(telemetry, contexts[i % len(contexts)], output_dir, cameras[i % len(cameras)])
        for i in range(count)
    ]
    return await asyncio.gather(*tasks)
# Seedream 5.0 terrain perception — enhanced prompts
