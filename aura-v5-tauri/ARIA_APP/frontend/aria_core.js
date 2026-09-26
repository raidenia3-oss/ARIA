class AriaCore {
  constructor(containerId, config = {}) {
    this.containerId = containerId;
    this.config = Object.assign({
      width: 300, height: 300,
      position: { x: 'right', y: 'bottom', offset: 20 },
      audioEnabled: false, particleCount: 5000,
      colors: { core: '#38bdf8', aura: '#ff6b35', accent: '#a855f7' },
      speed: { particleRotation: 0.001, breathing: 0.01, thinking: 0.05 },
    }, config);
    this.state = 'idle';
    this.scene = null; this.camera = null; this.renderer = null;
    this.core = null; this.particles = null; this.aura = null; this.aura2 = null;
    this.clock = new THREE.Clock();
    this.mouseX = 0; this.mouseY = 0; this.isHover = false;
    this.animationId = null;
    this.audioEnabled = this.config.audioEnabled;
    this.audioCtx = null; this.analyser = null; this.audioData = null;
    this._initThree();
  }

  _initThree() {
    const container = document.getElementById(this.containerId);
    if (!container) { console.error('AriaCore: container not found:', this.containerId); return; }
    const w = this.config.width, h = this.config.height;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 100);
    this.camera.position.z = 4;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(w, h);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(this.renderer.domElement);
    const ambient = new THREE.AmbientLight(0x404060, 0.5);
    this.scene.add(ambient);
    const pointLight = new THREE.PointLight(0x38bdf8, 2, 20);
    pointLight.position.set(0, 0, 3); this.scene.add(pointLight);
    const pointLight2 = new THREE.PointLight(0xff6b35, 1, 15);
    pointLight2.position.set(-2, -1, 2); this.scene.add(pointLight2);
    this._createCore(); this._createParticles(); this._createAura();
    this._bindEvents(container);
  }

  _createCore() {
    const geo = new THREE.IcosahedronGeometry(1, 1);
    const mat = new THREE.MeshStandardMaterial({
      color: 0x38bdf8, emissive: 0xff6b35, emissiveIntensity: 0.3,
      metalness: 0.8, roughness: 0.2, flatShading: true,
    });
    this.core = new THREE.Mesh(geo, mat); this.scene.add(this.core);
    const wireGeo = new THREE.IcosahedronGeometry(1.05, 1);
    const wireMat = new THREE.MeshBasicMaterial({
      color: 0x38bdf8, wireframe: true, transparent: true, opacity: 0.15,
    });
    this.coreWire = new THREE.Mesh(wireGeo, wireMat); this.scene.add(this.coreWire);
  }

  _createParticles() {
    const count = this.config.particleCount || 5000;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const c1 = new THREE.Color(this.config.colors.core);
    const c2 = new THREE.Color(this.config.colors.aura);
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 1.5 + Math.random() * 2;
      positions[i*3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i*3+1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i*3+2] = r * Math.cos(phi);
      const t = Math.random();
      const c = c1.clone().lerp(c2, t);
      colors[i*3] = c.r; colors[i*3+1] = c.g; colors[i*3+2] = c.b;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const mat = new THREE.PointsMaterial({
      size: 0.04, vertexColors: true, transparent: true, opacity: 0.8,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    this.particles = new THREE.Points(geo, mat);
    this.particles.userData = { velocities: this._initVelocities(count) };
    this.scene.add(this.particles);
  }

  _initVelocities(count) {
    const v = new Float32Array(count * 3);
    for (let i = 0; i < count * 3; i++) v[i] = (Math.random() - 0.5) * 0.01;
    return v;
  }

  _createAura() {
    const geo = new THREE.TorusGeometry(1.8, 0.02, 8, 64);
    const mat = new THREE.MeshBasicMaterial({ color: 0xff6b35, transparent: true, opacity: 0.4 });
    this.aura = new THREE.Mesh(geo, mat);
    this.aura.rotation.x = Math.PI / 4; this.scene.add(this.aura);
    const geo2 = new THREE.TorusGeometry(2.1, 0.015, 8, 64);
    const mat2 = new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.2 });
    this.aura2 = new THREE.Mesh(geo2, mat2);
    this.aura2.rotation.x = -Math.PI / 6; this.scene.add(this.aura2);
  }

  _bindEvents(container) {
    const canvas = this.renderer.domElement;
    canvas.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      this.mouseX = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
      this.mouseY = -((e.clientY - rect.top) / rect.height - 0.5) * 2;
      this.isHover = true;
    });
    canvas.addEventListener('mouseleave', () => { this.isHover = false; });
    canvas.addEventListener('click', () => {
      container.dispatchEvent(new CustomEvent('aria-click'));
    });
  }

  init() { this.start(); }

  start() {
    const animate = () => {
      this.animationId = requestAnimationFrame(animate);
      this._update(this.clock.getElapsedTime());
      this.renderer.render(this.scene, this.camera);
    };
    animate();
    this._emitEvent('startup');
  }

  _update(t) {
    const breathScale = 1.0 + Math.sin(t * this.config.speed.breathing * Math.PI) * 0.1;
    const hoverScale = this.isHover ? 0.3 : 0;
    const stateScale = this._getStateScale();
    const scale = breathScale + hoverScale + stateScale;
    if (this.core) {
      this.core.scale.setScalar(scale);
      this.core.rotation.x = t * 0.2; this.core.rotation.y = t * 0.3;
      this.core.material.emissiveIntensity = this._getEmissiveIntensity(t);
    }
    if (this.coreWire) {
      this.coreWire.scale.setScalar(scale * 1.02);
      this.coreWire.rotation.x = -t * 0.15; this.coreWire.rotation.z = t * 0.1;
    }
    if (this.particles) {
      const positions = this.particles.geometry.attributes.position.array;
      const velocities = this.particles.userData.velocities;
      const count = positions.length / 3;
      const speedMult = this._getParticleSpeed();
      for (let i = 0; i < count; i++) {
        const ix = i*3, iy = i*3+1, iz = i*3+2;
        const px = positions[ix], py = positions[iy], pz = positions[iz];
        const dist = Math.sqrt(px*px + py*py + pz*pz) + 0.1;
        velocities[ix] += -px/dist * 0.001 * speedMult;
        velocities[iy] += -py/dist * 0.001 * speedMult;
        velocities[iz] += -pz/dist * 0.001 * speedMult;
        velocities[ix] *= 0.99; velocities[iy] *= 0.99; velocities[iz] *= 0.99;
        positions[ix] += velocities[ix]; positions[iy] += velocities[iy]; positions[iz] += velocities[iz];
        const newDist = Math.sqrt(positions[ix]**2 + positions[iy]**2 + positions[iz]**2);
        if (newDist < 1.2) { const s = 1.2/newDist; positions[ix]*=s; positions[iy]*=s; positions[iz]*=s; }
      }
      this.particles.geometry.attributes.position.needsUpdate = true;
      this.particles.rotation.y = t * this.config.speed.particleRotation * speedMult;
    }
    if (this.aura) {
      this.aura.rotation.z = t * 0.5; this.aura.rotation.y = t * 0.3;
      this.aura.material.opacity = 0.3 + Math.sin(t * 2) * 0.15;
    }
    if (this.aura2) {
      this.aura2.rotation.z = -t * 0.3;
      this.aura2.rotation.x = Math.PI/6 + Math.sin(t * 0.5) * 0.2;
      this.aura2.material.opacity = 0.15 + Math.sin(t * 1.5) * 0.1;
    }
    this.camera.position.x += (this.mouseX * 0.3 - this.camera.position.x) * 0.05;
    this.camera.position.y += (this.mouseY * 0.3 - this.camera.position.y) * 0.05;
    this.camera.lookAt(0, 0, 0);
  }

  _getStateScale() {
    switch (this.state) {
      case 'thinking': return 0.15 + Math.sin(performance.now() * 0.005) * 0.05;
      case 'speaking': return 0.1;
      case 'learning': return 0.2;
      case 'active': return 0.25;
      default: return 0;
    }
  }

  _getEmissiveIntensity(t) {
    const base = 0.3;
    switch (this.state) {
      case 'idle': return base + Math.sin(t * 2) * 0.1;
      case 'thinking': return 0.8 + Math.sin(t * 8) * 0.3;
      case 'speaking': return 0.6 + Math.sin(t * 4) * 0.4;
      case 'learning': return 0.5 + Math.sin(t * 1.5) * 0.3;
      case 'active': return 1.0;
      default: return base;
    }
  }

  _getParticleSpeed() {
    switch (this.state) {
      case 'thinking': return 3; case 'speaking': return 2;
      case 'learning': return 1.5; case 'active': return 4;
      default: return 1;
    }
  }

  setState(state) { this.state = state; this._emitEvent('stateChange', { state }); }

  respond(text, duration = 2000) {
    this.setState('speaking');
    this._emitEvent('respond', { text, duration });
    setTimeout(() => { if (this.state === 'speaking') this.setState('idle'); }, duration);
  }

  startAudio() {
    if (!this.audioEnabled) return;
    try {
      this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = this.audioCtx.createAnalyser();
      analyser.fftSize = 256;
      navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
        const source = this.audioCtx.createMediaStreamSource(stream);
        source.connect(analyser);
        this.analyser = analyser;
        this.audioData = new Uint8Array(analyser.frequencyBinCount);
      });
    } catch (e) {}
  }

  stop() { if (this.animationId) cancelAnimationFrame(this.animationId); }

  _emitEvent(name, data = {}) {
    const container = document.getElementById(this.containerId);
    if (container) container.dispatchEvent(new CustomEvent('aria-' + name, { detail: data }));
  }
}
