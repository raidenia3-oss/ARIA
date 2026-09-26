import React, { useState, useEffect } from 'react'
import { Activity, Cpu, HardDrive, Wifi } from 'lucide-react'

function fallbackTelemetry() {
  return {
    cpu: { percent: 0 },
    memory: { used: 0, total: 0 },
    system: { temp: 0 },
    swarm: { active_agents: 0, active_tasks: 0, health: 0 },
    disk: { used: 0, total: 0, io_ops: 0 },
    network: { sent: 0, recv: 0, latency: 0 },
  }
}

export default function Telemetry({ data: externalData, theme }) {
  const [data, setData] = useState(externalData || fallbackTelemetry())

  useEffect(() => {
    if (externalData) {
      setData(externalData)
      return
    }

    let cancelled = false
    const load = async () => {
      try {
        const res = await fetch('/api/system/telemetry')
        if (!res.ok) return
        const json = await res.json()
        if (!cancelled) setData(json)
      } catch (e) {
        console.error('[telemetry] load failed', e)
      }
    }

    load()
    const interval = setInterval(load, 5000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [externalData])

  const cpu = data?.cpu?.percent ?? data?.cpu_usage ?? 0
  const memoryUsed = data?.memory?.used ?? data?.ram_used ?? 0
  const memoryTotal = data?.memory?.total ?? data?.ram_total ?? (memoryUsed || 1)
  const temp = data?.system?.temp ?? 0
  const agents = data?.swarm?.active_agents ?? data?.active_agents ?? 0
  const tasks = data?.swarm?.active_tasks ?? data?.active_tasks ?? 0
  const health = data?.swarm?.health ?? data?.health ?? 0
  const diskUsed = data?.disk?.used ?? data?.disk_used ?? 0
  const diskTotal = data?.disk?.total ?? data?.disk_total ?? (diskUsed || 1)
  const ioOps = data?.disk?.io_ops ?? data?.io_ops ?? 0
  const sent = data?.network?.sent ?? data?.network_sent ?? 0
  const recv = data?.network?.recv ?? data?.network_recv ?? 0
  const latency = data?.network?.latency ?? data?.network_latency ?? 0

  return (
    <div className="telemetry glass">
      <div className="telemetry-header">TELEMETRY</div>

      <div className="telemetry-section">
        <h4>
          <Cpu size={14} /> SYSTEM
        </h4>
        <div className="stat-item">
          <span>CPU</span>
          <span className="value">{cpu?.toFixed(1)}%</span>
        </div>
        <div className="stat-item">
          <span>RAM</span>
          <span className="value">
            {(memoryUsed / 1024 / 1024 / 1024).toFixed(1)}GB /
            {(memoryTotal / 1024 / 1024 / 1024).toFixed(1)}GB
          </span>
        </div>
        <div className="stat-item">
          <span>TEMP</span>
          <span className="value">{temp?.toFixed(1)}°C</span>
        </div>
      </div>

      <div className="telemetry-section">
        <h4>
          <Activity size={14} /> SWARM
        </h4>
        <div className="stat-item">
          <span>AGENTS</span>
          <span className="value">{agents}/16</span>
        </div>
        <div className="stat-item">
          <span>TASKS</span>
          <span className="value">{tasks}</span>
        </div>
        <div className="stat-item">
          <span>HEALTH</span>
          <span className="value" style={{ color: theme }}>
            {health?.toFixed(1)}%
          </span>
        </div>
      </div>

      <div className="telemetry-section">
        <h4>
          <HardDrive size={14} /> STORAGE
        </h4>
        <div className="stat-item">
          <span>DISK</span>
          <span className="value">
            {(diskUsed / 1024 / 1024 / 1024).toFixed(1)}GB /
            {(diskTotal / 1024 / 1024 / 1024).toFixed(1)}GB
          </span>
        </div>
        <div className="stat-item">
          <span>I/O</span>
          <span className="value">{ioOps?.toFixed(0)} ops/s</span>
        </div>
      </div>

      <div className="telemetry-section">
        <h4>
          <Wifi size={14} /> NETWORK
        </h4>
        <div className="stat-item">
          <span>SENT</span>
          <span className="value">{(sent / 1024 / 1024).toFixed(1)}MB</span>
        </div>
        <div className="stat-item">
          <span>RECV</span>
          <span className="value">{(recv / 1024 / 1024).toFixed(1)}MB</span>
        </div>
        <div className="stat-item">
          <span>LATENCY</span>
          <span className="value">{latency?.toFixed(1)}ms</span>
        </div>
      </div>

      <div className="telemetry-footer">
        <span>Last update: {new Date().toLocaleTimeString()}</span>
      </div>
    </div>
  )
}
