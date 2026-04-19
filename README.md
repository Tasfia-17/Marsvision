# 🔴 MarsVision — Autonomous Mars Rover

> **AI Lab: Seed Agents Challenge · Track 4 — Physical AI Simulation**

MarsVision is a fully autonomous Mars rover agent that navigates a physics simulation, perceives its environment using **Seedream 5.0**, generates cinematic mission footage with **Seedance 2.0**, and delivers everything to your Telegram — all driven by natural language.

No waypoints. No scripted paths. Pure autonomous AI decision-making.

---

## Demo

| CLI Mission Trace | Mission Control Dashboard |
|---|---|
| ![CLI](docs/screenshots/hermes_cli_mission.png) | ![Dashboard](docs/screenshots/dashboard.png) |

**Pipeline:**
```
Voice / Text  →  Agent Reasoning  →  Physics Simulation
     ↓                                      ↓
IonRouter STT          Seed 2.0 (plan)    IMU · LIDAR · Odometry
                                                ↓
                              Seedream 5.0 (terrain perception)
                                                ↓
                              Seedance 2.0 I2V (cinematic video)
                                                ↓
                              Telegram · Dashboard · CLI
```

---

## What Makes It Different

Most AI video tools generate generic content from text prompts. MarsVision does something fundamentally different:

1. **The agent navigates real physics** — Mars gravity (3.721 m/s²), LIDAR hazard detection, IMU tilt limits, odometry tracking
2. **Seedream 5.0 generates what the rover sees** — photorealistic terrain images derived from actual telemetry (position, heading, hazard proximity)
3. **Seedance 2.0 animates those images** — image-to-video with cinematic motion, dust, atmosphere, sol lighting
4. **The agent learns** — successful strategies are saved to SQLite and reused on future missions

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    CONTROL LAYER                        │
│   CLI · Telegram Bot · Web Dashboard · Voice (IonRouter)│
└────────────────────┬────────────────────────────────────┘
                     │ natural language goal
┌────────────────────▼────────────────────────────────────┐
│                  AGENT LAYER                            │
│                                                         │
│  1. SENSE    → read IMU, LIDAR, odometry                │
│  2. SAFETY   → tilt check, obstacle check               │
│  3. REASON   → Seed 2.0 plans route + scene             │
│  4. ACT      → navigate_to, drive_rover                 │
│  5. PERCEIVE → Seedream 5.0 generates terrain image     │
│  6. GENERATE → Seedance 2.0 I2V animates the image      │
│  7. LEARN    → save behavior to SQLite memory           │
│  8. REPORT   → PDF + video → Telegram                   │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│               SIMULATION LAYER                          │
│   Mars physics bridge · IMU · LIDAR · Odometry          │
│   Mars gravity 3.721 m/s² · Collision · Friction        │
│   (Gazebo Harmonic when available, mock bridge otherwise)│
└─────────────────────────────────────────────────────────┘
```

---

## ByteDance Seed Models Used

| Model | Role |
|---|---|
| **Seed 2.0** | Mission reasoning — plans route, writes scene description, detects intent |
| **Seedream 5.0** | Terrain perception — generates photorealistic Mars terrain from telemetry |
| **Seedance 2.0 Fast** | Video generation — animates terrain image into cinematic I2V footage |
| **IonRouter STT** | Voice commands — multilingual speech-to-text for Telegram voice messages |

---

## Tech Stack

| Layer | Technologies |
|---|---|
| AI | Seed 2.0 (OpenRouter), Seedream 5.0, Seedance 2.0, IonRouter |
| Backend | Python 3.12, FastAPI, Uvicorn, SQLite |
| Simulation | Physics bridge (Mars gravity, LIDAR, IMU, odometry) |
| Frontend | Next.js 15, React 19, Tailwind CSS, Canvas API |
| Integrations | python-telegram-bot, WebSocket, SSE |

---

## Project Structure

```
marsvision/
├── cli.py                          # Interactive CLI with colored trace
├── start.sh                        # One-command startup
├── .env                            # API keys
│
├── bridge/
│   └── mock_sensors.py             # Mars physics simulation (IMU/LIDAR/odometry)
│
├── hermes_rover/
│   ├── autonomous_agent.py         # Core agent loop (sense→reason→act→learn)
│   ├── perception.py               # Seedream 5.0 terrain image generation
│   ├── speech.py                   # IonRouter speech-to-text
│   └── tools/
│       ├── scene_video_tool.py     # Seedance 2.0 I2V video generation
│       ├── drive_tool.py           # Rover drive commands
│       ├── navigate_tool.py        # Goal-directed navigation
│       ├── sensor_tool.py          # Sensor reading
│       ├── hazard_tool.py          # Hazard detection
│       ├── memory_tool.py          # Persistent behavior memory
│       ├── report_tool.py          # PDF mission reports
│       └── camera_tool.py          # Camera capture (Gazebo)
│
├── api/
│   └── main.py                     # FastAPI: telemetry, missions, WebSocket, SSE
│
├── telegram_bot/
│   └── marsvision_bot.py           # Telegram bot (voice + text commands)
│
├── dashboard/
│   ├── app/page.tsx                # Mission control dashboard
│   └── lib/                        # API client, types, config
│
└── simulation/
    ├── worlds/mars_terrain.sdf     # Gazebo Mars world
    └── models/perseverance/        # NASA Perseverance rover model
```

---

## Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/Tasfia-17/Marsvision.git
cd Marsvision
cp .env.example .env
# Fill in your API keys (see below)
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
cd dashboard && npm install && cd ..
```

### 3. Configure `.env`

```bash
OPENROUTER_API_KEY=sk-or-v1-...        # Free tier at openrouter.ai
BYTEPLUS_API_KEY=...                    # Provided by hackathon
IONROUTER_API_KEY=...                   # Provided by hackathon
TELEGRAM_BOT_TOKEN=...                  # From @BotFather
TELEGRAM_ALLOWED_USERS=your_user_id    # From @userinfobot
```

### 4. Run

```bash
# Option A: all services at once
./start.sh

# Option B: individually
python -m uvicorn api.main:app --port 8000     # API
cd dashboard && npm run dev                     # Dashboard → http://localhost:3000
python telegram_bot/marsvision_bot.py          # Telegram bot
python cli.py                                   # Interactive CLI
```

---

## CLI Usage

```
▶ HERMES-ROVER Explore the crater rim and document findings

  🚀 [mission_start] Goal: Explore the crater rim and document findings
  📡 [sensing] Position (0.01, 0.00)m | Tilt 2.6° | LIDAR 8.9m
  🧠 [reasoning] Planning mission route...
  🗺  [plan] Target: (15.0, 8.0)m | Scene: approaching crater rim
  🛸 [navigating] Driving to (15.0, 8.0)m...
  🛸 [navigating] Arrived. Distance: 17.0m
  🎬 [generating_video] Calling Seedance 2.0...
  ✅ [video_complete] Video ready: 4537KB | Mode: i2v_seedream
  💾 [learning] Saved behavior to memory
  🏁 [mission_complete] Mission done. 11 events logged.

── Mission Summary ─────────────────────────
  Distance traveled : 17.0 m
  Final position    : {'x': 15.09, 'y': 7.99}
  Video mode        : i2v_seedream
  Video saved       : /home/user/rover_videos/scene_1234.mp4
```

**CLI commands:**
- `telemetry` — live sensor data
- `status` — last mission trace
- `history` — learned behaviors
- Any other text — starts an autonomous mission

---

## Telegram Commands

| Command | Description |
|---|---|
| `/start` | Show help |
| `/mission <goal>` | Start autonomous mission |
| `/telemetry` | Live sensor data |
| `/video <scene>` | Generate Seedance video |
| `/status` | Mission log |
| Voice message | Transcribed via IonRouter → runs as mission |

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/telemetry` | GET | Full sensor snapshot |
| `/status` | GET | Dashboard-compatible telemetry |
| `/mission/start` | POST | Start autonomous mission |
| `/mission/log` | GET | Mission event log |
| `/mission/log/stream` | GET | SSE live event stream |
| `/video/generate` | POST | Generate Seedance video |
| `/video/latest` | GET | Latest video file |
| `/terrain/latest` | GET | Latest Seedream terrain image |
| `/drive` | POST | Direct drive command |
| `/navigate` | POST | Navigate to coordinates |
| `/hazards` | GET | Hazard map |
| `/sessions` | GET | Mission history |
| `/ws/telemetry` | WebSocket | Live telemetry stream |

---

## Scoring Criteria

| Criterion | Weight | How we address it |
|---|---|---|
| **Video Output Quality** | 40% | Seedream 5.0 → Seedance 2.0 I2V pipeline produces 4-5MB cinematic Mars footage from real telemetry |
| **Agentic Execution** | 40% | 12-step visible trace: sense → safety → reason → plan → navigate → re-sense → perceive → generate → learn → report |
| **Demo & Presentation** | 20% | Voice commands, live dashboard, Telegram delivery, 4 Seed models used end-to-end |

---

## Credits

- **ByteDance Seed Team** — Seedream 5.0, Seedance 2.0, Seed 2.0
- **IonRouter** — Multilingual speech-to-text
- **Snehal (@SnehalRekt)** — Original Hermes Mars Rover simulation base
- **Tasfia (@Tasfia-17)** — MarsVision AI pipeline

---

## License

MIT
