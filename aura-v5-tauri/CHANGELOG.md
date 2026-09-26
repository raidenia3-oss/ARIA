# ARIA OS v5.0-Tauri — Changelog

## [5.0.0] — 2026-09-24

### ✨ Major Changes
- **Migrated from Electron to Tauri 2.0** — 44x smaller bundle (6 MB executable vs 250 MB)
- **Orb Visual** — 7-layer Three.js orb with fresnel shaders, particles, pulse rings, burst rays
- **UI Framework** — Serpantinum×Caelestia glassmorphism palette, Material Design 3 components
- **Architecture** — Rust backend + React frontend + FastAPI Python integration
- **Performance** — 60fps smooth, <50 MB RAM, instant startup

### 🎨 Visual Enhancements
- Orb: 7 layers (solid sphere, core glow, orbit ring, particles, outer halo, pulse ring, burst rays)
- Header: Logo glyph ◆, status dot, theme picker, window controls
- Chat: Markdown + GFM, metadata glow (src/conf/latency), streaming text
- Skills: Glassmorphism sidebar, 35+ skills from registry, search filter
- Controls: Material Design 3 toggles, opacity slider, 4 theme presets

### 🚀 Performance
- **Bundle Size**: 6 MB (standalone exe) + 11 MB (installer with Python)
- **Memory**: <50 MB runtime (vs 200+ MB Electron)
- **Startup**: <500ms (vs 2-5s Electron)
- **GPU**: Three.js WebGL2 (WebGPU ready for v5.1)

### 🛠️ Technical
- **Frontend**: React 19 + TypeScript + Tailwind + Three.js
- **Desktop**: Tauri 2.0 + Rust backend
- **Backend**: FastAPI Python + Ollama (localhost:8000)
- **IPC**: Tauri commands + HTTP bridge
- **Build**: Vite + electron-builder replacement

### 🔧 Known Limitations
- WebGPU compute shaders — planned for v5.1 (Phase 1)
- System tray — minimal (basic show/hide/exit)
- Multi-monitor — single window focus only

### 📦 Installation
- **Windows**: Download MSI installer or portable exe
- **Build from source**: `npm run tauri build`
- **Dev mode**: `npm run dev` + `npm run tauri dev`

### 🙏 Credits
- Frontend from ARIA v5.0 Electron migration
- Three.js orb by Kilo
- Tauri framework by Tauri Team
- Serpantinum palette inspiration from @nestquik dotfiles

---

## [4.0.0] — 2026-09-22

### Initial Release
- PyQt5 desktop app with floating orb overlay
- 25 features across 4 phases (visual polish, interaction, features, polish)
- Skills dock, control center, theme selector, command palette
- FastAPI backend integration, IPC communication

---