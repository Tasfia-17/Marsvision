#!/usr/bin/env python3
"""
MarsVision CLI — Interactive mission control terminal.
Type natural language goals, watch the agent reason and act in real time.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bridge.mock_sensors import get_snapshot, get_state_for_video

BANNER = """
\033[31m╔══════════════════════════════════════════════════════════╗
║          MARSVISION — AUTONOMOUS ROVER CLI               ║
║   Seedream 5.0 Perception · Seedance 2.0 I2V · Seed 2.0 ║
╚══════════════════════════════════════════════════════════╝\033[0m
Type a mission goal in plain English, or use a command:
  \033[33mtelemetry\033[0m  — show live sensor data
  \033[33mstatus\033[0m     — show last mission trace
  \033[33mhistory\033[0m    — show learned behaviors
  \033[33mhelp\033[0m       — show this message
  \033[33mexit\033[0m       — quit
"""

PHASE_COLORS = {
    "mission_start":    "\033[36m",   # cyan
    "sensing":          "\033[34m",   # blue
    "reasoning":        "\033[35m",   # magenta
    "plan":             "\033[33m",   # yellow
    "navigating":       "\033[33m",   # yellow
    "safety_halt":      "\033[31m",   # red
    "generating_video": "\033[32m",   # green
    "video_complete":   "\033[92m",   # bright green
    "learning":         "\033[36m",   # cyan
    "mission_complete": "\033[92m",   # bright green
    "video_error":      "\033[31m",   # red
}
RESET = "\033[0m"
DIM   = "\033[2m"
BOLD  = "\033[1m"


def print_telemetry():
    snap = get_snapshot()
    state = get_state_for_video()
    odom = snap["odometry"]
    imu  = snap["imu"]
    lidar = snap["lidar"]
    print(f"""
{BOLD}── Live Telemetry ─────────────────────────────{RESET}
  Position  : ({odom['x']:.3f}, {odom['y']:.3f}) m
  Heading   : {imu['yaw_deg']:.1f}°
  Tilt      : {imu['pitch_deg']:.1f}°
  LIDAR min : {lidar['min_distance_m']:.2f} m
  Battery   : {snap['battery_pct']}%
  Sol       : {snap['sol']}
  From base : {odom['distance_from_origin_m']:.2f} m
  Elapsed   : {snap['mission_elapsed_s']:.0f}s
{BOLD}───────────────────────────────────────────────{RESET}""")


def on_event(phase: str, detail: str, data: dict):
    color = PHASE_COLORS.get(phase, "\033[37m")
    icon = {
        "mission_start":    "🚀",
        "sensing":          "📡",
        "reasoning":        "🧠",
        "plan":             "🗺 ",
        "navigating":       "🛸",
        "safety_halt":      "⚠️ ",
        "generating_video": "🎬",
        "video_complete":   "✅",
        "learning":         "💾",
        "mission_complete": "🏁",
        "video_error":      "❌",
    }.get(phase, "·")
    print(f"  {color}{icon} [{phase}]{RESET} {detail}")


async def run_cli():
    print(BANNER)

    from hermes_rover.autonomous_agent import run_mission, get_trace
    from hermes_rover.memory import memory_manager as mm

    last_trace = []

    while True:
        try:
            goal = input(f"\n{BOLD}\033[31m▶ MARSVISION{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\033[2mMission control offline.\033[0m")
            break

        if not goal:
            continue

        if goal.lower() in ("exit", "quit", "q"):
            print("\033[2mMission control offline.\033[0m")
            break

        if goal.lower() == "telemetry":
            print_telemetry()
            continue

        if goal.lower() == "status":
            trace = get_trace()
            if not trace:
                print("  No mission run yet.")
            else:
                print(f"\n{BOLD}── Last Mission Trace ({len(trace)} events) ──{RESET}")
                for e in trace:
                    on_event(e["phase"], e["detail"], e)
            continue

        if goal.lower() == "history":
            try:
                behaviors = mm.get_learned_behaviors()
                print(f"\n{BOLD}── Learned Behaviors ({len(behaviors)}) ──{RESET}")
                for b in behaviors[:10]:
                    print(f"  · {b.get('trigger','?')[:50]} → {b.get('action','?')[:40]}")
            except Exception as e:
                print(f"  Error: {e}")
            continue

        if goal.lower() == "help":
            print(BANNER)
            continue

        # Run mission
        print(f"\n{DIM}Starting autonomous mission...{RESET}")
        print(f"{BOLD}── Mission: {goal} ──{RESET}")

        result = await run_mission(goal, on_event=on_event)

        print(f"\n{BOLD}── Mission Summary ─────────────────────────{RESET}")
        print(f"  Distance traveled : {result.get('distance_traveled_m', 0):.1f} m")
        print(f"  Final position    : {result.get('final_position', {})}")
        print(f"  Video mode        : {result.get('video_mode', '—')}")
        if result.get("video_file"):
            print(f"  Video saved       : {result['video_file']}")
        print(f"  Events logged     : {len(result.get('trace', []))}")
        print(f"{BOLD}────────────────────────────────────────────{RESET}")


if __name__ == "__main__":
    asyncio.run(run_cli())
