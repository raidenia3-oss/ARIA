"""ARIA Floating Widget Enhanced - JavaScript source.
Generado por Kilo para ARIA OS v3.2.0.
Clase: FloatingAriaWidget
"""

JS_CODE = r'''
class FloatingAriaWidget {
  constructor(config = {}) {
    this.config = Object.assign({
      width: 300, height: 300,
      position: { x: "right", y: "bottom", offset: 20 },
      z_index: 999999,
      particle_count: 10000,
      colors: {
        core: "#38bdf8", aura: "#ff6b35", accent: "#a855f7",
        neon_cyan: "#00ffff", neon_magenta: "#ff00ff", neon_lime: "#a8ff00",
      },
      speed: { particle_rotation: 0.001, breathing: 0.01, thinking: 0.05 },
      orb_detail: 200, metalness: 0.9, roughness: 0.1,
      bloom_strength: 0.8, bloom_radius: 0.3,
      antialias: true, msaa_samples: 4,
    }, config);
    this.state = "idle";
    this.is_visible = true;
    this.is_invisible = false;
    this._scene = null; this._camera = null; this._renderer = null;
    this._core = null; this._particles = null; this._aura = null; this._aura2 = null;
    this._coreWire = null; this._coreShell = null; this._clock = null;
    this._animationId = null;
    this._dragging = false; this._dragOffset = { x: 0, y: 0 };
    this._mouse = { x: 0, y: 0 }; this._isHover = false;
    this._trayIcon = null; this._container = null; this._ws = null;
  }

  async initEnhanced() {
    const container = document.getElementById("aria-floating-container");
    if (!container) return false;
    this._container = container;
    container.style.cssText = "position:fixed;bottom:20px;right:20px;z-index:999999;user-select:none;cursor:move;";

    this._scene = new THREE.Scene();
    this._camera = new THREE.PerspectiveCamera(50, this.config.width / this.config.height, 0.1, 100);
    this._camera.position.z = 4;
    this._renderer = new THREE.WebGLRenderer({ antialias: this.config.antialias, alpha: true, premultipliedAlpha: false });
    this._renderer.setSize(this.config.width, this.config.height);
    this._renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this._renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this._renderer.toneMappingExposure = 1.2;
    container.appendChild(this._renderer.domElement);

    this._scene.add(new THREE.AmbientLight(0x404060, 0.8));
    const l1 = new THREE.PointLight(0x38bdf8, 3, 25); l1.position.set(2, 2, 4); this._scene.add(l1);
    const l2 = new THREE.PointLight(0xff00ff, 2, 20); l2.position.set(-2, -1, 3); this._scene.add(l2);
    const l3 = new THREE.PointLight(0xa8ff00, 1, 15); l3.position.set(0, -3, 2); this._scene.add(l3);

    await this.renderOrbEnhanced();
    await this.particleSystemEnhanced();
    this._createAuraEffects();
    this._bindDragEvents(container);
    this._bindHoverEffects();
    this._animate();
    this._updateStatus("ARIA activa - Observando...");
    return true;
  }

  async renderOrbEnhanced() {
    const geo = new THREE.IcosahedronGeometry(1, this.config.orbDetail);
    const mat = new THREE.MeshPhysicalMaterial({
      color: 0x38bdf8, emissive: 0xff6b35, emissiveIntensity: 0.4,
      metalness: this.config.metalness, roughness: this.config.roughness,
      clearcoat: 1.0, clearcoatRoughness: 0.1, reflectivity: 0.9,
      transparent: true, opacity: 0.95, envMapIntensity: 1.5, side: THREE.DoubleSide,
    });
    this._core = new THREE.Mesh(geo, mat);
    this._scene.add(this._core);
    const wireGeo = new THREE.IcosahedronGeometry(1.02, 8);
    const wireMat = new THREE.MeshBasicMaterial({ color: 0x00ffff, wireframe: true, transparent: true, opacity: 0.1 });
    this._coreWire = new THREE.Mesh(wireGeo, wireMat);
    this._scene.add(this._coreWire);
    const shellGeo = new THREE.SphereGeometry(1.15, 64, 64);
    const shellMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.03, side: THREE.BackSide });
    this._coreShell = new THREE.Mesh(shellGeo, shellMat);
    this._scene.add(this._coreShell);
  }

  async particleSystemEnhanced() {
    const count = this.config.particleCount;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const velocities = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 1.5 + Math.random() * 3;
      positions[i*3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i*3+1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i*3+2] = r * Math.cos(phi);
      const t = Math.random();
      if (t < 0.33) { colors[i*3]=0; colors[i*3+1]=0.74; colors[i*3+2]=0.97; }
      else if (t < 0.66) { colors[i*3]=1; colors[i*3+1]=0.42; colors[i*3+2]=0.21; }
      else { colors[i*3]=0.66; colors[i*3+1]=0.33; colors[i*3+2]=0.97; }
      velocities[i*3] = (Math.random()-0.5)*0.01;
      velocities[i*3+1] = (Math.random()-0.5)*0.01;
      velocities[i*3+2] = (Math.random()-0.5)*0.01;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const mat = new THREE.PointsMaterial({
      size: 0.05, vertexColors: true, transparent: true, opacity: 0.8,
      blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true,
    });
    this._particles = new THREE.Points(geo, mat);
    this._particles.userData = { velocities };
    this._scene.add(this._particles);
  }

  _createAuraEffects() {
    const geo1 = new THREE.TorusGeometry(2, 0.02, 16, 100);
    const mat1 = new THREE.MeshBasicMaterial({ color: 0x00ffff, transparent: true, opacity: 0.3 });
    this._aura = new THREE.Mesh(geo1, mat1);
    this._aura.rotation.x = Math.PI / 2;
    this._scene.add(this._aura);
    const geo2 = new THREE.TorusGeometry(2.2, 0.015, 16, 100);
    const mat2 = new THREE.MeshBasicMaterial({ color: 0xa855f7, transparent: true, opacity: 0.2 });
    this._aura2 = new THREE.Mesh(geo2, mat2);
    this._aura2.rotation.x = Math.PI / 2;
    this._aura2.rotation.y = Math.PI / 4;
    this._scene.add(this._aura2);
  }

  _bindDragEvents(container) {
    container.addEventListener("mousedown", (e) => {
      this._dragging = true;
      this._dragOffset.x = e.clientX - container.offsetLeft;
      this._dragOffset.y = e.clientY - container.offsetTop;
      container.style.cursor = "grabbing";
    });
    document.addEventListener("mousemove", (e) => {
      if (this._dragging) {
        container.style.left = (e.clientX - this._dragOffset.x) + "px";
        container.style.top = (e.clientY - this._dragOffset.y) + "px";
        container.style.right = "auto"; container.style.bottom = "auto";
      }
      this._mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
      this._mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
    });
    document.addEventListener("mouseup", () => {
      if (this._dragging) { this._dragging = false; container.style.cursor = "move"; }
    });
  }

  _bindHoverEffects() {
    const canvas = this._renderer?.domElement;
    if (!canvas) return;
    canvas.addEventListener("mouseenter", () => { this._isHover = true; });
    canvas.addEventListener("mouseleave", () => { this._isHover = false; });
  }

  _animate() {
    this._animationId = requestAnimationFrame(() => this._animate());
    if (!this._core) return;
    this._core.rotation.x += 0.003;
    this._core.rotation.y += 0.005;
    const breath = 1 + Math.sin(Date.now() * this.config.speed.breathing) * 0.05;
    this._core.scale.setScalar(breath);
    if (this._coreWire) { this._coreWire.rotation.x -= 0.002; this._coreWire.rotation.y -= 0.003; this._coreWire.scale.setScalar(breath * 1.02); }
    if (this._coreShell) { this._coreShell.scale.setScalar(breath * 1.1); }
    if (this._aura) this._aura.rotation.z += 0.002;
    if (this._aura2) this._aura2.rotation.z -= 0.0015;
    if (this._particles) {
      const pos = this._particles.geometry.attributes.position.array;
      const vel = this._particles.userData.velocities;
      const gravity = -0.0002;
      for (let i = 0; i < pos.length; i += 3) {
        pos[i] += vel[i] + Math.sin(Date.now()*0.001+i) * 0.001;
        pos[i+1] += vel[i+1] + gravity;
        pos[i+2] += vel[i+2] + Math.cos(Date.now()*0.001+i) * 0.001;
        const dist = Math.sqrt(pos[i]**2 + pos[i+1]**2 + pos[i+2]**2);
        if (dist > 4) { pos[i]*=1.5/4; pos[i+1]*=1.5/4; pos[i+2]*=1.5/4; }
      }
      this._particles.geometry.attributes.position.needsUpdate = true;
      this._particles.rotation.y += this.config.speed.particleRotation;
    }
    if (this._core.material) {
      this._core.material.emissiveIntensity = this._isHover ? 0.6 + Math.sin(Date.now()*0.005)*0.2 : 0.4;
    }
    if (this._isInvisible) {
      this._renderer.domElement.style.opacity = "0";
      this._renderer.domElement.style.pointerEvents = "none";
    } else {
      this._renderer.domElement.style.opacity = "1";
      this._renderer.domElement.style.pointerEvents = "auto";
    }
    this._renderer.render(this._scene, this._camera);
  }

  async setInvisibleMode(invisible = true) {
    this.isInvisible = invisible;
    if (invisible) { this._showTrayIcon(); } else { this._hideTrayIcon(); }
  }

  _showTrayIcon() {
    if (document.getElementById("aria-tray-icon")) return;
    const tray = document.createElement("div");
    tray.id = "aria-tray-icon";
    tray.style.cssText = "position:fixed;bottom:10px;right:10px;width:32px;height:32px;border-radius:50%;background:radial-gradient(circle,#38bdf8,#0f172a);z-index:999999;cursor:pointer;box-shadow:0 0 15px rgba(56,189,248,0.5);display:flex;align-items:center;justify-content:center;font-size:14px;";
    tray.textContent = "💎";
    tray.title = "ARIA OS - Click to show";
    tray.addEventListener("click", () => this.setInvisibleMode(false));
    document.body.appendChild(tray);
    this._trayIcon = tray;
  }

  _hideTrayIcon() {
    if (this._trayIcon) { this._trayIcon.remove(); this._trayIcon = null; }
  }

  connectWebSocket() {
    try {
      this._ws = new WebSocket("ws://localhost:8000/api/aria/g7/stream");
      this._ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === "mood") { this._updateMood(data); }
        if (data.type === "suggestion") { this._showNotification(data.suggestion); }
        if (data.type === "activity") { this._updateStatus(data.text); }
      };
    } catch(e) {}
  }

  _updateMood(moodData) {
    const el = document.getElementById("aria-mood");
    if (el) el.textContent = moodData.mood || "idle";
  }

  _showNotification(suggestion) {
    const n = document.createElement("div");
    n.style.cssText = "position:fixed;top:20px;right:20px;background:rgba(56,189,248,0.2);border:1px solid rgba(56,189,248,0.4);border-radius:8px;padding:10px;color:#e2e8f0;font-size:12px;z-index:999998;max-width:300px;backdrop-filter:blur(10px);animation:fadeIn 0.3s ease;";
    n.innerHTML = "<strong>&#9830; ARIA</strong><br>" + (suggestion.title || suggestion.suggestion_type || "New suggestion");
    document.body.appendChild(n);
    setTimeout(() => n.remove(), 5000);
  }

  _updateStatus(text) {
    const el = document.getElementById("aria-status");
    if (el) el.textContent = text.substring(0, 60);
  }

  dispose() {
    if (this._ws) this._ws.close();
    if (this._animationId) cancelAnimationFrame(this._animationId);
    if (this._renderer) this._renderer.dispose();
    this._scene = null; this._core = null; this._particles = null;
    this._aura = null; this._aura2 = null; this._container = null;
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    window._ariaWidget = new FloatingAriaWidget();
    window._ariaWidget.initEnhanced();
    window._ariaWidget.connectWebSocket();
  });
} else {
  window._ariaWidget = new FloatingAriaWidget();
  window._ariaWidget.initEnhanced();
  window._ariaWidget.connectWebSocket();
}
'''
