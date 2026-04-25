"""
MarsVision Physical AI Training Data Generator.

Exports mission telemetry + Seedance videos as structured robot training datasets.

Format: RLDS-compatible (Open X-Embodiment standard)
  - Each episode = one autonomous mission
  - Each step = {observation, action, reward, is_terminal, language_instruction}
  - Observations include: image (Seedream frame), state vector (IMU/LIDAR/odometry)
  - Actions: continuous 6-DOF (dx, dy, dz, roll, pitch, yaw) + discrete (halt, sample)
  - Reward: +1.0 success, -1.0 failure, 0.0 intermediate
  - Compatible with: BC, DAgger, IQL, ACT, RT-2, OpenVLA

Pipeline mirrors NVIDIA DreamGen:
  Stage 1 — Generate video from telemetry (Seedream 5.0 → Seedance 2.0)
  Stage 2 — Extract pseudo-actions via finite-difference inverse dynamics
  Stage 3 — Annotate with language instructions and reward signals
  Stage 4 — Export as RLDS-compatible JSON + dataset index

Run 100 missions → 100 labeled episodes → train a robot policy.
"""
import json
import math
import os
import time
from pathlib import Path

TOOL_SCHEMA = {
    "name": "generate_training_data",
    "description": (
        "Export mission telemetry and generated videos as an RLDS-compatible robot "
        "training dataset. Produces behavior cloning data with continuous action vectors, "
        "reward signals, and language instructions. Compatible with BC, DAgger, IQL, ACT, "
        "RT-2, and OpenVLA training frameworks."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "mission_trace": {"type": "array", "description": "List of mission events from the agent loop."},
            "video_path": {"type": "string", "description": "Path to the generated Seedance video."},
            "outcome": {"type": "string", "enum": ["success", "failure", "partial"], "default": "success"},
            "language_instruction": {"type": "string", "description": "Natural language goal for this episode."},
        },
        "required": ["mission_trace"],
    },
}

_DATASET_DIR = Path("~/marsvision_dataset").expanduser()

# Mars gravity constant
_GRAVITY = 3.721  # m/s²


def _extract_action_vector(prev_obs: dict | None, curr_obs: dict | None) -> list[float]:
    """
    Pseudo-action extraction via finite-difference inverse dynamics.
    Mirrors DreamGen Stage 2: infer actions from consecutive observation pairs.
    Returns 6-DOF action vector: [dx, dy, dz, d_roll, d_pitch, d_yaw]
    """
    if prev_obs is None or curr_obs is None:
        return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    px = prev_obs.get("position", {})
    cx = curr_obs.get("position", {})
    dx = cx.get("x", 0.0) - px.get("x", 0.0)
    dy = cx.get("y", 0.0) - px.get("y", 0.0)
    dz = cx.get("z", 0.0) - px.get("z", 0.0)

    d_roll  = curr_obs.get("roll_deg",  0.0) - prev_obs.get("roll_deg",  0.0)
    d_pitch = curr_obs.get("tilt_deg",  0.0) - prev_obs.get("tilt_deg",  0.0)
    d_yaw   = curr_obs.get("heading_deg", 0.0) - prev_obs.get("heading_deg", 0.0)
    # Normalize yaw delta to [-180, 180]
    if d_yaw > 180:  d_yaw -= 360
    if d_yaw < -180: d_yaw += 360

    return [round(dx, 4), round(dy, 4), round(dz, 4),
            round(d_roll, 3), round(d_pitch, 3), round(d_yaw, 3)]


def _compute_reward(phase: str, outcome: str, lidar: float, tilt: float) -> float:
    """
    Reward shaping:
      +1.0  mission success terminal
      -1.0  safety halt / failure terminal
      +0.3  video generated (perception milestone)
      +0.1  navigation step completed
      -0.2  hazard proximity (lidar < 2m)
      -0.3  dangerous tilt (> 20 deg)
    """
    if phase == "mission_complete":
        return 1.0 if outcome == "success" else -0.5
    if phase == "safety_halt":
        return -1.0
    if phase == "video_complete":
        return 0.3
    if phase in ("navigating",):
        r = 0.1
        if lidar < 2.0: r -= 0.2
        if tilt > 20:   r -= 0.3
        return round(r, 2)
    return 0.0


def _build_state_vector(obs: dict) -> list[float]:
    """
    Compact state vector for policy input:
    [x, y, heading_deg, tilt_deg, lidar_min_m, battery_pct, distance_from_origin_m]
    """
    pos = obs.get("position", {})
    return [
        round(pos.get("x", 0.0), 4),
        round(pos.get("y", 0.0), 4),
        round(obs.get("heading_deg", 0.0), 2),
        round(obs.get("tilt_deg", 0.0), 2),
        round(obs.get("lidar_min_m", 10.0), 3),
        round(obs.get("battery_pct", 100.0), 1),
        round(obs.get("distance_from_origin_m", 0.0), 3),
    ]


async def execute(
    *,
    mission_trace: list,
    video_path: str = "",
    outcome: str = "success",
    language_instruction: str = "",
    **_,
) -> str:
    _DATASET_DIR.mkdir(parents=True, exist_ok=True)
    episode_id = f"episode_{int(time.time())}"

    # ── Stage 1: Parse trace into raw observations ──────────────────────────
    raw_obs: list[dict] = []
    for event in mission_trace:
        phase = event.get("phase", event.get("event", ""))
        if phase == "sensing":
            raw_obs.append({
                "phase": phase,
                "position": event.get("position", {}),
                "heading_deg": event.get("heading", 0.0),
                "tilt_deg": event.get("tilt", 0.0),
                "lidar_min_m": event.get("lidar", 10.0),
                "battery_pct": event.get("battery", 100.0),
                "distance_from_origin_m": event.get("distance", 0.0),
                "timestamp": event.get("time", event.get("timestamp", time.time())),
            })

    # ── Stage 2: Pseudo-action extraction (finite-difference inverse dynamics) ──
    steps = []
    prev_obs_raw = None

    for event in mission_trace:
        phase = event.get("phase", event.get("event", ""))
        lidar = event.get("lidar", 10.0)
        tilt  = event.get("tilt", 0.0)

        if phase == "sensing":
            curr_obs_raw = {
                "position": event.get("position", {}),
                "heading_deg": event.get("heading", 0.0),
                "tilt_deg": tilt,
                "lidar_min_m": lidar,
                "battery_pct": event.get("battery", 100.0),
                "distance_from_origin_m": event.get("distance", 0.0),
            }
            action_vec = _extract_action_vector(prev_obs_raw, curr_obs_raw)
            reward = _compute_reward(phase, outcome, lidar, tilt)
            steps.append({
                "observation": {
                    "state": _build_state_vector(curr_obs_raw),
                    "image_path": event.get("image_path"),   # Seedream frame if captured
                    "raw": curr_obs_raw,
                },
                "action": {
                    "type": "continuous",
                    "vector_6dof": action_vec,   # [dx, dy, dz, d_roll, d_pitch, d_yaw]
                    "description": "inferred via finite-difference inverse dynamics",
                },
                "reward": reward,
                "is_terminal": False,
                "language_instruction": language_instruction,
                "phase": phase,
                "timestamp": event.get("time", event.get("timestamp")),
            })
            prev_obs_raw = curr_obs_raw

        elif phase in ("navigating", "drive"):
            target = event.get("target", {})
            steps.append({
                "observation": {"state": _build_state_vector(prev_obs_raw or {})},
                "action": {
                    "type": "discrete",
                    "action_type": "navigate",
                    "target_x": target.get("x", 0.0),
                    "target_y": target.get("y", 0.0),
                    "distance_m": event.get("distance_traveled_m", 0.0),
                },
                "reward": _compute_reward(phase, outcome, lidar, tilt),
                "is_terminal": False,
                "language_instruction": language_instruction,
                "phase": phase,
                "timestamp": event.get("time", event.get("timestamp")),
            })

        elif phase == "safety_halt":
            steps.append({
                "observation": {"state": _build_state_vector(prev_obs_raw or {})},
                "action": {"type": "discrete", "action_type": "halt", "reason": event.get("detail")},
                "reward": _compute_reward(phase, outcome, lidar, tilt),
                "is_terminal": True,
                "language_instruction": language_instruction,
                "phase": phase,
                "timestamp": event.get("time", event.get("timestamp")),
            })

        elif phase == "video_complete":
            steps.append({
                "observation": {
                    "state": _build_state_vector(prev_obs_raw or {}),
                    "video_path": event.get("file_path", video_path),
                    "video_mode": event.get("mode"),
                    "reference_frames": event.get("reference_frames", 1),
                },
                "action": {"type": "perception", "action_type": "generate_video"},
                "reward": _compute_reward(phase, outcome, lidar, tilt),
                "is_terminal": False,
                "language_instruction": language_instruction,
                "phase": phase,
                "timestamp": event.get("time", event.get("timestamp")),
            })

        elif phase == "mission_complete":
            steps.append({
                "observation": {"state": _build_state_vector(prev_obs_raw or {})},
                "action": {"type": "terminal"},
                "reward": _compute_reward(phase, outcome, lidar, tilt),
                "is_terminal": True,
                "language_instruction": language_instruction,
                "phase": phase,
                "timestamp": event.get("time", event.get("timestamp")),
            })

    # ── Stage 3: Annotate episode ────────────────────────────────────────────
    total_distance = sum(
        s["action"].get("distance_m", 0.0)
        for s in steps if s["action"].get("action_type") == "navigate"
    )
    terminal_reward = next(
        (s["reward"] for s in reversed(steps) if s["is_terminal"]), 0.0
    )
    cumulative_reward = round(sum(s["reward"] for s in steps), 3)

    # ── Stage 4: RLDS-compatible episode export ──────────────────────────────
    episode = {
        # RLDS standard fields
        "episode_id": episode_id,
        "language_instruction": language_instruction,
        "steps": steps,
        # Episode-level metadata
        "metadata": {
            "environment": "Mars terrain simulation",
            "gravity_ms2": _GRAVITY,
            "generated_at": time.time(),
            "outcome": outcome,
            "total_steps": len(steps),
            "total_distance_m": round(total_distance, 3),
            "cumulative_reward": cumulative_reward,
            "terminal_reward": terminal_reward,
            "video_path": video_path,
            # Dataset compatibility
            "format": "RLDS_compatible",
            "action_space": "6dof_continuous_plus_discrete",
            "observation_space": "state_vector_7d_plus_image",
            "compatible_with": ["BC", "DAgger", "IQL", "ACT", "RT-2", "OpenVLA"],
            "pipeline": "MarsVision → Seedream5.0 → Seedance2.0 → RLDS",
        },
    }

    # Save episode
    ep_path = _DATASET_DIR / f"{episode_id}.json"
    ep_path.write_text(json.dumps(episode, indent=2))

    # Update dataset index with aggregate stats
    index_path = _DATASET_DIR / "dataset_index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {
        "episodes": [], "total": 0, "stats": {
            "success": 0, "failure": 0, "partial": 0,
            "total_distance_m": 0.0, "total_steps": 0,
        }
    }
    index["episodes"].append({
        "id": episode_id,
        "outcome": outcome,
        "steps": len(steps),
        "distance_m": round(total_distance, 3),
        "cumulative_reward": cumulative_reward,
        "path": str(ep_path),
    })
    index["total"] = len(index["episodes"])
    index["stats"][outcome] = index["stats"].get(outcome, 0) + 1
    index["stats"]["total_distance_m"] = round(
        index["stats"].get("total_distance_m", 0.0) + total_distance, 3
    )
    index["stats"]["total_steps"] += len(steps)
    index_path.write_text(json.dumps(index, indent=2))

    return json.dumps({
        "success": True,
        "episode_id": episode_id,
        "dataset_path": str(_DATASET_DIR),
        "steps_exported": len(steps),
        "total_episodes": index["total"],
        "cumulative_reward": cumulative_reward,
        "format": "RLDS_compatible",
        "message": (
            f"Training episode saved ({outcome}). "
            f"Dataset: {index['total']} episodes, "
            f"{index['stats']['total_steps']} total steps, "
            f"{index['stats']['total_distance_m']}m traversed."
        ),
    })
