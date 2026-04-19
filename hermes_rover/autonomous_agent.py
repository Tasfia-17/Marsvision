"""
MarsVision Autonomous Mission Agent.
Real agentic loop: sense → reason → act → learn → report.
Uses OpenRouter (free model) for reasoning. Shows thinking trace.
No Gazebo required — works with mock bridge.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bridge.mock_sensors import get_snapshot, drive, navigate_to, get_state_for_video
from hermes_rover.tools.scene_video_tool import execute as gen_video
from hermes_rover.memory import memory_manager as _mm

_OR_KEY = os.getenv("OPENROUTER_API_KEY", "")
_OR_MODEL = "google/gemini-2.0-flash-exp:free"  # free, no cost
_OR_URL = "https://openrouter.ai/api/v1/chat/completions"

class _Memory:
    def save_behavior(self, context, strategy, outcome, confidence):
        try: _mm.log_learned_behavior(trigger=context, action=strategy)
        except Exception: pass

memory = _Memory()
_trace: list[dict] = []  # visible reasoning trace for dashboard


def _log(phase: str, detail: str, data: dict = {}):
    entry = {"time": time.time(), "phase": phase, "detail": detail, **data}
    _trace.append(entry)
    print(f"[{phase.upper()}] {detail}")
    return entry


async def _reason(system: str, user: str) -> str:
    """Single LLM call for reasoning. Uses free OpenRouter model."""
    if not _OR_KEY:
        return "proceed"  # no key — use default behavior
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            _OR_URL,
            headers={"Authorization": f"Bearer {_OR_KEY}", "Content-Type": "application/json"},
            json={
                "model": _OR_MODEL,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "max_tokens": 200,
            },
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    return "proceed"


async def run_mission(goal: str, on_event=None) -> dict:
    """
    Full autonomous mission loop.
    on_event(phase, detail, data) called for each step — used by API for SSE.
    """
    _trace.clear()

    def emit(phase, detail, data={}):
        entry = _log(phase, detail, data)
        if on_event:
            on_event(phase, detail, data)
        return entry

    emit("mission_start", f"Goal: {goal}", {"goal": goal})

    # ── Phase 1: SENSE ────────────────────────────────────────────────────
    emit("sensing", "Reading all sensors...")
    snap = get_snapshot()
    state = get_state_for_video()
    tilt = snap["imu"]["pitch_deg"]
    lidar = snap["lidar"]["min_distance_m"]
    pos = snap["odometry"]

    emit("sensing", f"Position ({pos['x']:.2f}, {pos['y']:.2f})m | Tilt {tilt:.1f}° | LIDAR {lidar:.1f}m", {
        "position": state["position"], "tilt": tilt, "lidar": lidar
    })

    # ── Phase 2: SAFETY CHECK ─────────────────────────────────────────────
    if abs(tilt) > 25:
        emit("safety_halt", f"TILT {tilt:.1f}° exceeds 25° limit — mission aborted")
        return {"success": False, "reason": "tilt_limit"}

    if lidar < 1.0:
        emit("safety_halt", f"Obstacle {lidar:.1f}m — too close, replanning")
        drive(-0.3, 0, 2.0)  # back up
        emit("replan", "Backed up 0.6m, resuming")

    # ── Phase 3: REASON (1 LLM call — minimal OpenRouter usage) ──────────
    emit("reasoning", "Planning mission route...")
    plan_response = await _reason(
        system="You are a Mars rover mission planner. Reply with JSON only: {\"target_x\": float, \"target_y\": float, \"scene\": str}",
        user=f"Goal: '{goal}'. Current position: ({pos['x']:.1f}, {pos['y']:.1f}). "
             f"LIDAR min: {lidar:.1f}m. Tilt: {tilt:.1f}°. "
             f"Reply with target coordinates and scene description for Seedance video."
    )

    # Parse plan or use defaults
    try:
        plan = json.loads(plan_response)
        tx, ty = float(plan["target_x"]), float(plan["target_y"])
        scene = plan.get("scene", goal)
    except Exception:
        # Fallback plan based on keywords
        if "crater" in goal.lower():
            tx, ty, scene = 15.0, 8.0, "approaching crater rim, rocky elevated terrain"
        elif "return" in goal.lower() or "base" in goal.lower():
            tx, ty, scene = 0.0, 0.0, "returning to base, flat terrain, rover tracks visible"
        elif "north" in goal.lower():
            tx, ty, scene = 0.0, 20.0, "northward traverse, open Mars plains"
        else:
            tx, ty, scene = 10.0, 5.0, "exploring unknown Mars terrain"

    emit("plan", f"Target: ({tx}, {ty})m | Scene: {scene}", {"target": {"x": tx, "y": ty}, "scene": scene})

    # ── Phase 4: ACT — Navigate ───────────────────────────────────────────
    emit("navigating", f"Driving to ({tx:.1f}, {ty:.1f})m...")
    nav_result = navigate_to(tx, ty)
    emit("navigating", f"Arrived. Distance: {nav_result['distance_traveled_m']:.1f}m | Accuracy: {nav_result['accuracy_cm']:.0f}cm", nav_result)

    # ── Phase 5: RE-SENSE at destination ─────────────────────────────────
    snap2 = get_snapshot()
    state2 = get_state_for_video()
    emit("sensing", f"At destination: pos={state2['position']} heading={state2['heading_deg']}°")

    # ── Phase 6: GENERATE VIDEO (Seedance 2.0) ────────────────────────────
    emit("generating_video", f"Calling Seedance 2.0... scene: '{scene}'")
    video_result = json.loads(await gen_video(scene_context=scene, duration=5))

    if video_result["success"]:
        size_kb = os.path.getsize(video_result["file_path"]) // 1024
        emit("video_complete", f"Video ready: {size_kb}KB | Mode: {video_result.get('mode','t2v')}", {
            "file_path": video_result["file_path"],
            "mode": video_result.get("mode"),
            "size_kb": size_kb,
        })
    else:
        emit("video_error", f"Video failed: {video_result.get('error')}")

    # ── Phase 7: LEARN — Save behavior to memory ──────────────────────────
    try:
        memory.save_behavior(
            context=goal,
            strategy=f"navigate_to({tx},{ty}) then generate_scene_video",
            outcome="success" if video_result["success"] else "partial",
            confidence=0.85,
        )
        emit("learning", f"Saved behavior to memory for future missions")
    except Exception:
        pass

    # ── Phase 8: REPORT ───────────────────────────────────────────────────
    report = {
        "goal": goal,
        "distance_traveled_m": round(nav_result["distance_traveled_m"], 2),
        "final_position": state2["position"],
        "video_file": video_result.get("file_path"),
        "video_mode": video_result.get("mode"),
        "mission_elapsed_s": round(state2["mission_elapsed_s"], 1),
        "trace": _trace,
    }
    emit("mission_complete", f"Mission done. {len(_trace)} events logged.", report)
    return report


def get_trace() -> list[dict]:
    return _trace
# Autonomous agent loop
