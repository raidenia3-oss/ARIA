import React, { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import NucleusCanvas from './components/NucleusCanvas'
import NucleusCanvas3D from './components/NucleusCanvas3D'
import SynapticGraph from './components/SynapticGraph'
import ReactorMatrix from './components/ReactorMatrix'
import TacticalChat from './components/TacticalChat'
import HexColorPicker from './components/HexColorPicker'
import Telemetry from './components/Telemetry'
import QuickActions from './components/QuickActions'
import MasterDashboard from './components/MasterDashboard'
import WebSocketManager from './hooks/useWebSocket'
import './App.css'

export default function App() {
  const [theme, setTheme] = useState('#6366f1')
  const [activeTab, setActiveTab] = useState('nucleus')
  const [telemetry, setTelemetry] = useState(null)
  const [connected, setConnected] = useState(false)
  const [masterOpen, setMasterOpen] = useState(false)
  const [show3d, setShow3d] = useState(true)

  useEffect(() => {
    const wsManager = new WebSocketManager('ws://localhost:8000/ws/telemetry')
    wsManager.onMessage = (data) => { setTelemetry(data) }
    wsManager.onOpen = () => setConnected(true)
    wsManager.onClose = () => setConnected(false)
    return () => wsManager.close()
  }, [])

  const openMaster = useCallback(() => setMasterOpen(true), [])
  const closeMaster = useCallback(() => setMasterOpen(false), [])

  return (
    <div
      className="aura-app"
      style={{
        '--primary-color': theme,
        '--rgb-primary': hexToRgb(theme),
      }}
    >
      {/* ===== HEADER ===== */}
      <header className="aura-header">
        <div className="header-brand">
          <div className="nucleus-mini">
            <motion.div
              className="nucleus-dot"
              animate={{ scale: [1, 1.15, 1], opacity: [0.8, 1, 0.8] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
          </div>
          <h1>AURA NUCLEUS OS</h1>
          <span className={`status-dot ${connected ? 'online' : 'offline'}`}></span>
        </div>

        <nav className="header-nav">
          {['nucleus', 'chat', 'actions'].map((tab) => (
            <button
              key={tab}
              className={`nav-btn ${activeTab === tab ? 'active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab.toUpperCase()}
            </button>
          ))}
        </nav>

        <div className="header-controls">
          <button className="nav-btn master-btn" onClick={openMaster} title="Master Control">
            MASTER
          </button>
          <button
            className="nav-btn toggle-3d"
            onClick={() => setShow3d(!show3d)}
            title="Toggle 2D/3D"
          >
            {show3d ? '3D' : '2D'}
          </button>
          <HexColorPicker value={theme} onChange={setTheme} />
        </div>
      </header>

      {/* ===== MAIN CONTENT ===== */}
      <main className="aura-main">
        <AnimatePresence mode="wait">
          {activeTab === 'nucleus' && (
            <motion.div
              key="nucleus"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="tab-content"
            >
              {show3d ? (
                <NucleusCanvas3D theme={theme} telemetry={telemetry} />
              ) : (
                <NucleusCanvas theme={theme} telemetry={telemetry} />
              )}
            </motion.div>
          )}

          {activeTab === 'chat' && (
            <motion.div
              key="chat"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="tab-content"
            >
              <TacticalChat theme={theme} telemetry={telemetry} />
            </motion.div>
          )}

          {activeTab === 'actions' && (
            <motion.div
              key="actions"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="tab-content"
            >
              <QuickActions theme={theme} />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* ===== SIDEBAR ===== */}
      <aside className="aura-sidebar">
        <Telemetry data={telemetry} theme={theme} />
        <div className="sidebar-divider"></div>
        <QuickActions theme={theme} />
      </aside>

      {/* ===== STATUS BAR ===== */}
      <footer className="aura-footer">
        <div className="status-info">
          <span>🔌 Backend: {connected ? '✅ Connected' : '❌ Disconnected'}</span>
          {telemetry && (
            <>
              <span>💾 RAM: {telemetry.memory?.percent.toFixed(1)}%</span>
              <span>⚡ CPU: {telemetry.cpu?.percent.toFixed(1)}%</span>
              <span>🤖 Agents: {telemetry.swarm?.active_agents || 0}</span>
            </>
          )}
        </div>
        <div className="time">
          {new Date().toLocaleTimeString('es-ES')}
        </div>
      </footer>

      <MasterDashboard open={masterOpen} onClose={closeMaster} theme={theme} />
    </div>
  )
}

function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  return result
    ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}`
    : '99, 102, 241'
}
