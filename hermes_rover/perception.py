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
from pathlib import Path

import httpx

_API_KEY = os.getenv("BYTEPLUS_API_KEY", "a3f914cf-838f-4bd3-91c7-135c33518f40")
_BASE_URL = os.getenv("BYTEPLUS_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")
_MODEL = "seedream-5-0-260128"

# Terrain types mapped to visual descriptions
_TERRAIN_PROMPTS = {
    "crater_rim": "Mars crater rim edge, rocky elevated terrain, steep drop ahead, red iron oxide rocks, NASA rover POV",
    "flat_plains": "Mars flat plains, smooth red terrain, distant mountains, rover tracks behind, NASA Perseverance POV",
    "rocky_field": "Mars rocky field, scattered boulders, uneven terrain, red dust, NASA rover camera perspective",
    "return_base": "Mars terrain with rover wheel tracks leading back, flat ground, lander visible in distance",
    "hazard": "Mars terrain with large boulder obstacle close ahead, rocky dangerous terrain, rover POV",
    "default": "Mars surface terrain, red rocky ground, thin atmosphere, NASA Perseverance rover perspective",
}


def _build_image_prompt(telemetry: dict, scene_context: str) -> str:
    heading = telemetry.get("heading_deg", 0)
    tilt = telemetry.get("tilt_deg", 0)
    lidar = telemetry.get("lidar_min_m", 10)
    dist = telemetry.get("distance_from_origin_m", 0)

    # Pick terrain type from context
    ctx = scene_context.lower()
    if "crater" in ctx:
        terrain = _TERRAIN_PROMPTS["crater_rim"]
    elif "return" in ctx or "base" in ctx:
        terrain = _TERRAIN_PROMPTS["return_base"]
    elif lidar < 3.0:
        terrain = _TERRAIN_PROMPTS["hazard"]
    elif "plain" in ctx or "flat" in ctx:
        terrain = _TERRAIN_PROMPTS["flat_plains"]
    else:
        terrain = _TERRAIN_PROMPTS["rocky_field"]

    # Add lighting based on sol position (use distance as proxy)
    lighting = "golden hour sol lighting, long shadows" if dist > 10 else "midday sol lighting, harsh shadows"

    return (
        f"{terrain}, {lighting}, "
        f"thin CO2 atmosphere haze, dust particles, "
        f"photorealistic, ultra detailed, 8K quality, "
        f"NASA Mars photography style, no text, no watermark"
    )


async def generate_terrain_image(telemetry: dict, scene_context: str, output_dir: Path | None = None) -> dict:
    """
    Generate a photorealistic Mars terrain image using Seedream 5.0.
    Returns: {success, file_path, b64_data, prompt_used}
    """
    prompt = _build_image_prompt(telemetry, scene_context)
    out_dir = output_dir or Path("~/rover_images").expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    import time
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
            # Try alternate size if first fails
            payload["size"] = "2048x2048"
            r = await client.post(
                f"{_BASE_URL}/images/generations",
                headers={"Authorization": f"Bearer {_API_KEY}", "Content-Type": "application/json"},
                json=payload,
            )

        if r.status_code != 200:
            return {"success": False, "error": r.text[:200], "prompt_used": prompt}

        data = r.json()
        # Extract b64 image
        b64 = None
        if "data" in data and data["data"]:
            item = data["data"][0]
            b64 = item.get("b64_json") or item.get("b64")
        if not b64:
            # Try url format
            url = data.get("data", [{}])[0].get("url")
            if url:
                img_r = await client.get(url)
                b64 = base64.b64encode(img_r.content).decode()

        if not b64:
            return {"success": False, "error": "No image data in response", "raw": str(data)[:300]}

        # Save to disk
        img_bytes = base64.b64decode(b64)
        output_path.write_bytes(img_bytes)

        return {
            "success": True,
            "file_path": str(output_path),
            "b64_data": b64,
            "prompt_used": prompt,
            "size_kb": len(img_bytes) // 1024,
        }
