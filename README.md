# MarsVision - Autonomous Mars Rover

> AI Lab: Seed Agents Challenge - Track 4: Physical AI Simulation
> ByteDance Seed Agents Hackathon - Demo Day: May 2, 2026

MarsVision is a fully autonomous Mars rover agent that navigates real physics simulation, perceives its environment using Seedream 5.0, generates cinematic training footage with Seedance 2.0, and exports structured robot training datasets - all from a single natural language goal.

No waypoints. No scripted paths. Pure autonomous AI that generates its own training data.

---

## What It Does

Give the rover a goal in plain English. It plans the mission, navigates Mars terrain with real physics, generates photorealistic video of what it sees, and exports a labeled behavior cloning dataset that can train a robot policy.

```
Input:  "Explore the crater rim and document findings"

Output:
  - Cinematic mission video (Seedream 5.0 -> Seedance 2.0 I2V)
  - Structured training dataset (observation, action, outcome pairs)
  - PDF mission report
  - Live telemetry delivered to Telegram
```

---

## Demo

| CLI - Live Agent Trace | Mission Control Dashboard |
|---|---|
| ![CLI](docs/screenshots/hermes_cli_mission.png) | ![Dashboard](docs/screenshots/dashboard.png) |

**Example mission trace:**

```
  [mission_start]     Goal: Explore the crater rim and document findings
  [sensing]           Position (0.01, 0.00)m | Tilt 2.6 deg | LIDAR 8.9m
  [reasoning]         Planning mission route...
  [plan]              Target: (15.0, 8.0)m | Scene: approaching crater rim
  [navigating]        Driving to (15.0, 8.0)m...
  [navigating]        Arrived. Distance: 17.0m | Accuracy: 22cm
  [sensing]           At destination: pos=(15.09, 7.99) heading=28.1 deg
  [generating_video]  Calling Seedance 2.0... scene: crater rim approach
  [video_complete]    Video ready: 4537KB | Mode: i2v_seedream
  [training_data]     Dataset episode saved: episode_1234 | Total: 7 episodes
  [learning]          Saved behavior to memory for future missions
  [mission_complete]  Mission done. 12 events logged.
```

---

## Physical AI - Training Data Generation

This is the core of Track 4. Every mission automatically exports a structured training episode:

```json
{
  "episode_id": "episode_1776594823",
  "outcome": "success",
  "environment": "Mars terrain simulation",
  "gravity_ms2": 3.721,
  "steps": [
    {"type": "observation", "position": {"x": 0.01, "y": 0.0}, "tilt_deg": 2.6, "lidar_min_m": 8.9},
    {"type": "action", "action_type": "navigate", "target": {"x": 15.0, "y": 8.0}, "distance_m": 17.0},
    {"type": "observation", "modality": "video", "video_path": "scene_1776594823.mp4", "video_mode": "i2v_seedream"}
  ],
  "compatible_with": ["BC", "DAgger", "IQL", "ACT"]
}
```

Each episode pairs:
- Sensor observations (IMU, LIDAR, odometry) with the actions that followed
- Generated video frames with the telemetry state that produced them
- Mission outcome (success/failure/partial) as the reward signal

Run 100 missions, get 100 labeled training episodes. Feed them to any imitation learning framework to train a robot policy without real-world data collection.

---

## Architecture

```
+----------------------------------------------------------+
|                     CONTROL LAYER                        |
|                                                          |
|   CLI (python cli.py)   Telegram Bot   Web Dashboard     |
|   Natural language <-> Voice (IonRouter STT) <-> REST    |
+------------------------+---------------------------------+
                         | natural language goal
+------------------------v---------------------------------+
|                     AGENT LAYER                          |
|                                                          |
|  Step 1   SENSE      Read IMU, LIDAR, odometry           |
|  Step 2   SAFETY     Tilt check, obstacle check          |
|  Step 3   REASON     Seed 2.0 plans route + scene        |
|  Step 4   PLAN       Set target coordinates              |
|  Step 5   ACT        navigate_to(x, y)                   |
|  Step 6   RE-SENSE   Confirm arrival                     |
|  Step 7   PERCEIVE   Seedream 5.0 generates terrain img  |
|  Step 8   GENERATE   Seedance 2.0 I2V animates image     |
|  Step 9   EXPORT     Save training episode to dataset    |
|  Step 10  LEARN      Save behavior to SQLite memory      |
|  Step 11  REPORT     PDF + video -> Telegram             |
|  Step 12  LOG        Emit all events to SSE stream       |
+------------------------+---------------------------------+
                         |
+------------------------v---------------------------------+
|                  SIMULATION LAYER                        |
|                                                          |
|   Physics bridge: Mars gravity 3.721 m/s2               |
|   Sensors: IMU, LIDAR, Odometry, Camera                  |
|   Gazebo Harmonic (when installed) or mock bridge        |
|   Rover: NASA Perseverance model, 6-wheel diff-drive     |
+----------------------------------------------------------+
```

---

## ByteDance Seed Models

| Model | Role | How Used |
|---|---|---|
| Seed 2.0 | Mission reasoning | Plans route, writes scene description, detects intent |
| Seedream 5.0 | Terrain perception | Generates photorealistic Mars terrain from telemetry |
| Seedance 2.0 Fast | Video generation | Animates terrain image into cinematic I2V footage |
| IonRouter STT | Voice commands | Transcribes Telegram voice messages in 100+ languages |

---

## Video Output Quality

MarsVision uses a two-stage AI pipeline that produces cinematic output no text-to-video tool can match:

**Stage 1 - Seedream 5.0 terrain perception**

The agent reads live telemetry (position, heading, tilt, LIDAR proximity, sol number) and passes it to Seedream 5.0, which generates a photorealistic Mars terrain image grounded in the rover's actual physical state. The image reflects the correct terrain type (crater rim, rocky field, flat plains), lighting angle for the sol, and hazard proximity.

**Stage 2 - Seedance 2.0 image-to-video**

That terrain image becomes the reference frame for Seedance 2.0 I2V. The model animates it with cinematic motion: dolly forward, dust particles, atmospheric haze, sol lighting. Because the input is a real reference image and not a text prompt, the output is visually consistent and grounded in the rover's actual environment.

Result: 4-5MB, 720p, 5-second cinematic clips with native audio. Mode: i2v_seedream.

---

## Agentic Execution

Every mission runs a 12-step autonomous loop. The agent does not follow a script - it reads sensors, reasons about what to do, acts, checks results, and learns.

**Hazard recovery:** If LIDAR detects an obstacle under 1.5m, the agent backs up, replans, and continues. If tilt exceeds 25 degrees, the mission halts and reports the failure explicitly.

**Persistent learning:** Successful strategies are stored in SQLite with a confidence score. On future missions with similar context, the agent retrieves and reuses the highest-confidence behavior instead of replanning from scratch.

**Visible reasoning:** Every step emits a named event to the SSE stream. The dashboard and CLI show the full trace in real time so judges can see the agent thinking, not just the output.

---

## Vision - After the Hackathon

**Short term (1-3 months)**

- Connect to real Gazebo simulation with full physics (already scaffolded in simulation/)
- Add multi-rover coordination: one rover scouts, another films
- Integrate Seedance 2.0 reference-to-video with up to 9 reference images for richer scene continuity

**Medium term (3-12 months)**

- Replace mock physics bridge with real robot hardware (ROS 2 compatible interface already in bridge/sensor_bridge.py)
- Use generated synthetic video data to train robot manipulation policies (the GoferAI / DreamGen approach)
- Build a mission replay system: any past mission can be re-rendered cinematically from its telemetry log

**Long term**

MarsVision is the foundation for AI-native physical simulation: environments where the agent's perception, reasoning, and world-model are all AI-generated rather than hand-authored. The same pipeline applies to warehouse robotics, autonomous vehicles, and any domain where generating synthetic training data from agent behavior is valuable.

The video economy for physical AI is unsolved. MarsVision is the first step toward agents that document their own work cinematically.

---

## Tech Stack

| Layer | Technologies |
|---|---|
| AI | Seed 2.0 (OpenRouter), Seedream 5.0, Seedance 2.0, IonRouter |
| Backend | Python 3.12, FastAPI, Uvicorn, SQLite, WebSocket, SSE |
| Simulation | Physics bridge (Mars gravity, LIDAR, IMU, odometry) |
| Frontend | Next.js 15, React 19, Tailwind CSS, Canvas API |
| Delivery | python-telegram-bot, PDF reports |

---

## Project Structure

```
marsvision/
|
+-- cli.py                              # Interactive CLI with colored agent trace
+-- start.sh                            # One-command startup
+-- requirements.txt
+-- .env.example
|
+-- bridge/
|   +-- mock_sensors.py                 # Mars physics simulation (IMU/LIDAR/odometry)
|   +-- sensor_bridge.py               # Gazebo Transport bridge (when Gazebo installed)
|
+-- hermes_rover/
|   +-- autonomous_agent.py             # Core agent loop (12 steps)
|   +-- perception.py                   # Seedream 5.0 terrain image generation
|   +-- speech.py                       # IonRouter speech-to-text
|   |
|   +-- tools/
|   |   +-- scene_video_tool.py         # Seedance 2.0 I2V video generation
|   |   +-- training_data_tool.py       # Robot training dataset export
|   |   +-- drive_tool.py
|   |   +-- navigate_tool.py
|   |   +-- sensor_tool.py
|   |   +-- hazard_tool.py
|   |   +-- memory_tool.py
|   |   +-- report_tool.py
|   |   +-- camera_tool.py
|   |
|   +-- memory/
|   |   +-- memory_manager.py           # SQLite: sessions, hazards, learned behaviors
|   |
|   +-- skills/
|       +-- cliff_protocol/
|       +-- obstacle_avoidance/
|       +-- storm_protocol/
|       +-- terrain_assessment/
|       +-- self_improvement/
|
+-- api/
|   +-- main.py                         # FastAPI: telemetry, missions, WebSocket, SSE
|
+-- telegram_bot/
|   +-- marsvision_bot.py               # Telegram bot (voice + text + video delivery)
|
+-- dashboard/
|   +-- app/page.tsx                    # Mission control dashboard
|   +-- components/                     # Map, Status, Sensors, Command, Timeline
|   +-- lib/                            # API client, WebSocket, types
|
+-- simulation/
    +-- worlds/mars_terrain.sdf
    +-- models/perseverance/            # NASA Perseverance rover model
```

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/Tasfia-17/Marsvision.git
cd Marsvision
```

### 2. Install

```bash
pip install -r requirements.txt
cd dashboard && npm install && cd ..
```

### 3. Configure .env

```bash
cp .env.example .env
```

```bash
OPENROUTER_API_KEY=sk-or-v1-...
BYTEPLUS_API_KEY=your-key
IONROUTER_API_KEY=your-key
TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_ALLOWED_USERS=your_user_id
```

### 4. Run

```bash
./start.sh
```

Or individually:

```bash
python -m uvicorn api.main:app --port 8000
cd dashboard && npm run dev
python telegram_bot/marsvision_bot.py
python cli.py
```

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| /health | GET | Health check |
| /telemetry | GET | Full sensor snapshot |
| /status | GET | Dashboard-compatible telemetry |
| /mission/start | POST | Start autonomous mission |
| /mission/log | GET | Last 50 mission events |
| /mission/log/stream | GET | SSE live event stream |
| /video/generate | POST | Generate Seedance video |
| /video/latest | GET | Latest video file |
| /terrain/latest | GET | Latest Seedream terrain image |
| /drive | POST | Direct drive command |
| /navigate | POST | Navigate to coordinates |
| /hazards | GET | Hazard map |
| /sessions | GET | Mission history |
| /ws/telemetry | WebSocket | Live telemetry stream (1Hz) |

---

## Telegram Commands

| Command | Description |
|---|---|
| /start | Show help |
| /mission goal | Start autonomous mission |
| /telemetry | Live sensor data |
| /video scene | Generate Seedance video |
| /status | Mission log |
| Voice message | Transcribed via IonRouter, runs as mission |



## License

MIT
