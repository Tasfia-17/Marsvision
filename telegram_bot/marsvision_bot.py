"""
MarsVision Telegram Bot.
Accepts natural language mission commands, delivers video + reports.
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED = set(int(x) for x in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if x.strip())
API_URL = os.getenv("API_URL", "http://localhost:8000")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _allowed(update: Update) -> bool:
    return not ALLOWED or update.effective_user.id in ALLOWED


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 *MarsVision Rover Online*\n\n"
        "Commands:\n"
        "/mission <goal> — start autonomous mission\n"
        "/telemetry — live sensor data\n"
        "/video <scene> — generate Seedance video\n"
        "/status — mission log\n",
        parse_mode="Markdown"
    )


async def cmd_telemetry(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update): return
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/telemetry")
        data = r.json()
    odom = data["odometry"]
    imu = data["imu"]
    lidar = data["lidar"]
    text = (
        f"📡 *Live Telemetry — Sol {data['sol']}*\n\n"
        f"📍 Position: `({odom['x']:.2f}, {odom['y']:.2f})m`\n"
        f"🧭 Heading: `{imu['yaw_deg']:.1f}°`\n"
        f"📐 Tilt: `{imu['pitch_deg']:.1f}°`\n"
        f"📏 LIDAR min: `{lidar['min_distance_m']:.1f}m`\n"
        f"🔋 Battery: `{data['battery_pct']}%`\n"
        f"⏱ Elapsed: `{data['mission_elapsed_s']:.0f}s`\n"
        f"📏 From base: `{odom['distance_from_origin_m']:.2f}m`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_mission(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update): return
    goal = " ".join(ctx.args) if ctx.args else "explore and document terrain"
    await update.message.reply_text(f"🤖 Starting mission: *{goal}*\nPlanning route...", parse_mode="Markdown")

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{API_URL}/mission/start", json={"goal": goal})
        data = r.json()

    await update.message.reply_text(f"✅ Mission started. Generating cinematic footage...\n_This takes ~60s_", parse_mode="Markdown")

    # Poll for video completion
    await asyncio.sleep(5)
    await _deliver_latest_video(update, goal)


async def cmd_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update): return
    scene = " ".join(ctx.args) if ctx.args else "Mars terrain exploration, rover POV"
    await update.message.reply_text(f"🎬 Generating video: _{scene}_\nCalling Seedance 2.0...", parse_mode="Markdown")

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{API_URL}/video/generate", json={"scene_context": scene, "duration": 5})
        result = r.json()

    if result.get("success"):
        video_path = Path(result["file_path"])
        if video_path.exists():
            await update.message.reply_video(
                video=open(video_path, "rb"),
                caption=f"🎬 *MarsVision — Seedance 2.0*\n_{scene}_",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"✅ Video generated: `{result['file_path']}`", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Generation failed: {result.get('error')}")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update): return
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/mission/log")
        data = r.json()

    log_entries = data["log"][-5:]
    lines = [f"📋 *Mission Log* (last {len(log_entries)} events)\n"]
    for e in log_entries:
        lines.append(f"• `{e['event']}` — {json.dumps({k:v for k,v in e.items() if k not in ('timestamp','event')})[:80]}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Natural language fallback — treat any message as a mission goal."""
    if not _allowed(update): return
    text = update.message.text.lower()

    if any(w in text for w in ["video", "generate", "film", "record", "shoot"]):
        ctx.args = update.message.text.split()
        await cmd_video(update, ctx)
    elif any(w in text for w in ["sensor", "telemetry", "status", "where", "position"]):
        await cmd_telemetry(update, ctx)
    else:
        # Treat as mission goal
        ctx.args = update.message.text.split()
        await cmd_mission(update, ctx)


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages — transcribe with IonRouter then run as mission."""
    if not _allowed(update): return
    await update.message.reply_text("🎙 Transcribing voice command...")
    try:
        file = await ctx.bot.get_file(update.message.voice.file_id)
        audio = await file.download_as_bytearray()
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from hermes_rover.speech import transcribe
        text = await transcribe(bytes(audio))
        if text:
            await update.message.reply_text(f"🎙 Heard: _{text}_", parse_mode="Markdown")
            ctx.args = text.split()
            await cmd_mission(update, ctx)
        else:
            await update.message.reply_text("❌ Could not transcribe. Try typing your command.")
    except Exception as e:
        await update.message.reply_text(f"❌ Voice error: {e}")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{API_URL}/video/latest")
            if r.status_code == 200:
                await update.message.reply_video(
                    video=r.content,
                    caption=f"🎬 *Mission Complete*\n_{caption}_",
                    parse_mode="Markdown"
                )
                return
    except Exception:
        pass
    await update.message.reply_text("⏳ Video still generating. Use /status to check progress.")


def main():
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("telemetry", cmd_telemetry))
    app.add_handler(CommandHandler("mission", cmd_mission))
    app.add_handler(CommandHandler("video", cmd_video))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("MarsVision bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
# Telegram bot
