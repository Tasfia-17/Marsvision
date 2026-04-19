import type { RoverTelemetry, CommandResponse } from './types'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export async function getStatus(): Promise<RoverTelemetry> {
  const r = await fetch(`${API}/telemetry`)
  if (!r.ok) throw new Error('telemetry failed')
  return r.json()
}

export async function sendCommand(text: string): Promise<CommandResponse> {
  const r = await fetch(`${API}/mission/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal: text }),
  })
  if (!r.ok) throw new Error('command failed')
  return r.json()
}

export async function getMissionLog(): Promise<{ log: any[] }> {
  const r = await fetch(`${API}/mission/log`)
  if (!r.ok) throw new Error('log failed')
  return r.json()
}

export async function getSessions(): Promise<{ sessions: any[] }> {
  try {
    const r = await fetch(`${API}/sessions`)
    if (!r.ok) return { sessions: [] }
    return r.json()
  } catch { return { sessions: [] } }
}

export async function getSession(id: string): Promise<any> {
  const r = await fetch(`${API}/sessions/${id}`)
  if (!r.ok) throw new Error('not found')
  return r.json()
}

export async function getSkills(): Promise<{ skills: any[] }> {
  return { skills: [] }
}

export async function getHazards(): Promise<{ hazards: any[] }> {
  try {
    const r = await fetch(`${API}/hazards`)
    if (!r.ok) return { hazards: [] }
    return r.json()
  } catch { return { hazards: [] } }
}
