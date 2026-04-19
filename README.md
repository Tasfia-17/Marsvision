# MarsVision — Autonomous Mars Rover

> **AI Lab: Seed Agents Challenge · Track 4 — Physical AI Simulation**
> Built for the ByteDance Seed Agents Hackathon · Demo Day: May 2, 2026

MarsVision is a fully autonomous Mars rover agent. Give it a natural language goal  it plans the mission, navigates real physics simulation, perceives the terrain using **Seedream 5.0**, generates cinematic footage with **Seedance 2.0**, and delivers a mission report to your Telegram. No waypoints. No scripted paths. Pure autonomous AI.

---

## Demo

| CLI  Live Agent Trace | Mission Control Dashboard |
|---|---|
| ![CLI](docs/screenshots/hermes_cli_mission.png) | ![Dashboard](docs/screenshots/dashboard.png) |

**Example mission:**
```
 MARSVISION  Explore the crater rim and document findings

  [mission_start]     Goal: Explore the crater rim and document findings
  [sensing]           Position (0.01, 0.00)m | Tilt 2.6 | LIDAR 8.9m
  [reasoning]         Planning mission route...
  [plan]             Target: (15.0, 8.0)m | Scene: approaching crater rim
  [navigating]        Driving to (15.0, 8.0)m...
  [navigating]        Arrived. Distance: 17.0m | Accuracy: 22cm
  [sensing]           At destination: pos=(15.09, 7.99) heading=28.1
  [generating_video]  Calling Seedance 2.0... scene: crater rim approach
  [video_complete]    Video ready: 4537KB | Mode: i2v_seedream
  [learning]          Saved behavior to memory for future missions
  [mission_complete]  Mission done. 11 events logged.
```

---

## What Makes It Different

Most AI video tools generate generic content from text prompts. MarsVision does something fundamentally different:

1. **Real physics**  Mars gravity (3.721 m/s), LIDAR hazard detection, IMU tilt limits, odometry tracking
2. **AI perception**  Seedream 5.0 generates photorealistic terrain images from actual telemetry (position, heading, hazard proximity, sol lighting)
3. **Cinematic animation**  Seedance 2.0 I2V animates those terrain images into mission footage
4. **Persistent learning**  successful strategies saved to SQLite, reused on future missions with ranked confidence

---

## Architecture

```

                      CONTROL LAYER                           
                                                              
   CLI (python cli.py)    Telegram Bot    Web Dashboard       
   Natural language    Voice (IonRouter STT)    REST     

                            natural language goal

                      AGENT LAYER                             
                                                              
  Step 1  SENSE      read IMU, LIDAR, odometry              
  Step 2  SAFETY     tilt check (>25 = halt), obstacle check
  Step 3  REASON     Seed 2.0 plans route + scene context    
  Step 4  ACT        navigate_to(x,y), drive_rover          
  Step 5  RE-SENSE   confirm arrival, read final state       
  Step 6  PERCEIVE   Seedream 5.0 generates terrain image    
  Step 7  GENERATE   Seedance 2.0 I2V animates the image     
  Step 8  LEARN      save behavior to SQLite memory          
  Step 9  REPORT     PDF + video  Telegram delivery         

                           

                   SIMULATION LAYER                           
                                                              
   Physics bridge: Mars gravity 3.721 m/s                   
   Sensors: IMU  LIDAR  Odometry  Camera                  
   Gazebo Harmonic (when installed) or mock bridge            
   Rover model: NASA Perseverance (6-wheel diff-drive)        

```

---

## ByteDance Seed Models

| Model | Role | How Used |
|---|---|---|
| **Seed 2.0** | Mission reasoning | Plans route, writes scene description, detects intent from natural language |
| **Seedream 5.0** | Terrain perception | Generates photorealistic Mars terrain images from telemetry data |
| **Seedance 2.0 Fast** | Video generation | Animates terrain image  cinematic I2V mission footage |
| **IonRouter STT** | Voice commands | Transcribes Telegram voice messages in 100+ languages |

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

 cli.py                              # Interactive CLI with colored agent trace
 start.sh                            # One-command startup (all services)
 requirements.txt
 .env.example

 bridge/
    mock_sensors.py                 # Mars physics simulation (IMU/LIDAR/odometry)
    sensor_bridge.py               # Gazebo Transport bridge (when Gazebo installed)

 hermes_rover/
    autonomous_agent.py             # Core agent loop (sensereasonactlearnreport)
    perception.py                   # Seedream 5.0 terrain image generation
    speech.py                       # IonRouter speech-to-text
    mission_agent.py                # Programmatic mission runner
    hazard_detector.py              # LIDAR-based hazard detection
    telemetry.py                    # Telemetry snapshot utilities
   
    tools/
       scene_video_tool.py         # Seedance 2.0 I2V video generation  KEY
       drive_tool.py               # Rover drive commands
       navigate_tool.py            # Goal-directed navigation with hazard checks
       sensor_tool.py              # Sensor reading (IMU, odometry, LIDAR)
       hazard_tool.py              # Hazard detection and reporting
       memory_tool.py              # Persistent behavior memory (SQLite)
       report_tool.py              # PDF mission report generation
       camera_tool.py              # Camera capture (Gazebo frames)
       tool_registry.py            # Tool registration
   
    memory/
       memory_manager.py           # SQLite: sessions, hazards, learned behaviors
       session_logger.py           # Session logging
   
    skills/
       cliff_protocol/             # Cliff detection behavior
       obstacle_avoidance/         # Obstacle avoidance behavior
       storm_protocol/             # Dust storm protocol
       terrain_assessment/         # Terrain traversability assessment
       self_improvement/           # Behavior learning and improvement
       camera_telegram_delivery/   # Camera  Telegram delivery
   
    config/
        system_prompt.md            # Agent system prompt
        hermes_config.yaml          # Agent configuration

 api/
    main.py                         # FastAPI: telemetry, missions, WebSocket, SSE

 telegram_bot/
    marsvision_bot.py               # Telegram bot (voice + text + video delivery)

 dashboard/
    app/
       page.tsx                    # Mission control dashboard (main page)
       layout.tsx
    components/
       MapView.tsx                 # Canvas rover map with path + hazards
       RoverStatus.tsx             # Position, speed, heading, uptime
       SensorPanel.tsx             # IMU roll/pitch/yaw, LIDAR, hazard status
       CommandInput.tsx            # Natural language command input
       SessionTimeline.tsx         # Mission history
       HazardAlert.tsx             # Hazard warning banner
    lib/
        api.ts                      # API client
        websocket.ts                # WebSocket manager with auto-reconnect
        types.ts                    # TypeScript types
        config.ts                   # URL configuration

 simulation/
    worlds/
       mars_terrain.sdf            # Gazebo Mars world (headless)
       mars_terrain_websocket.sdf  # Gazebo Mars world (browser viz)
    models/perseverance/            # NASA Perseverance rover model
        model.sdf                   # 6-wheel diff-drive, NavCam, HazCam, LIDAR
        model.config

 tests/
     test_tools.py
     test_api.py
     test_bridge.py
     test_mission_agent.py
```

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/Tasfia-17/Marsvision.git
cd Marsvision
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
cd dashboard && npm install && cd ..
```

### 3. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# LLM reasoning (free tier at openrouter.ai  no card needed)
OPENROUTER_API_KEY=sk-or-v1-...
LLM_MODEL=google/gemini-2.0-flash-exp:free

# Seedance + Seedream (BytePlus ModelArk  hackathon provided)
BYTEPLUS_API_KEY=your-key-here
BYTEPLUS_BASE_URL=https://ark.ap-southeast.bytepluses.com/api/v3

# IonRouter speech-to-text (hackathon provided)
IONROUTER_API_KEY=your-key-here

# Telegram (free  from @BotFather)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_ALLOWED_USERS=your_numeric_user_id   # from @userinfobot
```

### 4. Run

**Option A  all services at once:**
```bash
./start.sh
```

**Option B  individually:**
```bash
# Terminal 1: API server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Dashboard
cd dashboard && npm run dev
#  http://localhost:3000

# Terminal 3: Telegram bot
python telegram_bot/marsvision_bot.py

# Terminal 4: Interactive CLI
python cli.py
```

---

## CLI Usage

```bash
python cli.py
```

```

          MARSVISION  AUTONOMOUS ROVER CLI               
   Seedream 5.0 Perception  Seedance 2.0 I2V  Seed 2.0 


 MARSVISION  Explore the crater rim and document findings
 MARSVISION  telemetry
 MARSVISION  status
 MARSVISION  history
 MARSVISION  exit
```

**Built-in commands:**
| Command | Description |
|---|---|
| Any text | Starts an autonomous mission |
| `telemetry` | Show live IMU, LIDAR, odometry, battery |
| `status` | Show last mission trace (all 12 steps) |
| `history` | Show learned behaviors from SQLite |
| `help` | Show banner |
| `exit` | Quit |

---

## Telegram Commands

| Command | Description |
|---|---|
| `/start` | Show help and available commands |
| `/mission <goal>` | Start autonomous mission |
| `/telemetry` | Live sensor data |
| `/video <scene>` | Generate Seedance video directly |
| `/status` | Last 5 mission log events |
| Voice message | Transcribed via IonRouter  runs as mission |

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/telemetry` | GET | Full sensor snapshot (IMU, LIDAR, odometry) |
| `/status` | GET | Dashboard-compatible telemetry |
| `/mission/start` | POST | `{"goal": "..."}`  start autonomous mission |
| `/mission/log` | GET | Last 50 mission events |
| `/mission/log/stream` | GET | SSE live event stream |
| `/mission/trace` | GET | Full agent reasoning trace |
| `/video/generate` | POST | `{"scene_context": "..."}`  generate Seedance video |
| `/video/latest` | GET | Latest generated video file |
| `/terrain/latest` | GET | Latest Seedream terrain image |
| `/drive` | POST | `{"linear_ms": 0.5, "angular_rads": 0, "duration_s": 2}` |
| `/navigate` | POST | `{"x": 15.0, "y": 8.0}` |
| `/hazards` | GET | Hazard map from SQLite |
| `/sessions` | GET | Mission history |
| `/ws/telemetry` | WebSocket | Live telemetry stream (1Hz) |

---

## Rover Tools

The agent has 8 tools it calls autonomously:

| Tool | Description |
|---|---|
| `drive_rover` | Fixed-duration drive with speed + angular velocity |
| `read_sensors` | Read IMU, odometry, LIDAR, camera |
| `navigate_to` | Goal-directed navigation with hazard checks |
| `check_hazards` | LIDAR-based obstacle detection |
| `rover_memory` | Save/retrieve learned behaviors from SQLite |
| `generate_report` | Generate PDF mission report |
| `capture_camera_image` | Capture camera frame (Gazebo or mock) |
| `generate_scene_video` | **Seedream 5.0  Seedance 2.0 I2V**  new |

---

## Simulation

The rover model is based on NASA Perseverance:

| Property | Value |
|---|---|
| Drive system | 6-wheel differential drive |
| Physics | ODE rigid-body, Mars gravity 3.721 m/s |
| Max speed | 1.0 m/s linear, 0.5 rad/s angular |
| Tilt limit | 25 (auto-halt) |
| Sensors | IMU, NavCam, HazCam (front/rear), MastCam, LIDAR, Odometry |
| Simulation | Gazebo Harmonic (optional) or mock physics bridge |

**With Gazebo installed:**
```bash
# Install Gazebo Harmonic (Ubuntu 22.04/24.04)
sudo apt install gz-harmonic

# Run full simulation
gz sim simulation/worlds/mars_terrain.sdf
```

**Without Gazebo** (default): the mock physics bridge provides identical telemetry data with realistic Mars physics constants.

---

## Scoring Criteria

| Criterion | Weight | Our Approach |
|---|---|---|
| **Video Output Quality** | 40% | Seedream 5.0 generates photorealistic terrain  Seedance 2.0 I2V animates it. Output: 4-5MB cinematic Mars footage per mission. |
| **Agentic Execution** | 40% | 12-step visible trace: sense  safety check  reason  plan  navigate  re-sense  perceive  generate  learn  report. Agent recovers from hazards, saves learned behaviors. |
| **Demo & Presentation** | 20% | Voice commands (IonRouter), live dashboard (WebSocket), Telegram delivery, 4 Seed models used end-to-end. |

---

## Credits

- **ByteDance Seed Team**  Seedream 5.0, Seedance 2.0, Seed 2.0 models
- **IonRouter**  Multilingual speech-to-text
- **Snehal (@SnehalRekt)**  Original Mars rover simulation base
- **Tasfia (@Tasfia-17)**  MarsVision AI pipeline, Seedance integration, autonomous agent

---

## License

MIT
