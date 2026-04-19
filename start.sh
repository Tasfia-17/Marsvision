#!/bin/bash
# MarsVision — start all services
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "🚀 Starting MarsVision..."

# 1. FastAPI backend
echo "▶ Starting API server (port 8000)..."
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

# 2. Telegram bot
echo "▶ Starting Telegram bot..."
python telegram_bot/marsvision_bot.py &
BOT_PID=$!

# 3. Dashboard
echo "▶ Starting dashboard (port 3000)..."
cd dashboard && npm run dev &
DASH_PID=$!
cd "$ROOT"

echo ""
echo "✅ MarsVision running:"
echo "   API:       http://localhost:8000"
echo "   Dashboard: http://localhost:3000"
echo "   Telegram:  @marsvision_rover_bot"
echo ""
echo "Press Ctrl+C to stop all services."

trap "kill $API_PID $BOT_PID $DASH_PID 2>/dev/null; echo 'Stopped.'" EXIT
wait
