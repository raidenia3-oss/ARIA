/* ============================================================
   ARIA CORE EXTREME — Three.js 10x Improved
   ============================================================ */
class AriaCoreExtreme {
  constructor(containerId, config = {}) {
    this.containerId = containerId;
    this.config = Object.assign({
      width: 400, height: 400,
      particleCount: 20000,
      colors: { core1: '#00ff88', core2: '#00d9ff', accent: '#ff006e' },
      speed: { rotation: 0.3, breathing: 1.0, particle: 0.5 },
      quality: 'high',
    }, config);
    this.state = 'ready';
    this.mouseX = 0; this.mouseY = 0; this.isHover = false;
    this.audioLevel = 0; this.mood = 'neutral';
    this.animationId = null;
    this._initThree();
  }

  _initThree() {
    const container = document.getElementById(this.containerId);
    if (!container) return;
    const w = this.config.width, h = this.config.height;

    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.FogExp2(0x0a0e27, 0.05);

    this.camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 100);
    this.camera.position.z = 5;

    this.renderer = new THREE.WebGLRenderer({
      antialias: true, alpha: true, preserveDrawingBuffer: true,
    });
    this.renderer.setSize(w, h);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.2;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(this.renderer.domElement);

    this._createLights();
    this._createCore();
    this._createParticles();
    this._createAura();
    this._createPulseWaves();
    this._createHalo();
    this._createGridFloor();
    this._createEnvironmentMap();
    this._bindEvents(container);
  }

  _createLights() {
    this.ambient = new THREE.AmbientLight(0x1a1f3a, 0.5);
    this.scene.add(this.ambient);

    this.dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
    this.dirLight.position.set(3, 5, 4);
    this.dirLight.castShadow = true;
    this.dirLight.shadow.mapSize.set(4096, 4096);
    this.scene.add(this.dirLight);

    const colors = [0x00ff88, 0x00d9ff, 0xff006e, 0xffd600];
    this.pointLights = [];
    for (let i = 0; i < 4; i++) {
      const pl = new THREE.PointLight(colors[i], 2, 25);
      pl.position.set(
        Math.cos(i * Math.PI / 2) * 4,
        Math.sin(i * Math.PI / 2) * 3,
        2 + i * 0.5
      );
      this.pointLights.push(pl);
      this.scene.add(pl);
    }

    this.spotLight1 = new THREE.SpotLight(0x00ff88, 3, 20, Math.PI / 6, 0.5);
    this.spotLight1.position.set(2, 6, 3);
    this.scene.add(this.spotLight1);

    this.spotLight2 = new THREE.SpotLight(0xff006e, 2, 20, Math.PI / 6, 0.5);
    this.spotLight2.position.set(-2, 4, -3);
    this.scene.add(this.spotLight2);
  }

  _createCore() {
    const geo = new THREE.IcosahedronGeometry(1.2, 4);
    const mat = new THREE.MeshPhysicalMaterial({
      color: 0x0a0e27,
      metalness: 0.95,
      roughness: 0.05,
      emissive: 0x00ff88,
      emissiveIntensity: 0.3,
      clearcoat: 1.0,
      clearcoatRoughness: 0.1,
      envMapIntensity: 1.5,
    });
    this.core = new THREE.Mesh(geo, mat);
    this.core.castShadow = true;
    this.scene.add(this.core);

    const wireGeo = new THREE.IcosahedronGeometry(1.35, 2);
    const wireMat = new THREE.MeshBasicMaterial({
      color: 0x00ff88, wireframe: true, transparent: true, opacity: 0.12,
    });
    this.coreWire = new THREE.Mesh(wireGeo, wireMat);
    this.scene.add(this.coreWire);
  }

  _createParticles() {
    const count = this.config.particleCount;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    const c1 = new THREE.Color(this.config.colors.core1);
    const c2 = new THREE.Color(this.config.colors.core2);
    const c3 = new THREE.Color(this.config.colors.accent);

    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 1.8 + Math.random() * 3.5;
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);

      const t = Math.random();
      let c;
      if (t < 0.4) c = c1;
      else if (t < 0.7) c = c2;
      else c = c3;
      colors[i * 3] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
      sizes[i] = Math.random() * 0.08 + 0.02;
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geo.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

    const mat = new THREE.PointsMaterial({
      size: 0.06, vertexColors: true, transparent: true, opacity: 0.85,
      blending: THREE.AdditiveBlending, depthWrite: false,
      sizeAttenuation: true,
    });
    this.particles = new THREE.Points(geo, mat);
    this.particles.userData = {
      velocities: this._initVelocities(count),
      phases: this._initPhases(count),
    };
    this.scene.add(this.particles);
  }

  _initVelocities(count) {
    const v = new Float32Array(count * 3);
    for (let i = 0; i < count * 3; i++) v[i] = (Math.random() - 0.5) * 0.005;
    return v;
  }

  _initPhases(count) {
    const p = new Float32Array(count);
    for (let i = 0; i < count; i++) p[i] = Math.random() * Math.PI * 2;
    return p;
  }

  _createAura() {
    this.auras = [];
    const auraColors = [0x00ff88, 0x00d9ff, 0xff006e, 0xffd600];
    for (let i = 0; i < 3; i++) {
      const geo = new THREE.TorusGeometry(2.0 + i * 0.3, 0.015, 8, 128);
      const mat = new THREE.MeshBasicMaterial({
        color: auraColors[i], transparent: true, opacity: 0.15 - i * 0.03,
      });
      const aura = new THREE.Mesh(geo, mat);
      aura.rotation.x = Math.PI / (3 + i);
      aura.rotation.y = i * 0.3;
      this.auras.push(aura);
      this.scene.add(aura);
    }
  }

  _createPulseWaves() {
    const geo = new THREE.SphereGeometry(1.5, 32, 32);
    const mat = new THREE.MeshBasicMaterial({
      color: 0x00ff88, transparent: true, opacity: 0.05, wireframe: true,
    });
    this.pulseWave = new THREE.Mesh(geo, mat);
    this.pulseWave.scale.setScalar(1.0);
    this.scene.add(this.pulseWave);

    const geo2 = new THREE.SphereGeometry(1.8, 32, 32);
    const mat2 = new THREE.MeshBasicMaterial({
      color: 0x00d9ff, transparent: true, opacity: 0.03, wireframe: true,
    });
    this.pulseWave2 = new THREE.Mesh(geo2, mat2);
    this.scene.add(this.pulseWave2);
  }

  _createHalo() {
    const geo = new THREE.SphereGeometry(2.5, 32, 32);
    const mat = new THREE.MeshBasicMaterial({
      color: 0x00ff88, transparent: true, opacity: 0.02, side: THREE.BackSide,
    });
    this.halo = new THREE.Mesh(geo, mat);
    this.scene.add(this.halo);
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
    canvas.addEventListener('click', () => { this._explodeAndReform(); });
    canvas.addEventListener('dblclick', () => { this._toggleState(); });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'm' || e.key === 'M') this._toggleInvisible();
      if (e.key === 'q' || e.key === 'Q') this.camera.position.x -= 0.1;
      if (e.key === 'e' || e.key === 'E') this.camera.position.x += 0.1;
    });

    window.addEventListener('resize', () => {
      const r = container.getBoundingClientRect();
      this.camera.aspect = r.width / r.height;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(r.width, r.height);
    });
  }

  _explodeAndReform() {
    const positions = this.particles.geometry.attributes.position.array;
    const velocities = this.particles.userData.velocities;
    const count = positions.length / 3;
    for (let i = 0; i < count; i++) {
      const ix = i * 3, iy = i * 3 + 1, iz = i * 3 + 2;
      const px = positions[ix], py = positions[iy], pz = positions[iz];
      const dist = Math.sqrt(px * px + py * py + pz * pz) || 1;
      const force = 0.15;
      velocities[ix] += (px / dist) * force;
      velocities[iy] += (py / dist) * force;
      velocities[iz] += (pz / dist) * force;
    }
    setTimeout(() => {
      for (let i = 0; i < count * 3; i++) velocities[i] *= 0.1;
    }, 500);
  }

  _toggleState() {
    const states = ['ready', 'active', 'thinking', 'idle'];
    const idx = states.indexOf(this.state);
    this.state = states[(idx + 1) % states.length];
    if (this.onStateChange) this.onStateChange(this.state);
  }

  _toggleInvisible() {
    if (this.onInvisible) this.onInvisible();
  }

  setState(state) {
    this.state = state;
    if (this.onStateChange) this.onStateChange(state);
  }

  setMood(mood) { this.mood = mood; }
  setAudioLevel(level) { this.audioLevel = Math.max(0, Math.min(1, level)); }

  start() {
    const animate = () => {
      this.animationId = requestAnimationFrame(animate);
      this._update(performance.now() * 0.001);
      this.renderer.render(this.scene, this.camera);
    };
    animate();
  }

  _update(t) {
    const cfg = this._getStateConfig();
    const speedMult = this.state === 'thinking' ? 2.0 : this.state === 'active' ? 1.5 : 1.0;

    const breathScale = 1.0 + Math.sin(t * cfg.breathing) * 0.08 + this.audioLevel * 0.15;
    const hoverScale = this.isHover ? 0.12 : 0;
    this.core.scale.setScalar(breathScale + hoverScale);
    this.core.rotation.x = t * cfg.rotation * speedMult;
    this.core.rotation.y = t * cfg.rotation * 0.7 * speedMult;
    this.core.material.emissiveIntensity = 0.2 + Math.sin(t * 2) * 0.1 + this.audioLevel * 0.3;

    this.coreWire.scale.setScalar(breathScale + hoverScale + 0.05);
    this.coreWire.rotation.x = -t * cfg.rotation * 0.5;
    this.coreWire.rotation.z = t * cfg.rotation * 0.3;

    this._updateParticles(t, speedMult);

    this.auras.forEach((aura, i) => {
      aura.rotation.x += 0.002 * (i + 1);
      aura.rotation.y += 0.003 * (i + 1);
      aura.rotation.z += 0.001 * speedMult;
      aura.material.opacity = (0.12 - i * 0.03) + Math.sin(t * 1.5 + i) * 0.05;
    });

    const pulseScale = 1.0 + Math.sin(t * 1.5) * 0.05 + this.audioLevel * 0.1;
    this.pulseWave.scale.setScalar(pulseScale);
    this.pulseWave.material.opacity = 0.05 + Math.sin(t * 2) * 0.02;
    this.pulseWave2.scale.setScalar(1.0 + Math.sin(t * 1.0 + 1) * 0.08);
    this.pulseWave2.material.opacity = 0.03 + Math.sin(t * 1.5 + 1) * 0.01;

    this.halo.scale.setScalar(1.0 + Math.sin(t * 0.8) * 0.03);
    this.halo.material.opacity = 0.02 + Math.sin(t * 1.2) * 0.01;

    this.dirLight.position.x = Math.cos(t * 0.3) * 5;
    this.dirLight.position.z = Math.sin(t * 0.3) * 5;

    this.pointLights.forEach((pl, i) => {
      const angle = t * 0.5 + i * Math.PI / 2;
      pl.position.x = Math.cos(angle) * 4;
      pl.position.y = Math.sin(angle * 1.3) * 3;
      pl.position.z = Math.cos(angle * 0.7) * 3;
      pl.intensity = 2 + Math.sin(t * 2 + i) * 0.5;
    });

    this.spotLight1.position.x = Math.cos(t * 0.4) * 3;
    this.spotLight1.position.z = Math.sin(t * 0.4) * 3;
    this.spotLight2.position.x = Math.cos(t * 0.4 + Math.PI) * 3;
    this.spotLight2.position.z = Math.sin(t * 0.4 + Math.PI) * 3;

    this.camera.position.x += (this.mouseX * 0.5 - this.camera.position.x) * 0.03;
    this.camera.position.y += (this.mouseY * 0.5 - this.camera.position.y) * 0.03;
    this.camera.lookAt(0, 0, 0);
  }

  _updateParticles(t, speedMult) {
    const positions = this.particles.geometry.attributes.position.array;
    const velocities = this.particles.userData.velocities;
    const phases = this.particles.userData.phases;
    const count = positions.length / 3;

    for (let i = 0; i < count; i++) {
      const ix = i * 3, iy = i * 3 + 1, iz = i * 3 + 2;
      const px = positions[ix], py = positions[iy], pz = positions[iz];
      const dist = Math.sqrt(px * px + py * py + pz * pz) + 0.1;

      velocities[ix] += (-px / dist) * 0.0005 * speedMult;
      velocities[iy] += (-py / dist) * 0.0005 * speedMult;
      velocities[iz] += (-pz / dist) * 0.0005 * speedMult;

      velocities[ix] *= 0.995;
      velocities[iy] *= 0.995;
      velocities[iz] *= 0.995;

      const phase = phases[i];
      const wobble = 0.001 * speedMult;
      velocities[ix] += Math.sin(t * 2 + phase) * wobble;
      velocities[iy] += Math.cos(t * 2.5 + phase) * wobble;
      velocities[iz] += Math.sin(t * 1.5 + phase * 2) * wobble;

      positions[ix] += velocities[ix];
      positions[iy] += velocities[iy];
      positions[iz] += velocities[iz];

      const newDist = Math.sqrt(positions[ix] ** 2 + positions[iy] ** 2 + positions[iz] ** 2);
      if (newDist < 1.5) {
        const s = 1.5 / newDist;
        positions[ix] *= s; positions[iy] *= s; positions[iz] *= s;
      }
      if (newDist > 6) {
        const s = 6 / newDist;
        positions[ix] *= s; positions[iy] *= s; positions[iz] *= s;
      }
    }
    this.particles.geometry.attributes.position.needsUpdate = true;
    this.particles.rotation.y = t * this.config.speed.particle * speedMult;
    this.particles.rotation.x = Math.sin(t * 0.3) * 0.1;
  }

  _getStateConfig() {
    switch (this.state) {
      case 'active': return { breathing: 1.5, rotation: 0.5 };
      case 'thinking': return { breathing: 0.8, rotation: 0.2 };
      case 'idle': return { breathing: 1.0, rotation: 0.15 };
      default: return { breathing: 1.0, rotation: 0.3 };
    }
  }

  stop() {
    if (this.animationId) cancelAnimationFrame(this.animationId);
  }

  // === POST-PROCESSING SIMULATION ===
  _applyPostProcessing() {
    const canvas = this.renderer.domElement;
    const ctx = canvas.getContext('2d');
    this._postProcessCanvas = document.createElement('canvas');
    this._postProcessCanvas.width = canvas.width;
    this._postProcessCanvas.height = canvas.height;
  }

  // === VIGNETTE EFFECT ===
  _drawVignette(w, h) {
    if (!this._postProcessCanvas) return;
    const ctx = this._postProcessCanvas.getContext('2d');
    ctx.drawImage(this.renderer.domElement, 0, 0);
    const gradient = ctx.createRadialGradient(w/2, h/2, w*0.3, w/2, h/2, w*0.7);
    gradient.addColorStop(0, 'rgba(0,0,0,0)');
    gradient.addColorStop(1, 'rgba(0,0,0,0.4)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, w, h);
  }

  // === BLOOM PASS SIMULATION ===
  _applyBloom(intensity = 0.5) {
    if (!this.renderer || !this.renderer.domElement) return;
    const canvas = this.renderer.domElement;
    const ctx = canvas.getContext('2d');
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imageData.data;
    for (let i = 0; i < data.length; i += 4) {
      const brightness = (data[i] + data[i+1] + data[i+2]) / 3;
      if (brightness > 128) {
        data[i] = Math.min(255, data[i] + brightness * intensity);
        data[i+1] = Math.min(255, data[i+1] + brightness * intensity);
        data[i+2] = Math.min(255, data[i+2] + brightness * intensity);
      }
    }
    ctx.putImageData(imageData, 0, 0);
  }

  // === COLOR CORRECTION ===
  _colorCorrection(temperature = 0.1) {
    if (!this.renderer || !this.renderer.domElement) return;
    const canvas = this.renderer.domElement;
    const ctx = canvas.getContext('2d');
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imageData.data;
    for (let i = 0; i < data.length; i += 4) {
      data[i] = Math.max(0, Math.min(255, data[i] + temperature * 20));
      data[i+2] = Math.max(0, Math.min(255, data[i+2] - temperature * 10));
    }
    ctx.putImageData(imageData, 0, 0);
  }

  // === CHROMATIC ABERRATION ===
  _chromaticAberration(offset = 2) {
    if (!this.renderer || !this.renderer.domElement) return;
    const canvas = this.renderer.domElement;
    const ctx = canvas.getContext('2d');
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imageData.data;
    const shifted = ctx.getImageData(offset, 0, canvas.width - offset, canvas.height);
    for (let i = 0; i < data.length; i += 4) {
      if (i + 4 < data.length) data[i] = shifted.data[i]; // R channel shifted
    }
    ctx.putImageData(imageData, 0, 0);
  }

  // === MOTION BLUR SIMULATION ===
  _motionBlur(intensity = 0.1) {
    if (!this.renderer || !this.renderer.domElement) return;
    const canvas = this.renderer.domElement;
    const ctx = canvas.getContext('2d');
    ctx.globalAlpha = intensity;
    ctx.drawImage(canvas, -1, 0);
    ctx.drawImage(canvas, 1, 0);
    ctx.drawImage(canvas, 0, -1);
    ctx.drawImage(canvas, 0, 1);
    ctx.globalAlpha = 1.0;
  }

  // === PARTICLE TRAIL EFFECT ===
  _updateParticleTrails(t) {
    const positions = this.particles.geometry.attributes.position.array;
    const count = positions.length / 3;
    const trailPositions = new Float32Array(count * 6);
    for (let i = 0; i < count; i++) {
      const ix = i * 3;
      trailPositions[i*6] = positions[ix];
      trailPositions[i*6+1] = positions[ix+1];
      trailPositions[i*6+2] = positions[ix+2];
      trailPositions[i*6+3] = positions[ix] * 0.95;
      trailPositions[i*6+4] = positions[ix+1] * 0.95;
      trailPositions[i*6+5] = positions[ix+2] * 0.95;
    }
    return trailPositions;
  }

  // === AUDIO VISUALIZATION IN 3D ===
  _audioVisualize3D() {
    if (this.audioLevel <= 0) return;
    const scale = 1 + this.audioLevel * 0.3;
    this.core.scale.multiplyScalar(scale);
    this.pointLights.forEach(pl => {
      pl.intensity += this.audioLevel * 0.5;
    });
  }

  // === MOUSE HOVER 3D EFFECT ===
  _hoverEffect() {
    if (this.isHover) {
      this.core.material.emissiveIntensity += 0.02;
      this.core.scale.lerp(new THREE.Vector3(1.15, 1.15, 1.15), 0.05);
    } else {
      this.core.material.emissiveIntensity *= 0.95;
      this.core.scale.lerp(new THREE.Vector3(1, 1, 1), 0.05);
    }
  }

  // === GRID FLOOR EFFECT ===
  _createGridFloor() {
    const gridHelper = new THREE.GridHelper(10, 20, 0x00ff88, 0x0a0e27);
    gridHelper.position.y = -3;
    gridHelper.material.opacity = 0.1;
    gridHelper.material.transparent = true;
    this.scene.add(gridHelper);
  }

  // === EXPLOSION PARTICLES ===
  _createExplosion() {
    const count = 500;
    const positions = new Float32Array(count * 3);
    const velocities = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const c1 = new THREE.Color(0x00ff88);
    const c2 = new THREE.Color(0xff006e);
    for (let i = 0; i < count; i++) {
      positions[i*3] = 0; positions[i*3+1] = 0; positions[i*3+2] = 0;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const speed = Math.random() * 0.1 + 0.02;
      velocities[i*3] = Math.sin(phi) * Math.cos(theta) * speed;
      velocities[i*3+1] = Math.sin(phi) * Math.sin(theta) * speed;
      velocities[i*3+2] = Math.cos(phi) * speed;
      const t = Math.random();
      const c = c1.clone().lerp(c2, t);
      colors[i*3] = c.r; colors[i*3+1] = c.g; colors[i*3+2] = c.b;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const mat = new THREE.PointsMaterial({
      size: 0.1, vertexColors: true, transparent: true, opacity: 1.0,
      blending: THREE.AdditiveBlending,
    });
    const explosion = new THREE.Points(geo, mat);
    this.scene.add(explosion);
    let frame = 0;
    const animateExplosion = () => {
      if (frame > 60) { this.scene.remove(explosion); return; }
      const pos = explosion.geometry.attributes.position.array;
      for (let i = 0; i < count; i++) {
        pos[i*3] += velocities[i*3];
        pos[i*3+1] += velocities[i*3+1];
        pos[i*3+2] += velocities[i*3+2];
        velocities[i*3] *= 0.96;
        velocities[i*3+1] *= 0.96;
        velocities[i*3+2] *= 0.96;
      }
      explosion.geometry.attributes.position.needsUpdate = true;
      explosion.material.opacity = Math.max(0, 1.0 - frame / 60);
      frame++;
      requestAnimationFrame(animateExplosion);
    };
    animateExplosion();
  }

  // === ENVIRONMENT REFLECTION SIMULATION ===
  _createEnvironmentMap() {
    const envScene = new THREE.Scene();
    const envGeo = new THREE.SphereGeometry(50, 32, 32);
    const envColors = [0x00ff88, 0x00d9ff, 0xff006e, 0xffd600];
    const envMats = envColors.map(color => new THREE.MeshBasicMaterial({ color, side: THREE.BackSide }));
    const positions = [
      [50, 0, 0], [-50, 0, 0], [0, 50, 0], [0, -50, 0], [0, 0, 50], [0, 0, -50],
    ];
    positions.forEach((pos, i) => {
      const mesh = new THREE.Mesh(envGeo, envMats[i % envMats.length]);
      mesh.position.set(...pos);
      envScene.add(mesh);
    });
    this.envMap = envScene;
  }

  // === RESIZE HANDLER ===
  _onResize() {
    const container = document.getElementById(this.containerId);
    if (container) {
      const rect = container.getBoundingClientRect();
      this.camera.aspect = rect.width / rect.height;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(rect.width, rect.height);
    }
  }
}

if (typeof window !== 'undefined') {
  window.AriaCoreExtreme = AriaCoreExtreme;
}
