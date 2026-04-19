'use client'
import { useEffect, useRef, useState } from 'react'
import { getStatus, sendCommand, getMissionLog, getHazards } from '../lib/api'
import type { RoverTelemetry, MissionEvent } from '../lib/types'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ── Map Canvas ────────────────────────────────────────────────────────────────
function MapView({ telemetry, posHistory, hazards }: {
  telemetry: RoverTelemetry | null
  posHistory: { x: number; y: number }[]
  hazards: any[]
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rx = telemetry?.odometry?.x ?? telemetry?.position?.x ?? 0
  const ry = telemetry?.odometry?.y ?? telemetry?.position?.y ?? 0

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    const W = canvas.width, H = canvas.height
    ctx.fillStyle = '#3d2b1f'
    ctx.fillRect(0, 0, W, H)
    const cx = W / 2, cy = H / 2

    const maxExt = Math.max(0.5,
      Math.abs(rx), Math.abs(ry),
      ...posHistory.map(p => Math.max(Math.abs(p.x), Math.abs(p.y))),
      ...hazards.map(h => Math.max(Math.abs(h.x ?? 0), Math.abs(h.y ?? 0)))
    )
    const scale = Math.min(W, H) * 0.42 / (maxExt * 1.15)
    const toC = (x: number, y: number) => ({ px: cx + x * scale, py: cy - y * scale })

    // Grid
    ctx.strokeStyle = 'rgba(255,255,255,0.08)'
    ctx.lineWidth = 1
    for (let i = -5; i <= 5; i++) {
      const { px } = toC(i * Math.ceil(maxExt / 5), 0)
      const { py } = toC(0, i * Math.ceil(maxExt / 5))
      ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, H); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(0, py); ctx.lineTo(W, py); ctx.stroke()
    }

    // Origin crosshair
    ctx.strokeStyle = 'rgba(255,255,255,0.25)'
    ctx.lineWidth = 1
    ctx.beginPath(); ctx.moveTo(cx - 12, cy); ctx.lineTo(cx + 12, cy)
    ctx.moveTo(cx, cy - 12); ctx.lineTo(cx, cy + 12); ctx.stroke()

    // Path trail
    if (posHistory.length >= 2) {
      ctx.strokeStyle = 'rgba(251,191,36,0.5)'
      ctx.lineWidth = 1.5
      ctx.beginPath()
      const p0 = toC(posHistory[0].x, posHistory[0].y)
      ctx.moveTo(p0.px, p0.py)
      posHistory.forEach(p => { const pt = toC(p.x, p.y); ctx.lineTo(pt.px, pt.py) })
      ctx.stroke()
    }

    // Hazard markers
    ctx.strokeStyle = '#ef4444'; ctx.lineWidth = 2
    hazards.forEach(h => {
      const { px, py } = toC(h.x ?? 0, h.y ?? 0)
      const s = 6
      ctx.beginPath()
      ctx.moveTo(px - s, py - s); ctx.lineTo(px + s, py + s)
      ctx.moveTo(px + s, py - s); ctx.lineTo(px - s, py + s)
      ctx.stroke()
    })

    // Rover dot
    const rp = toC(rx, ry)
    ctx.fillStyle = '#fbbf24'
    ctx.beginPath(); ctx.arc(rp.px, rp.py, 7, 0, Math.PI * 2); ctx.fill()
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.stroke()

    // Coords label
    ctx.fillStyle = 'rgba(251,191,36,0.8)'
    ctx.font = '11px monospace'
    ctx.fillText(`(${rx.toFixed(2)}, ${ry.toFixed(2)}) m`, rp.px + 10, rp.py - 6)
  }, [telemetry, posHistory, hazards, rx, ry])

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-lg p-4">
      <h3 className="text-amber-100 font-semibold mb-2">📍 Rover Map</h3>
      <canvas ref={canvasRef} width={580} height={320}
        className="w-full rounded border border-stone-700" />
    </div>
  )
}

// ── Sensor Panel ──────────────────────────────────────────────────────────────
function SensorPanel({ t }: { t: RoverTelemetry | null }) {
  const pitch = t?.imu?.pitch_deg ?? (t?.orientation?.pitch ?? 0) * 180 / Math.PI
  const roll = t?.imu?.roll_deg ?? (t?.orientation?.roll ?? 0) * 180 / Math.PI
  const yaw = t?.imu?.yaw_deg ?? (t?.orientation?.yaw ?? 0) * 180 / Math.PI
  const lidar = t?.lidar?.min_distance_m
  const hazard = t?.hazard_detected ?? (lidar !== undefined && lidar < 1.5)

  const tiltColor = (v: number) => Math.abs(v) > 20 ? 'text-red-500' : Math.abs(v) > 12 ? 'text-amber-500' : 'text-emerald-500'

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-lg p-4">
      <h3 className="text-amber-100 font-semibold mb-3">🔬 Sensors</h3>
      <div className="space-y-2 font-mono text-sm">
        <Row label="Roll" value={<span className={tiltColor(roll)}>{roll.toFixed(2)}°</span>} />
        <Row label="Pitch" value={<span className={tiltColor(pitch)}>{pitch.toFixed(2)}°</span>} />
        <Row label="Yaw" value={`${yaw.toFixed(2)}°`} />
        <Row label="LIDAR min" value={lidar !== undefined ? `${lidar.toFixed(2)} m` : '—'} />
        <Row label="Battery" value={t?.battery_pct !== undefined ? `${t.battery_pct}%` : '—'} />
        <div className="flex items-center gap-2 mt-2">
          <span className={`px-2 py-0.5 rounded text-xs font-bold ${hazard ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
            {hazard ? '⚠ HAZARD' : '✓ SAFE'}
          </span>
        </div>
      </div>
    </div>
  )
}

// ── Rover Status ──────────────────────────────────────────────────────────────
function RoverStatus({ t, connected }: { t: RoverTelemetry | null; connected: boolean }) {
  const x = t?.odometry?.x ?? t?.position?.x ?? 0
  const y = t?.odometry?.y ?? t?.position?.y ?? 0
  const speed = t?.odometry?.speed_ms ?? t?.velocity?.linear ?? 0
  const heading = t?.odometry?.heading_deg ?? (t?.orientation?.yaw ?? 0) * 180 / Math.PI
  const dist = t?.odometry?.distance_from_origin_m ?? Math.sqrt(x * x + y * y)
  const uptime = t?.mission_elapsed_s ?? t?.uptime_seconds ?? 0

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-lg p-4">
      <h3 className="text-amber-100 font-semibold mb-3">🛸 Rover Status</h3>
      <div className="space-y-2 font-mono text-sm">
        <Row label="Position" value={`${x.toFixed(3)}, ${y.toFixed(3)} m`} />
        <Row label="Speed" value={`${speed.toFixed(3)} m/s`} />
        <Row label="Heading" value={`${heading.toFixed(1)}°`} />
        <Row label="From base" value={`${dist.toFixed(2)} m`} />
        <Row label="Sol" value={t?.sol ?? '—'} />
        <Row label="Elapsed" value={`${uptime.toFixed(0)}s`} />
        <div className="flex items-center gap-2 mt-1">
          <span className="text-stone-400 text-sm">Stream</span>
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500' : 'bg-red-500'}`} />
          <span className={`text-sm ${connected ? 'text-emerald-400' : 'text-red-400'}`}>
            {connected ? 'Live' : 'Polling'}
          </span>
        </div>
      </div>
    </div>
  )
}

// ── Command Input ─────────────────────────────────────────────────────────────
function CommandInput({ onMission }: { onMission: (goal: string) => void }) {
  const [text, setText] = useState('')
  const [history, setHistory] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  const presets = [
    'Explore the crater rim and document findings',
    'Return to base safely',
    'Survey northern plains',
    'Check for hazards and report',
  ]

  async function submit(goal: string) {
    if (!goal.trim() || loading) return
    setLoading(true)
    try {
      await sendCommand(goal.trim())
      setHistory(h => [goal.trim(), ...h].slice(0, 5))
      setText('')
      onMission(goal.trim())
    } catch (e) {
      setHistory(h => [`ERROR: ${e}`, ...h].slice(0, 5))
    } finally { setLoading(false) }
  }

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-lg p-4">
      <h3 className="text-amber-100 font-semibold mb-3">🎯 Mission Command</h3>
      <form onSubmit={e => { e.preventDefault(); submit(text) }} className="flex gap-2">
        <input value={text} onChange={e => setText(e.target.value)}
          placeholder="Natural language mission goal..."
          className="flex-1 bg-stone-800 border border-stone-700 rounded px-3 py-2 text-amber-100 placeholder-stone-500 text-sm focus:border-red-500 focus:outline-none"
          disabled={loading} />
        <button type="submit" disabled={loading || !text.trim()}
          className="px-4 py-2 bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 disabled:opacity-40 text-sm font-bold">
          {loading ? '⏳' : '🚀'}
        </button>
      </form>
      <div className="mt-2 flex flex-wrap gap-1">
        {presets.map(p => (
          <button key={p} onClick={() => submit(p)}
            className="text-xs px-2 py-1 bg-stone-800 text-stone-400 rounded hover:text-amber-300 hover:bg-stone-700">
            {p.slice(0, 28)}…
          </button>
        ))}
      </div>
      {history.length > 0 && (
        <div className="mt-3 space-y-1 font-mono text-xs text-stone-400 border-t border-stone-800 pt-2">
          {history.map((h, i) => <div key={i} className="truncate">› {h}</div>)}
        </div>
      )}
    </div>
  )
}

// ── Mission Log ───────────────────────────────────────────────────────────────
function MissionLog({ events }: { events: MissionEvent[] }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { ref.current?.scrollTo(0, ref.current.scrollHeight) }, [events])

  const color = (e: string) => {
    if (e.includes('error') || e.includes('fail') || e.includes('halt')) return 'text-red-400'
    if (e.includes('video') || e.includes('complete')) return 'text-green-400'
    if (e.includes('reason') || e.includes('plan')) return 'text-blue-400'
    if (e.includes('navig') || e.includes('drive')) return 'text-yellow-400'
    return 'text-orange-300'
  }

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-lg p-4">
      <h3 className="text-amber-100 font-semibold mb-2">📋 Mission Log</h3>
      <div ref={ref} className="h-44 overflow-y-auto space-y-0.5 font-mono">
        {events.length === 0 && <p className="text-stone-500 text-xs">No events. Start a mission.</p>}
        {events.map((e, i) => (
          <div key={i} className="flex gap-2 text-xs">
            <span className="text-stone-600 shrink-0">{new Date(e.timestamp * 1000).toLocaleTimeString()}</span>
            <span className={`font-bold shrink-0 ${color(e.event)}`}>{e.event}</span>
            <span className="text-stone-400 truncate">{e.detail || ''}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Video + Terrain Panel ─────────────────────────────────────────────────────
function VideoPanel({ videoUrl, terrainUrl }: { videoUrl: string | null; terrainUrl: string | null }) {
  return (
    <div className="bg-stone-900 border border-stone-800 rounded-lg p-4">
      <h3 className="text-amber-100 font-semibold mb-3">🎬 Seedance 2.0 — Mission Footage</h3>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-xs text-stone-500 mb-1">Seedream 5.0 Terrain Perception</p>
          {terrainUrl
            ? <img src={terrainUrl} alt="terrain" className="w-full rounded border border-stone-700 aspect-video object-cover" />
            : <div className="aspect-video bg-stone-800 rounded border border-stone-700 flex items-center justify-center text-stone-600 text-xs">Awaiting terrain image...</div>
          }
        </div>
        <div>
          <p className="text-xs text-stone-500 mb-1">Seedance 2.0 I2V Animation</p>
          {videoUrl
            ? <video src={videoUrl} controls autoPlay loop muted className="w-full rounded border border-orange-900 aspect-video object-cover" />
            : <div className="aspect-video bg-stone-800 rounded border border-stone-700 flex items-center justify-center text-stone-600 text-xs">Awaiting video...</div>
          }
        </div>
      </div>
      {videoUrl && <p className="text-xs text-stone-500 mt-2 text-center">Pipeline: Seedream 5.0 → Seedance 2.0 I2V → Cinematic Mars footage</p>}
    </div>
  )
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function Row({ label, value }: { label: string; value: any }) {
  return (
    <div className="flex justify-between">
      <span className="text-stone-400">{label}</span>
      <span className="text-amber-100">{value}</span>
    </div>
  )
}

// ── Main Dashboard ────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [telemetry, setTelemetry] = useState<RoverTelemetry | null>(null)
  const [posHistory, setPosHistory] = useState<{ x: number; y: number }[]>([])
  const [hazards, setHazards] = useState<any[]>([])
  const [events, setEvents] = useState<MissionEvent[]>([])
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [terrainUrl, setTerrainUrl] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)

  // Poll telemetry every 2s
  useEffect(() => {
    const poll = async () => {
      try {
        const t = await getStatus()
        setTelemetry(t)
        setConnected(true)
        const x = t.odometry?.x ?? t.position?.x ?? 0
        const y = t.odometry?.y ?? t.position?.y ?? 0
        setPosHistory(prev => {
          const last = prev[prev.length - 1]
          if (last && Math.abs(last.x - x) < 0.001 && Math.abs(last.y - y) < 0.001) return prev
          return [...prev, { x, y }].slice(-500)
        })
      } catch { setConnected(false) }
    }
    poll()
    const id = setInterval(poll, 2000)
    return () => clearInterval(id)
  }, [])

  // SSE mission log
  useEffect(() => {
    const es = new EventSource(`${API}/mission/log/stream`)
    es.onmessage = e => {
      const entry = JSON.parse(e.data) as MissionEvent
      setEvents(prev => [...prev.slice(-199), entry])
      if (entry.event === 'video_complete' || entry.event === 'video_done') {
        setVideoUrl(`${API}/video/latest?t=${Date.now()}`)
        setTerrainUrl(`${API}/terrain/latest?t=${Date.now()}`)
      }
    }
    return () => es.close()
  }, [])

  // Load hazards once
  useEffect(() => {
    getHazards().then(r => setHazards(r.hazards)).catch(() => {})
  }, [])

  const onMission = (goal: string) => {
    setEvents(prev => [...prev, { timestamp: Date.now() / 1000, event: 'mission_start', detail: goal }])
  }

  return (
    <div className="min-h-screen bg-stone-950 text-amber-100 p-4">
      <header className="text-center mb-5">
        <h1 className="text-3xl font-bold tracking-wider text-red-400">
          MARSVISION — MISSION CONTROL
        </h1>
        <p className="text-sm text-stone-400 mt-1">
          Autonomous Mars Rover · Seedream 5.0 Perception · Seedance 2.0 I2V · Seed 2.0 Reasoning
        </p>
      </header>

      <div className="grid grid-cols-12 gap-4">
        {/* Left: Map + Mission Log + Video */}
        <div className="col-span-8 space-y-4">
          <MapView telemetry={telemetry} posHistory={posHistory} hazards={hazards} />
          <VideoPanel videoUrl={videoUrl} terrainUrl={terrainUrl} />
          <MissionLog events={events} />
        </div>

        {/* Right: Status + Sensors + Command */}
        <div className="col-span-4 space-y-4">
          <RoverStatus t={telemetry} connected={connected} />
          <SensorPanel t={telemetry} />
          <CommandInput onMission={onMission} />
        </div>
      </div>
    </div>
  )
}
// Mission control dashboard
