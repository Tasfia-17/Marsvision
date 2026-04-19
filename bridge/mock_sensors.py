"""
Mock Gazebo sensor bridge for development without Gazebo installed.
Simulates realistic Mars rover telemetry: IMU, odometry, LIDAR, cameras.
Drop-in replacement — real bridge uses same data shapes.
"""
import asyncio
import json
import math
import random
import time
from dataclasses import dataclass, field, asdict


@dataclass
class RoverState:
    x: float = 0.0
    y: float = 0.0
    heading_deg: float = 0.0
    speed: float = 0.0
    tilt_deg: float = 0.0
    lidar_min_m: float = 8.5
    battery_pct: float = 94.0
    sol: int = 127
    mission_elapsed_s: float = 0.0
    hazards: list = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)


_state = RoverState()
_start_time = time.time()


def _noise(scale=0.05):
    return random.gauss(0, scale)


def get_imu() -> dict:
    return {
        "roll_deg": _noise(0.3),
        "pitch_deg": _state.tilt_deg + _noise(0.2),
        "yaw_deg": _state.heading_deg + _noise(0.1),
        "accel_x": _noise(0.01),
        "accel_y": _noise(0.01),
        "accel_z": -3.721 + _noise(0.005),  # Mars gravity
        "timestamp": time.time(),
    }


def get_odometry() -> dict:
    return {
        "x": _state.x + _noise(0.01),
        "y": _state.y + _noise(0.01),
        "heading_deg": _state.heading_deg,
        "speed_ms": _state.speed,
        "distance_from_origin_m": math.sqrt(_state.x**2 + _state.y**2),
        "timestamp": time.time(),
    }


def get_lidar() -> dict:
    readings = []
    for angle in range(0, 360, 10):
        base = _state.lidar_min_m if abs(angle) < 30 else random.uniform(3.0, 12.0)
        readings.append({"angle_deg": angle, "distance_m": base + _noise(0.1)})
    return {
        "min_distance_m": _state.lidar_min_m,
        "readings": readings,
        "timestamp": time.time(),
    }


def get_snapshot() -> dict:
    elapsed = time.time() - _start_time
    _state.mission_elapsed_s = elapsed
    # Slowly drift position to simulate movement
    _state.x += math.cos(math.radians(_state.heading_deg)) * _state.speed * 0.1
    _state.y += math.sin(math.radians(_state.heading_deg)) * _state.speed * 0.1
    _state.tilt_deg = 2.1 + _noise(0.3)
    _state.lidar_min_m = max(1.5, 8.5 + _noise(0.5))

    return {
        "imu": get_imu(),
        "odometry": get_odometry(),
        "lidar": get_lidar(),
        "battery_pct": _state.battery_pct,
        "sol": _state.sol,
        "mission_elapsed_s": elapsed,
        "hazards": _state.hazards,
        "timestamp": time.time(),
    }


def drive(linear_ms: float, angular_rads: float, duration_s: float) -> dict:
    _state.speed = min(abs(linear_ms), 1.0) * (1 if linear_ms >= 0 else -1)
    _state.heading_deg = (_state.heading_deg + math.degrees(angular_rads) * duration_s) % 360
    _state.x += math.cos(math.radians(_state.heading_deg)) * _state.speed * duration_s
    _state.y += math.sin(math.radians(_state.heading_deg)) * _state.speed * duration_s
    _state.speed = 0.0
    return {"success": True, "new_position": {"x": _state.x, "y": _state.y}, "heading_deg": _state.heading_deg}


def navigate_to(target_x: float, target_y: float) -> dict:
    dx = target_x - _state.x
    dy = target_y - _state.y
    dist = math.sqrt(dx**2 + dy**2)
    _state.heading_deg = math.degrees(math.atan2(dy, dx)) % 360
    _state.x = target_x + _noise(0.1)
    _state.y = target_y + _noise(0.1)
    return {
        "success": True,
        "distance_traveled_m": dist,
        "final_position": {"x": _state.x, "y": _state.y},
        "heading_deg": _state.heading_deg,
        "accuracy_cm": abs(_noise(5)) * 100,
    }


def get_state_for_video() -> dict:
    """Returns telemetry dict for Seedance prompt generation."""
    return {
        "position": {"x": round(_state.x, 2), "y": round(_state.y, 2)},
        "heading_deg": round(_state.heading_deg, 1),
        "tilt_deg": round(_state.tilt_deg, 1),
        "lidar_min_m": round(_state.lidar_min_m, 1),
        "battery_pct": _state.battery_pct,
        "sol": _state.sol,
        "mission_elapsed_s": round(_state.mission_elapsed_s, 1),
        "distance_from_origin_m": round(math.sqrt(_state.x**2 + _state.y**2), 2),
    }
# MarsVision Physics Bridge v1.0
