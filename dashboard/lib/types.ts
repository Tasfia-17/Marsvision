export interface RoverTelemetry {
  position?: { x: number; y: number; z?: number };
  orientation?: { roll: number; pitch: number; yaw: number };
  velocity?: { linear: number; angular: number };
  hazard_detected?: boolean;
  uptime_seconds?: number;
  sim_connected?: boolean;
  imu?: { pitch_deg: number; roll_deg?: number; yaw_deg: number; accel_z?: number };
  odometry?: { x: number; y: number; heading_deg: number; speed_ms: number; distance_from_origin_m: number };
  lidar?: { min_distance_m: number };
  battery_pct?: number;
  sol?: number;
  mission_elapsed_s?: number;
  hazards?: any[];
}

export interface Hazard {
  id?: number;
  x: number;
  y: number;
  hazard_type?: string;
  severity?: string;
  description?: string;
}

export interface MissionEvent {
  timestamp: number;
  event: string;
  detail?: string;
  [key: string]: any;
}

export interface CommandResponse {
  response?: string;
  status?: string;
  goal?: string;
}

export interface Session {
  id?: number;
  session_id?: string;
  start_time?: string;
  end_time?: string;
  distance_traveled?: number;
  hazards_encountered?: number;
  skills_used?: string;
  summary?: string;
}
