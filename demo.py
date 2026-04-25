#!/usr/bin/env python3
"""
MarsVision — Self-running demo.
Runs a full autonomous mission and prints the live agent trace.
No config needed. Works out of the box with mock sensors.

Usage:
    python demo.py
    python demo.py "Explore the crater rim and document findings"
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
RED = "\033[31m"; GREEN = "\033[92m"; YELLOW = "\033[33m"
CYAN = "\033[36m"; BLUE = "\033[34m"; MAG = "\033[35m"

PHASE_COLOR = {
    "mission_start": CYAN, "sensing": BLUE, "reasoning": MAG,
    "plan": YELLOW, "navigating": YELLOW, "safety_halt": RED,
    "generating_video": GREEN, "video_complete": GREEN,
    "training_data": CYAN, "learning": CYAN, "mission_complete": GREEN,
}
PHASE_ICON = {
    "mission_start": "🚀", "sensing": "📡", "reasoning": "🧠",
    "plan": "🗺 ", "navigating": "🛸", "safety_halt": "⚠️ ",
    "generating_video": "🎬", "video_complete": "✅",
    "training_data": "📦", "learning": "💾", "mission_complete": "🏁",
}

BANNER = f"""
{RED}{BOLD}╔══════════════════════════════════════════════════════════════╗
║            MARSVISION — AUTONOMOUS ROVER DEMO                ║
║   Seedream 5.0 Perception  ·  Seedance 2.0 Multi-Ref I2V     ║
║   RLDS Training Data Export  ·  Physical AI  ·  Track 4      ║
╚══════════════════════════════════════════════════════════════╝{RESET}
"""


def on_event(phase: str, detail: str, data: dict):
    color = PHASE_COLOR.get(phase, "\033[37m")
    icon = PHASE_ICON.get(phase, "·")
    ts = time.strftime("%H:%M:%S")
    print(f"  {DIM}{ts}{RESET}  {color}{icon}  [{phase}]{RESET}  {detail}")


def print_telemetry():
    from bridge.mock_sensors import get_snapshot
    s = get_snapshot()
    o, i, l = s["odometry"], s["imu"], s["lidar"]
    print(f"""
{BOLD}── Live Telemetry ──────────────────────────────────────{RESET}
  Position   ({o['x']:.3f}, {o['y']:.3f}) m    Heading  {i['yaw_deg']:.1f}°
  Tilt       {i['pitch_deg']:.1f}°              LIDAR    {l['min_distance_m']:.2f} m
  Battery    {s['battery_pct']}%                Sol      {s['sol']}
{BOLD}────────────────────────────────────────────────────────{RESET}""")


async def main():
    print(BANNER)
    goal = (
        sys.argv[1] if len(sys.argv) > 1
        else "Explore the crater rim, document terrain, and generate training data"
    )
    print(f"{BOLD}Mission goal:{RESET} {goal}\n")
    print_telemetry()
    print(f"\n{BOLD}── Autonomous Mission Trace ────────────────────────────{RESET}")

    from hermes_rover.autonomous_agent import run_mission
    t0 = time.time()
    result = await run_mission(goal, on_event=on_event)
    elapsed = time.time() - t0

    trace = result.get("trace", [])
    outcome_color = GREEN if result.get("success") else RED
    print(f"""
{BOLD}── Mission Summary ─────────────────────────────────────{RESET}
  Outcome       : {outcome_color}{result.get('outcome', 'unknown')}{RESET}
  Distance      : {result.get('distance_traveled_m', 0):.1f} m
  Events logged : {len(trace)}
  Wall time     : {elapsed:.1f}s
  Video mode    : {result.get('video_mode', '—')}
  Dataset       : {result.get('dataset_path', '~/marsvision_dataset/')}
{BOLD}────────────────────────────────────────────────────────{RESET}""")

    Path("demo_output.json").write_text(json.dumps({
        "goal": result.get("goal"), "outcome": result.get("outcome"),
        "distance_m": result.get("distance_traveled_m"),
        "events": len(trace), "wall_time_s": round(elapsed, 2),
        "video_mode": result.get("video_mode"),
        "trace_summary": [{"phase": e["phase"], "detail": e["detail"]} for e in trace],
    }, indent=2))

    print(f"{BOLD}What just happened:{RESET}")
    print(f"  1. Agent read live IMU, LIDAR, odometry (Mars gravity 3.721 m/s²)")
    print(f"  2. Seed 2.0 reasoned about the goal and planned a route")
    print(f"  3. Rover navigated to target coordinates")
    print(f"  4. Seedream 5.0 generated terrain images from 3 camera angles simultaneously")
    print(f"  5. Seedance 2.0 multi-reference I2V animated all frames into cinematic video")
    print(f"  6. Mission exported as RLDS-compatible episode (BC/DAgger/IQL/ACT/RT-2/OpenVLA)")
    print(f"  7. Strategy saved to SQLite memory for future missions")
    print(f"\n  {DIM}Full trace → demo_output.json{RESET}")
    print(f"  {DIM}Run again: python demo.py \"your goal here\"{RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
