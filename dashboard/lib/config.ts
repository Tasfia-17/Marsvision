const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function getApiBaseUrl() { return API_BASE }
export function getWsStreamUrl() { return API_BASE.replace('http', 'ws') + '/ws/telemetry' }
