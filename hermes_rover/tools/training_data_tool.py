"""
Generate robot training data from mission telemetry + Seedance videos.
Exports behavior cloning dataset: {observation, action, outcome} pairs.
This is what makes MarsVision a Physical AI training data generator.
"""
import json
import os
import time
from pathlib import Path

TOOL_SCHEMA = {
    "name": "generate_training_data",
    "description": (
        "Export mission telemetry and generated videos as a structured robot training dataset. "
        "Produces behavior cloning data: (observation, action, outcome) pairs that can train "
        "robot policies using BC, DAgger, or IQL frameworks."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "mission_trace": {"type": "array", "description": "List of mission events from the agent loop."},
            "video_path": {"type": "string", "description": "Path to the generated Seedance video."},
            "outcome": {"type": "string", "enum": ["success", "failure", "partial"], "default": "success"},
        },
        "required": ["mission_trace"],
    },
}

_DATASET_DIR = Path("~/marsvision_dataset").expanduser()


async def execute(*, mission_trace: list, video_path: str = "", outcome: str = "success", **_) -> str:
    _DATASET_DIR.mkdir(parents=True, exist_ok=True)
    episode_id = f"episode_{int(time.time())}"

    # Extract structured steps from trace
    steps = []
    for event in mission_trace:
        phase = event.get("phase", event.get("event", ""))
        if phase == "sensing":
            steps.append({
                "type": "observation",
                "position": event.get("position"),
                "tilt_deg": event.get("tilt"),
                "lidar_min_m": event.get("lidar"),
                "timestamp": event.get("time", event.get("timestamp")),
            })
        elif phase in ("navigating", "drive"):
            steps.append({
                "type": "action",
                "action_type": "navigate",
                "target": event.get("target"),
                "distance_m": event.get("distance_traveled_m"),
                "timestamp": event.get("time", event.get("timestamp")),
            })
        elif phase == "safety_halt":
            steps.append({
                "type": "action",
                "action_type": "halt",
                "reason": event.get("detail"),
                "timestamp": event.get("time", event.get("timestamp")),
            })
        elif phase == "video_complete":
            steps.append({
                "type": "observation",
                "modality": "video",
                "video_path": event.get("file_path", video_path),
                "video_mode": event.get("mode"),
                "timestamp": event.get("time", event.get("timestamp")),
            })

    episode = {
        "episode_id": episode_id,
        "outcome": outcome,
        "total_steps": len(steps),
        "video_path": video_path,
        "steps": steps,
        "metadata": {
            "environment": "Mars terrain simulation",
            "gravity_ms2": 3.721,
            "generated_at": time.time(),
            "format": "behavior_cloning",
            "compatible_with": ["BC", "DAgger", "IQL", "ACT"],
        },
    }

    # Save episode JSON
    ep_path = _DATASET_DIR / f"{episode_id}.json"
    ep_path.write_text(json.dumps(episode, indent=2))

    # Update dataset index
    index_path = _DATASET_DIR / "dataset_index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {"episodes": [], "total": 0}
    index["episodes"].append({"id": episode_id, "outcome": outcome, "steps": len(steps), "path": str(ep_path)})
    index["total"] = len(index["episodes"])
    index_path.write_text(json.dumps(index, indent=2))

    return json.dumps({
        "success": True,
        "episode_id": episode_id,
        "dataset_path": str(_DATASET_DIR),
        "steps_exported": len(steps),
        "total_episodes": index["total"],
        "message": f"Training episode saved. Dataset now has {index['total']} episodes.",
    })
