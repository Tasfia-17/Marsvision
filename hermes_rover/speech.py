"""
IonRouter speech-to-text for voice mission commands.
Converts audio (OGG/MP3/WAV) to text for Telegram voice messages.
"""
import os
import httpx

_KEY = os.getenv("IONROUTER_API_KEY", "sk-bb3d84f1cea67cd03ef7e1355f51e184837a72cfd321fbbb")
_BASE = os.getenv("IONROUTER_BASE_URL", "https://ionrouter.io")


async def transcribe(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Transcribe audio bytes to text. Returns transcription string."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{_BASE}/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {_KEY}"},
            files={"file": (filename, audio_bytes, "audio/ogg")},
            data={"model": "whisper-1", "language": "en"},
        )
        if r.status_code == 200:
            return r.json().get("text", "").strip()
        # fallback
        return ""
