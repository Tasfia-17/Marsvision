'use client'
import { useEffect, useRef, useState } from 'react'
import { getStatus, sendCommand, getHazards, getSessions, getSession } from '../lib/api'
import { getWsStreamUrl } from '../lib/config'
import type { RoverTelemetry, MissionEvent, Hazard, Session } from '../lib/types'
import MediaGallery from '../components/MediaGallery'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ── WebSocket Manager ─────────────────────────────────────────────────────────
class WS {
  private ws: WebSocket | null = null
  private onMsg: ((d: RoverTelemetry) => void) | null = null
  private onState: ((c: boolean) => void) | null = null
  private reconnect = false
  private url = ''
  connect(url: string) {
    this.reconnect = true; this.url = url
    if (this.ws) this.ws.close()
    this.ws = new WebSocket(url)
    this.ws.onopen = () => this.onState?.(true)
    this.ws.onmessage = e => { try { this.onMsg?.(JSON.parse(e.data)) } catch {} }
    this.ws.onclose = () => { this.onState?.(false); if (this.reconnect) setTimeout(() => this.connect(this.url), 2000) }
    this.ws.onerror = () => this.onState?.(false)
  }
  onMessage(cb: (d: RoverTelemetry) => void) { this.onMsg = cb }
  onStateChange(cb: (c: boolean) => void) { this.onState = cb }
  disconnect() { this.reconnect = false; this.ws?.close(); this.ws = null }
}

// ── Map ───────────────────────────────────────────────────────────────────────
function MapView({ telemetry, hazards, posHistory }: { telemetry: RoverTelemetry | null; hazards: Hazard[]; posHistory: {x:number;y:number}[] }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const rx = telemetry?.odometry?.x ?? telemetry?.position?.x ?? 0
  const ry = telemetry?.odometry?.y ?? telemetry?.position?.y ?? 0

  useEffect(() => {
    const c = ref.current; if (!c) return
    const ctx = c.getContext('2d')!
    const W = c.width, H = c.height
    ctx.fillStyle = '#3d2b1f'; ctx.fillRect(0, 0, W, H)
    const cx = W/2, cy = H/2
    const maxExt = Math.max(0.5, Math.abs(rx), Math.abs(ry),
      ...posHistory.map(p => Math.max(Math.abs(p.x), Math.abs(p.y))),
      ...hazards.map(h => Math.max(Math.abs(h.x), Math.abs(h.y))))
    const scale = Math.min(W,H)*0.42 / (maxExt*1.15)
    const toC = (x:number,y:number) => ({px: cx+x*scale, py: cy-y*scale})

    // Grid lines
    ctx.strokeStyle='rgba(255,255,255,0.07)'; ctx.lineWidth=1
    for(let i=-6;i<=6;i++){
      const s=Math.ceil(maxExt/5)
      const {px}=toC(i*s,0); const {py}=toC(0,i*s)
      ctx.beginPath();ctx.moveTo(px,0);ctx.lineTo(px,H);ctx.stroke()
      ctx.beginPath();ctx.moveTo(0,py);ctx.lineTo(W,py);ctx.stroke()
    }
    // Origin
    ctx.strokeStyle='rgba(255,255,255,0.3)'; ctx.lineWidth=1
    ctx.beginPath();ctx.moveTo(cx-12,cy);ctx.lineTo(cx+12,cy);ctx.moveTo(cx,cy-12);ctx.lineTo(cx,cy+12);ctx.stroke()

    // Path
    if(posHistory.length>=2){
      ctx.strokeStyle='rgba(251,191,36,0.55)'; ctx.lineWidth=1.5; ctx.beginPath()
      const p0=toC(posHistory[0].x,posHistory[0].y); ctx.moveTo(p0.px,p0.py)
      posHistory.forEach(p=>{const pt=toC(p.x,p.y);ctx.lineTo(pt.px,pt.py)}); ctx.stroke()
    }
    // Hazards
    ctx.strokeStyle='#ef4444'; ctx.lineWidth=2
    hazards.forEach(h=>{
      const {px,py}=toC(h.x,h.y); const s=6
      ctx.beginPath();ctx.moveTo(px-s,py-s);ctx.lineTo(px+s,py+s);ctx.moveTo(px+s,py-s);ctx.lineTo(px-s,py+s);ctx.stroke()
    })
    // Rover
    const rp=toC(rx,ry)
    ctx.fillStyle='#fbbf24'; ctx.beginPath(); ctx.arc(rp.px,rp.py,7,0,Math.PI*2); ctx.fill()
    ctx.strokeStyle='#fff'; ctx.lineWidth=1.5; ctx.stroke()
    ctx.fillStyle='rgba(251,191,36,0.9)'; ctx.font='11px monospace'
    ctx.fillText(`(${rx.toFixed(2)}, ${ry.toFixed(2)}) m`, rp.px+10, rp.py-6)
  }, [telemetry, hazards, posHistory, rx, ry])

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-lg p-4">
      <h3 className="text-amber-100 font-semibold mb-1">Map</h3>
      <div className="text-[11px] text-stone-400 mb-2 font-mono">
        Pos: {rx.toFixed(4)}, {ry.toFixed(4)} m
      </div>
      <canvas ref={ref} width={580} height={320} className="w-full rounded border border-stone-700" />
    </div>
  )
}

// ── Session Timeline ──────────────────────────────────────────────────────────
function SessionTimeline() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [expanded, setExpanded] = useState<string|null>(null)
  const [detail, setDetail] = useState<Session|null>(null)

  useEffect(() => {
    const refresh = async () => { try { const r=await getSessions(); setSessions(r.sessions) } catch {} }
    refresh(); const t=setInterval(refresh,4000); return ()=>clearInterval(t)
  }, [])

  useEffect(() => {
    if(!expanded) return
    const refresh = async () => { try { const s=await getSession(expanded); setDetail(s) } catch { setDetail(null) } }
    refresh(); const t=setInterval(refresh,4000); return ()=>clearInterval(t)
  }, [expanded])

  const toggle = async (id:string) => {
    if(expanded===id){setExpanded(null);setDetail(null);return}
    try{const s=await getSession(id);setDetail(s);setExpanded(id)}catch{setExpanded(null)}
  }

  const seen=new Set<string>(); const rows=sessions.filter(s=>{const id=String(s.session_id||'').trim();if(id&&seen.has(id))return false;if(id)seen.add(id);return true})

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-lg p-4">
      <h3 className="text-amber-100 font-semibold mb-3">Session Timeline</h3>
      <div className="space-y-2 font-mono text-sm max-h-48 overflow-y-auto">
        {rows.length===0 && <div className="text-stone-400 text-xs">No sessions yet</div>}
        {rows.map((s,i)=>(
          <div key={`${s.session_id}-${i}`} className="border border-stone-800 rounded p-2 cursor-pointer hover:bg-stone-800/50"
            onClick={()=>s.session_id&&toggle(s.session_id)}>
            <div className="flex justify-between text-amber-100">
              <span className="truncate">{(s.session_id||'unknown').slice(0,8)}...</span>
              <span className="text-stone-400 text-xs">{s.start_time?.slice(0,19)}</span>
            </div>
            <div className="text-stone-400 text-xs mt-1">dist: {(s.distance_traveled??0).toFixed(1)}m · hazards: {s.hazards_encountered??0}</div>
            {s.session_id&&expanded===s.session_id&&detail&&(
              <div className="mt-2 pt-2 border-t border-stone-700 text-stone-400 text-xs">
                <div>End: {detail.end_time||'—'}</div>
                <div>Summary: {detail.summary||'—'}</div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Rover Status ──────────────────────────────────────────────────────────────
function RoverStatus({t, ws}: {t:RoverTelemetry|null; ws:boolean}) {
  const x=t?.odometry?.x??t?.position?.x??0, y=t?.odometry?.y??t?.position?.y??0
  const speed=t?.odometry?.speed_ms??t?.velocity?.linear??0
  const yaw=t?.imu?.yaw_deg??(t?.orientation?.yaw??0)*180/Math.PI
  const dist=t?.odometry?.distance_from_origin_m??Math.sqrt(x*x+y*y)
  const uptime=t?.mission_elapsed_s??t?.uptime_seconds??0
  const sim=t?.sim_connected??true
  return (
    <div className="bg-stone-900 border border-stone-800 rounded-lg p-4">
      <h3 className="text-amber-100 font-semibold mb-3">Rover Status</h3>
      <div className="space-y-2 font-mono text-sm">
        <Row l="Position" v={`${x.toFixed(3)}, ${y.toFixed(3)}, 0`}/>
        <Row l="Speed" v={`${speed.toFixed(3)} m/s`}/>
        <Row l="Heading" v={`${yaw.toFixed(1)} deg`}/>
        <Row l="Uptime" v={`${uptime.toFixed(0)}s`}/>
        <Row l="From base" v={`${dist.toFixed(2)} m`}/>
        <Row l="Sol" v={t?.sol??'—'}/>
        <div className="flex items-center gap-2">
          <span className="text-stone-400">Stream</span>
          <span className={`w-2 h-2 rounded-full ${ws?'bg-emerald-500':'bg-red-500'}`}/>
          <span className={ws?'text-emerald-500':'text-red-500'}>{ws?'Connected':'Disconnected'}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-stone-400">Simulation</span>
          <span className={`w-2 h-2 rounded-full ${sim?'bg-emerald-500':'bg-red-500'}`}/>
          <span className={sim?'text-emerald-500':'text-red-500'}>{sim?'Connected':'Disconnected'}</span>
        </div>
      </div>
    </div>
  )
}

// ── Sensor Panel ──────────────────────────────────────────────────────────────
function SensorPanel({t}: {t:RoverTelemetry|null}) {
  const roll=t?.imu?.roll_deg??(t?.orientation?.roll??0)*180/Math.PI
  const pitch=t?.imu?.pitch_deg??(t?.orientation?.pitch??0)*180/Math.PI
  const yaw=t?.imu?.yaw_deg??(t?.orientation?.yaw??0)*180/Math.PI
  const lidar=t?.lidar?.min_distance_m
  const hazard=t?.hazard_detected??(lidar!==undefined&&lidar<1.5)
  const tc=(v:number)=>Math.abs(v)>20?'text-red-500':Math.abs(v)>12?'text-amber-500':'text-emerald-500'
  return (
    <div className="bg-stone-900 border border-stone-800 rounded-lg p-4">
      <h3 className="text-amber-100 font-semibold mb-3">Sensors</h3>
      <div className="space-y-2 font-mono text-sm">
        <Row l="Roll" v={<span className={tc(roll)}>{roll.toFixed(2)} deg</span>}/>
        <Row l="Pitch" v={<span className={tc(pitch)}>{pitch.toFixed(2)} deg</span>}/>
        <Row l="Yaw" v={`${yaw.toFixed(2)} deg`}/>
        <Row l="LIDAR min" v={lidar!==undefined?`${lidar.toFixed(2)} m`:'—'}/>
        <Row l="Battery" v={t?.battery_pct!==undefined?`${t.battery_pct}%`:'—'}/>
        <div className="flex items-center gap-2 mt-2">
          <span className={`px-2 py-0.5 rounded text-xs ${hazard?'bg-red-500/20 text-red-500':'bg-emerald-500/20 text-emerald-500'}`}>
            {hazard?'⚠ Hazard':'✓ Safe'}
          </span>
        </div>
      </div>
    </div>
  )
}

// ── Command Input ─────────────────────────────────────────────────────────────
function CommandInput({onMission}: {onMission:(g:string)=>void}) {
  const [text, setText] = useState('')
  const [history, setHistory] = useState<{text:string;resp:string}[]>([])
  const [loading, setLoading] = useState(false)

  const submit = async (goal:string) => {
    if(!goal.trim()||loading) return
    setLoading(true)
    try {
      const r = await sendCommand(goal.trim())
      setHistory(h=>[{text:goal.trim(),resp:r.response||r.goal||'Mission started'},  ...h].slice(0,5))
      setText(''); onMission(goal.trim())
    } catch(e) {
      setHistory(h=>[{text:goal.trim(),resp:String(e)},...h].slice(0,5))
    } finally { setLoading(false) }
  }

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-lg p-4">
      <h3 className="text-amber-100 font-semibold mb-3">Command</h3>
      <form onSubmit={e=>{e.preventDefault();submit(text)}} className="flex gap-2">
        <input value={text} onChange={e=>setText(e.target.value)}
          placeholder="Enter mission goal..."
          className="flex-1 bg-stone-800 border border-stone-700 rounded px-3 py-2 text-amber-100 placeholder-stone-500 text-sm focus:border-red-500 focus:outline-none"
          disabled={loading} suppressHydrationWarning/>
        <button type="submit" disabled={loading||!text.trim()}
          className="px-4 py-2 bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 disabled:opacity-40 text-sm font-medium"
          suppressHydrationWarning>
          {loading?'…':'Send'}
        </button>
      </form>
      {history.length>0&&(
        <div className="mt-3 space-y-2 font-mono text-sm">
          {history.map((h,i)=>(
            <div key={i} className="border-l-2 border-stone-700 pl-2">
              <div className="text-amber-100">{h.text}</div>
              <div className="text-stone-400 text-xs">{h.resp}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Video + Terrain Panel ─────────────────────────────────────────────────────
function VideoPanel({videoUrl, terrainUrl}: {videoUrl:string|null; terrainUrl:string|null}) {
  return (
    <div className="bg-stone-900 border border-stone-800 rounded-lg p-4">
      <h3 className="text-amber-100 font-semibold mb-3">🎬 Seedance 2.0 — Mission Footage</h3>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-[11px] text-stone-500 mb-1 font-mono">Seedream 5.0 Terrain Perception</p>
          {terrainUrl
            ? <img src={terrainUrl} alt="terrain" className="w-full rounded border border-stone-700 aspect-video object-cover"/>
            : <div className="aspect-video bg-stone-800 rounded border border-stone-700 flex items-center justify-center text-stone-600 text-xs">Awaiting terrain image...</div>}
        </div>
        <div>
          <p className="text-[11px] text-stone-500 mb-1 font-mono">Seedance 2.0 I2V Animation</p>
          {videoUrl
            ? <video src={videoUrl} controls autoPlay loop muted className="w-full rounded border border-orange-900 aspect-video object-cover"/>
            : <div className="aspect-video bg-stone-800 rounded border border-stone-700 flex items-center justify-center text-stone-600 text-xs">Awaiting video...</div>}
        </div>
      </div>
      {videoUrl&&<p className="text-[11px] text-stone-500 mt-2 text-center font-mono">Seedream 5.0 → Seedance 2.0 I2V pipeline</p>}
    </div>
  )
}

// ── Hazard Alert ──────────────────────────────────────────────────────────────
function HazardAlert({onDismiss}: {onDismiss:()=>void}) {
  return (
    <div className="mb-4 bg-red-500/10 border border-red-500/40 rounded-lg p-3 flex items-center justify-between">
      <span className="text-red-400 font-mono text-sm">⚠ HAZARD DETECTED — Rover stopped</span>
      <button onClick={onDismiss} className="text-stone-400 hover:text-white text-xs px-2 py-1 border border-stone-700 rounded">Dismiss</button>
    </div>
  )
}

// ── Helper ────────────────────────────────────────────────────────────────────
function Row({l,v}:{l:string;v:any}) {
  return <div className="flex justify-between"><span className="text-stone-400">{l}</span><span>{v}</span></div>
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [telemetry, setTelemetry] = useState<RoverTelemetry|null>(null)
  const [wsConnected, setWsConnected] = useState(false)
  const [hazards, setHazards] = useState<Hazard[]>([])
  const [posHistory, setPosHistory] = useState<{x:number;y:number}[]>([])
  const [hazardDismissed, setHazardDismissed] = useState(false)
  const [videoUrl, setVideoUrl] = useState<string|null>(null)
  const [terrainUrl, setTerrainUrl] = useState<string|null>(null)
  const wsRef = useRef<WS|null>(null)

  useEffect(() => {
    const push = (x:number,y:number) => setPosHistory(prev=>{
      const last=prev[prev.length-1]
      if(last&&Math.abs(last.x-x)<1e-4&&Math.abs(last.y-y)<1e-4) return prev
      return [...prev,{x,y}].slice(-500)
    })
    const ws=new WS(); wsRef.current=ws
    ws.onStateChange(setWsConnected)
    ws.onMessage(d=>{setTelemetry(d);if(d.position){push(d.position.x??0,d.position.y??0)}
      if(d.odometry){push(d.odometry.x,d.odometry.y)}})
    ws.connect(getWsStreamUrl())
    getStatus().then(d=>{setTelemetry(d);const x=d.odometry?.x??d.position?.x??0;const y=d.odometry?.y??d.position?.y??0;push(x,y)}).catch(()=>{})
    getHazards().then(r=>setHazards(r.hazards)).catch(()=>{})
    return ()=>{ws.disconnect();wsRef.current=null}
  }, [])

  // SSE for mission events + video
  useEffect(() => {
    const es=new EventSource(`${API}/mission/log/stream`)
    es.onmessage=e=>{
      const entry=JSON.parse(e.data)
      if(entry.event==='video_complete'||entry.event==='video_done'){
        setVideoUrl(`${API}/video/latest?t=${Date.now()}`)
        setTerrainUrl(`${API}/terrain/latest?t=${Date.now()}`)
      }
    }
    return ()=>es.close()
  }, [])

  const showHazard=!!telemetry?.hazard_detected&&!hazardDismissed

  return (
    <div className="min-h-screen bg-stone-950 text-amber-100 p-4">
      <header className="text-center mb-6">
        <h1 className="text-3xl font-bold tracking-wider text-red-400">MARSVISION — MISSION CONTROL</h1>
        <p className="text-sm text-stone-400 mt-1">Live Simulation Dashboard</p>
        <p className="text-xs text-stone-500 mt-0.5">Seedream 5.0 Perception · Seedance 2.0 I2V · Seed 2.0 Reasoning · IonRouter STT</p>
      </header>

      {showHazard&&<HazardAlert onDismiss={()=>setHazardDismissed(true)}/>}

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-8 space-y-4">
          <MapView telemetry={telemetry} hazards={hazards} posHistory={posHistory}/>
          <VideoPanel videoUrl={videoUrl} terrainUrl={terrainUrl}/>
          <MediaGallery/>
          <SessionTimeline/>
        </div>
        <div className="col-span-4 space-y-4">
          <RoverStatus t={telemetry} ws={wsConnected}/>
          <SensorPanel t={telemetry}/>
          <CommandInput onMission={()=>{}}/>
        </div>
      </div>
    </div>
  )
}
