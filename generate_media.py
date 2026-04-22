"""
Batch generate high-quality Mars terrain images (Seedream 5.0)
and cinematic videos (Seedance 2.0) for MarsVision demo.
Saves to docs/generated_media/ and commits to repo.
"""
import asyncio
import base64
import itertools
import json
import time
from pathlib import Path
import httpx

BASE_URL = "https://ark.ap-southeast.bytepluses.com/api/v3"
API_KEYS = [
    "e66b5732-3a87-4351-ae56-0ce02d40c50f",
    "ffcb6a9b-74ff-49e4-9b0f-7e1e864b36cf",
    "2d2003f8-d945-4271-b6fe-c08612065aed",
    "a3f914cf-838f-4bd3-91c7-135c33518f40",
]
_keys = itertools.cycle(API_KEYS)
def key(): return next(_keys)

OUT_IMAGES = Path("docs/generated_media/images")
OUT_VIDEOS = Path("docs/generated_media/videos")
OUT_IMAGES.mkdir(parents=True, exist_ok=True)
OUT_VIDEOS.mkdir(parents=True, exist_ok=True)

IMAGE_PROMPTS = [
    (
        "jezero_crater_dawn",
        "Mars Jezero Crater floor at dawn, ancient dried lakebed, smooth wind-polished red regolith, "
        "NASA Perseverance rover wheel tracks stretching to horizon, distant crater rim mountains, "
        "pre-dawn blue-pink twilight sky, very long shadows, thin CO2 atmosphere, "
        "photorealistic, ultra-detailed, 8K, NASA Mars photography style, no watermark"
    ),
    (
        "rocky_field_midday",
        "Mars rocky terrain, dense field of angular basalt boulders 0.3 to 2 meters diameter, "
        "fine red iron oxide dust coating every surface, harsh midday sol overhead lighting, "
        "short stark shadows, NASA Perseverance rover hazcam perspective, "
        "photorealistic, ultra-detailed, 8K, RAW photo quality, no watermark"
    ),
    (
        "crater_rim_golden_hour",
        "Mars crater rim edge, jagged volcanic basalt, steep 30-meter drop into ancient impact basin, "
        "layered sedimentary rock strata on crater walls, golden hour sol lighting, "
        "long dramatic shadows, thin CO2 atmosphere haze, dust particles floating, "
        "NASA Perseverance rover mastcam telephoto, photorealistic, 8K, no watermark"
    ),
    (
        "dust_storm_approaching",
        "Mars surface, massive global dust storm wall approaching from horizon, "
        "thick orange-brown dust cloud 2km high, visibility dropping, "
        "rover wheel tracks in foreground regolith, dramatic dark sky, "
        "photorealistic, cinematic, ultra-detailed, 8K, NASA documentary style, no watermark"
    ),
    (
        "bedrock_scientific_target",
        "Mars exposed bedrock outcrop, ancient Noachian-era layered mudstone, "
        "fine laminated sedimentary layers, drill target candidate, "
        "NASA Perseverance rover mastcam close-up scientific perspective, "
        "midday sol lighting, photorealistic, ultra-detailed, 8K, no watermark"
    ),
    (
        "sand_dunes_afternoon",
        "Mars aeolian sand dunes, rippled fine dark basaltic sand, "
        "wind-sculpted barchan dune forms, warm afternoon sol light, "
        "medium-length shadows eastward, NASA Perseverance rover navcam wide-angle, "
        "photorealistic, ultra-detailed, 8K, no watermark"
    ),
    (
        "lander_return_path",
        "Mars surface, clear rover wheel tracks pressed into regolith leading back toward lander, "
        "distant glint of rover lander hardware on horizon, flat traversable ground, "
        "early morning golden sol light, long warm shadows, "
        "NASA Perseverance rover navcam rear perspective, photorealistic, 8K, no watermark"
    ),
    (
        "olympus_mons_vista",
        "Mars surface near Olympus Mons base, massive shield volcano slope visible on horizon, "
        "vast flat lava plains, scattered volcanic rocks, thin atmosphere, "
        "dramatic wide panoramic view, afternoon sol lighting, "
        "photorealistic, ultra-detailed, 8K, NASA Mars photography style, no watermark"
    ),
]

VIDEO_PROMPTS = [
    (
        "rover_exploration_dolly",
        "Mars terrain exploration, NASA Perseverance rover POV camera, "
        "Jezero Crater floor, slow cinematic dolly forward, parallax rock movement, "
        "dust kicked up by wheels, golden hour sol lighting, long dramatic shadows, "
        "thin CO2 atmosphere haze, suspended dust particles, iron oxide red terrain, "
        "photorealistic, cinematic 4K, film grain, anamorphic lens flare, NASA documentary style"
    ),
    (
        "dust_storm_dramatic",
        "Mars surface, massive dust storm approaching, handheld shaky camera, "
        "dust particles whipping past lens, dramatic darkening sky, "
        "rover POV, orange-brown dust wall on horizon, "
        "photorealistic, cinematic 4K, ultra-detailed, NASA documentary style"
    ),
    (
        "crater_rim_reveal",
        "Mars crater rim, sweeping panoramic tilt-up from rocky ground to vast crater interior, "
        "epic wide reveal, ancient impact basin 40km diameter, layered walls, "
        "golden hour sol lighting, thin atmosphere haze, "
        "photorealistic, cinematic 4K, anamorphic, NASA documentary style"
    ),
    (
        "scientific_sample_orbital",
        "Mars bedrock outcrop, slow orbital arc camera movement around scientific target, "
        "rack focus from foreground rocks to background terrain, "
        "NASA Perseverance rover arm visible, midday sol lighting, "
        "photorealistic, cinematic 4K, ultra-detailed, NASA documentary style"
    ),
]

MODEL_IMAGE = "seedream-5-0-260128"
MODEL_VIDEO = "dreamina-seedance-2-0-fast-260128"
POLL_INTERVAL = 8
MAX_WAIT = 360


async def generate_image(name: str, prompt: str) -> dict:
    out_path = OUT_IMAGES / f"{name}.jpg"
    if out_path.exists():
        print(f"  [skip] {name}.jpg already exists")
        return {"name": name, "path": str(out_path), "skipped": True}

    print(f"  [image] generating {name}...")
    payload = {
        "model": MODEL_IMAGE,
        "prompt": prompt,
        "size": "1920x1080",
        "response_format": "b64_json",
        "n": 1,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{BASE_URL}/images/generations",
            headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"},
            json=payload,
        )
        if r.status_code != 200:
            payload["size"] = "2048x2048"
            r = await client.post(
                f"{BASE_URL}/images/generations",
                headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"},
                json=payload,
            )
        if r.status_code != 200:
            print(f"  [error] {name}: {r.status_code} {r.text[:300]}")
            return {"name": name, "error": r.text[:300]}

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
            print(f"  [error] {name}: no image data — raw: {str(data)[:300]}")
            return {"name": name, "error": "no image data"}

        img_bytes = base64.b64decode(b64)
        out_path.write_bytes(img_bytes)
        size_kb = len(img_bytes) // 1024
        print(f"  [done]  {name}.jpg — {size_kb}KB")
        return {"name": name, "path": str(out_path), "size_kb": size_kb}


async def create_video_task(prompt: str) -> str:
    payload = {
        "model": MODEL_VIDEO,
        "content": [{"type": "text", "text": prompt}],
        "parameters": {"duration": 5, "resolution": "1080p", "watermark": False},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{BASE_URL}/contents/generations/tasks",
            headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"},
            json=payload,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("id") or data["data"]["task_id"]


async def poll_video(task_id: str) -> str:
    deadline = time.time() + MAX_WAIT
    async with httpx.AsyncClient(timeout=30) as client:
        while time.time() < deadline:
            r = await client.get(
                f"{BASE_URL}/contents/generations/tasks/{task_id}",
                headers={"Authorization": f"Bearer {key()}"},
            )
            r.raise_for_status()
            data = r.json()
            status = data.get("status", "").lower()
            if status in ("succeeded", "completed", "success"):
                content = data.get("content", {})
                if isinstance(content, dict):
                    return content.get("video_url", "")
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "video":
                            return item["video_url"]
            if status in ("failed", "error"):
                raise RuntimeError(f"Task failed: {data}")
            print(f"    polling {task_id[:16]}... status={status}")
            await asyncio.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Task {task_id} timed out")


async def generate_video(name: str, prompt: str) -> dict:
    out_path = OUT_VIDEOS / f"{name}.mp4"
    if out_path.exists():
        print(f"  [skip] {name}.mp4 already exists")
        return {"name": name, "path": str(out_path), "skipped": True}

    print(f"  [video] submitting {name}...")
    try:
        task_id = await create_video_task(prompt)
        print(f"  [video] task {task_id[:20]}... polling...")
        video_url = await poll_video(task_id)
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            r = await client.get(video_url)
            r.raise_for_status()
            out_path.write_bytes(r.content)
        size_kb = out_path.stat().st_size // 1024
        print(f"  [done]  {name}.mp4 — {size_kb}KB")
        return {"name": name, "path": str(out_path), "size_kb": size_kb}
    except Exception as e:
        print(f"  [error] {name}: {e}")
        return {"name": name, "error": str(e)}


async def main():
    print("=== MarsVision Media Generation ===\n")

    print(f"Generating {len(IMAGE_PROMPTS)} images in parallel (Seedream 5.0)...")
    image_results = await asyncio.gather(*[generate_image(n, p) for n, p in IMAGE_PROMPTS])

    print(f"\nGenerating {len(VIDEO_PROMPTS)} videos (Seedance 2.0, 1080p 5s each)...")
    video_results = []
    for name, prompt in VIDEO_PROMPTS:
        result = await generate_video(name, prompt)
        video_results.append(result)

    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "models": {"image": MODEL_IMAGE, "video": MODEL_VIDEO},
        "images": image_results,
        "videos": video_results,
    }
    manifest_path = Path("docs/generated_media/manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2))

    ok_img = sum(1 for r in image_results if "size_kb" in r)
    ok_vid = sum(1 for r in video_results if "size_kb" in r)
    print(f"\n=== Done ===")
    print(f"Images: {ok_img}/{len(IMAGE_PROMPTS)} generated")
    print(f"Videos: {ok_vid}/{len(VIDEO_PROMPTS)} generated")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    asyncio.run(main())
