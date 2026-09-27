import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import type { OrbPhase } from '../../hooks/useOrbState'
import { EffectComposer } from 'three-stdlib'
import { RenderPass } from 'three-stdlib'
import { UnrealBloomPass } from 'three-stdlib'

/** Colores por estado — Gran Sabio / Raphael / Ciel inspired palette */
const PHASE_COLORS: Record<OrbPhase, { core: string; glow: string; fractal: string }> = {
  idle: { core: '#38bdf8', glow: '#0284c7', fractal: '#1e40af' },
  thinking: { core: '#f59e0b', glow: '#b45309', fractal: '#7c2d12' },
  responding: { core: '#00d4ff', glow: '#0e7490', fractal: '#083344' },
  listening: { core: '#b066ff', glow: '#7c3aed', fractal: '#311b92' },
  wisdom: { core: '#ffffff', glow: '#a78bfa', fractal: '#4c1d99' },
}

const PARTICLE_COUNT = 12
const BREATH_PERIOD = 1.5
const PULSE_PERIOD = 2.0
const FRACTAL_LAYERS = 4  // Anillos concéntricos del Gran Sabio
const DATA_STREAM_COUNT = 24  // Partículas de datos que fluyen al núcleo

interface LayerConfig {
  radius: number
  opacity: number
  intensity: number
  speed: [number, number, number]
}

/** 7 capas: núcleo + 6 halos fresnel con rotación propia */
const LAYERS: LayerConfig[] = [
  { radius: 0.5, opacity: 0.98, intensity: 0.55, speed: [0.1, 0.26, 0.04] },
  { radius: 0.6, opacity: 0.72, intensity: 0.85, speed: [-0.16, 0.2, 0.08] },
  { radius: 0.72, opacity: 0.52, intensity: 1.1, speed: [0.22, -0.18, -0.06] },
  { radius: 0.86, opacity: 0.38, intensity: 1.35, speed: [-0.12, 0.14, 0.1] },
  { radius: 1.02, opacity: 0.26, intensity: 1.6, speed: [0.18, -0.1, 0.05] },
  { radius: 1.2, opacity: 0.16, intensity: 1.85, speed: [-0.08, 0.12, -0.07] },
  { radius: 1.42, opacity: 0.1, intensity: 2.1, speed: [0.06, 0.08, 0.03] },
]

const VERTEX_SHADER = `
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vView = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`

const FRAGMENT_SHADER = `
  uniform vec3 uColor;
  uniform vec3 uGlow;
  uniform float uIntensity;
  uniform float uOpacity;
  varying vec3 vNormal;
  varying vec3 vView;
  void main() {
    float facing = abs(dot(normalize(vNormal), normalize(vView)));
    float fres = pow(1.0 - facing, 2.2);
    vec3 col = mix(uGlow, uColor, facing);
    col += uColor * fres * uIntensity;
    float alpha = uOpacity * (0.25 + 0.75 * fres);
    gl_FragColor = vec4(col, clamp(alpha, 0.0, 1.0));
  }
`

/** Shader fractal inspirado en el ojo del Gran Sabio — patrón infinitamente detallado */
const FRACTAL_FRAGMENT_SHADER = `
  uniform vec3 uFractalColor;
  uniform float uTime;
  uniform float uPulse;
  varying vec3 vNormal;
  varying vec3 vView;
  varying vec3 vPosition;
  
  void main() {
    float facing = abs(dot(normalize(vNormal), normalize(vView)));
    float fres = pow(1.0 - facing, 1.5);
    
    // Coordenadas fractales en la esfera
    vec2 uv = vec2(
      atan(vPosition.z, vPosition.x) / (3.14159 * 2.0),
      acos(vPosition.y / length(vPosition)) / 3.14159
    );
    
    // Patrón de ojo — espiral logarítmica infinita
    float angle = uTime * 0.3 + uv.x * 3.14159 * 4.0;
    float spiral = sin(length(vPosition) * 12.0 - angle) * cos(uv.y * 3.14159 * 6.0);
    
    // Efecto de iris pulsante
    float iris = 0.7 + 0.3 * sin(uTime * 2.0) * uPulse;
    float depth = pow(spiral * 0.5 + 0.5, 5.0) * iris;
    
    vec3 col = uFractalColor * (0.4 + 0.6 * depth * fres);
    float alpha = 0.75 * (0.3 + 0.7 * depth) * (0.2 + 0.8 * fres);
    gl_FragColor = vec4(col, alpha);
  }
`

/** Textura radial (sprite de partícula / halo suave) generada en canvas */
function radialTexture(size = 128, power = 2.2): THREE.Texture {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  if (ctx) {
    const half = size / 2
    const gradient = ctx.createRadialGradient(half, half, 0, half, half, half)
    gradient.addColorStop(0, 'rgba(255,255,255,1)')
    gradient.addColorStop(0.35 / power, 'rgba(255,255,255,0.55)')
    gradient.addColorStop(0.75, 'rgba(255,255,255,0.12)')
    gradient.addColorStop(1, 'rgba(255,255,255,0)')
    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, size, size)
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.needsUpdate = true
  return texture
}

interface OrbLayer {
  mesh: THREE.Mesh
  material: THREE.ShaderMaterial
  speed: THREE.Vector3
  opacity: number
}

interface Particle {
  radius: number
  speed: number
  phase: number
  tilt: number
  height: number
}

interface PulseRing {
  mesh: THREE.Mesh
  material: THREE.MeshBasicMaterial
  offset: number
}

/** Partículas de dato que fluyen hacia el núcleo (inspirado en Ciel) */
interface DataStream {
  geometry: THREE.BufferGeometry
  material: THREE.LineBasicMaterial
  positions: Float32Array
  speeds: number[]
}

/** Anillos concéntricos que representan capas de conocimiento (Gran Sabio) */
interface FractalRing {
  mesh: THREE.Mesh
  material: THREE.ShaderMaterial
}

interface Burst {
  lines: THREE.LineSegments
  material: THREE.LineBasicMaterial
  life: number
}

/** Escena Three.js autocontenida: capas, partículas, anillos y bursts */
  class OrbScene {
    public renderer: THREE.WebGLRenderer
    public scene: THREE.Scene
    public camera: THREE.PerspectiveCamera
    private host: HTMLElement
    private clock = new THREE.Clock()
    private raf = 0
    private observer: ResizeObserver | null = null
    private layers: OrbLayer[] = []
    private particles: Particle[] = []
    private points: THREE.Points
    private pointPositions: Float32Array
    private rings: PulseRing[] = []
    private bursts: Burst[] = []
    private glowSprite: THREE.Sprite
    private dataStreams: DataStream[] = []
    private fractalRings: FractalRing[] = []
    private targetCore = new THREE.Color(PHASE_COLORS.idle.core)
    private targetGlow = new THREE.Color(PHASE_COLORS.idle.glow)
    private targetFractal = new THREE.Color(PHASE_COLORS.idle.fractal)
    private currentCore = new THREE.Color(PHASE_COLORS.idle.core)
    private currentGlow = new THREE.Color(PHASE_COLORS.idle.glow)
    private currentFractal = new THREE.Color(PHASE_COLORS.idle.fractal)
    private animated = true
    private phase: OrbPhase = 'idle'

    constructor(host: HTMLElement) {
      this.host = host
      this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
      this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
      this.renderer.setClearColor(0x000000, 0)
      this.host.appendChild(this.renderer.domElement)

      this.scene = new THREE.Scene()
      this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100)
      this.camera.position.set(0, 0, 3.6)

    for (const cfg of LAYERS) {
      const geometry = new THREE.SphereGeometry(cfg.radius, 48, 48)
      const material = new THREE.ShaderMaterial({
        uniforms: {
          uColor: { value: this.currentCore.clone() },
          uGlow: { value: this.currentGlow.clone() },
          uIntensity: { value: cfg.intensity },
          uOpacity: { value: cfg.opacity },
        },
        vertexShader: VERTEX_SHADER,
        fragmentShader: FRAGMENT_SHADER,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      })
      const mesh = new THREE.Mesh(geometry, material)
      this.scene.add(mesh)
      this.layers.push({ mesh, material, speed: new THREE.Vector3(...cfg.speed), opacity: cfg.opacity })
    }

    this.glowSprite = this.createGlowSprite()
    this.points = this.createParticles()
    this.pointPositions = (this.points.geometry.getAttribute('position') as THREE.BufferAttribute)
      .array as Float32Array
    this.createPulseRings()
    this.createDataStreams()
    this.createFractalRings()

    this.resize()
    this.observer = new ResizeObserver(() => this.resize())
    this.observer.observe(this.host)
    this.animate()
  }

  private createGlowSprite(): THREE.Sprite {
    const material = new THREE.SpriteMaterial({
      map: radialTexture(256, 1.6),
      color: this.currentCore.clone(),
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      opacity: 0.55,
    })
    const sprite = new THREE.Sprite(material)
    sprite.scale.set(3.6, 3.6, 1)
    this.scene.add(sprite)
    return sprite
  }

  private createParticles(): THREE.Points {
    const positions = new Float32Array(PARTICLE_COUNT * 3)
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      this.particles.push({
        radius: 1.15 + (i % 4) * 0.22,
        speed: 0.35 + (i % 5) * 0.14,
        phase: (i / PARTICLE_COUNT) * Math.PI * 2,
        tilt: 0.35 + (i % 3) * 0.28,
        height: ((i % 5) - 2) * 0.12,
      })
    }
    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    const material = new THREE.PointsMaterial({
      size: 0.13,
      map: radialTexture(64, 2.4),
      color: this.currentCore.clone(),
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      sizeAttenuation: true,
    })
    const points = new THREE.Points(geometry, material)
    points.frustumCulled = false
    this.scene.add(points)
    return points
  }

  private createPulseRings(): void {
    for (let i = 0; i < 2; i++) {
      const geometry = new THREE.RingGeometry(0.98, 1.02, 128)
      const material = new THREE.MeshBasicMaterial({
        color: this.currentCore.clone(),
        transparent: true,
        opacity: 0,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        depthWrite: false,
      })
      const mesh = new THREE.Mesh(geometry, material)
      this.scene.add(mesh)
      this.rings.push({ mesh, material, offset: (i * PULSE_PERIOD) / 2 })
    }
  }

  /** 24 partículas de datos que fluyen espiralmente hacia el núcleo (inspirado en Ciel) */
  private createDataStreams(): void {
    for (let i = 0; i < DATA_STREAM_COUNT; i++) {
      const positions = new Float32Array(6)
      const angle = (i / DATA_STREAM_COUNT) * Math.PI * 2
      const radius = 1.5 + (i % 5) * 0.3
      const x = Math.cos(angle) * radius
      const z = Math.sin(angle) * radius
      const y = 0

      positions.set([x, y, z, x * 0.5, y * 0.5, z * 0.5])

      const geometry = new THREE.BufferGeometry()
      geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))

      const material = new THREE.LineBasicMaterial({
        color: this.currentCore.clone(),
        transparent: true,
        opacity: 0.4,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      })

      const line = new THREE.LineSegments(geometry, material)
      this.scene.add(line)

      this.dataStreams.push({
        geometry,
        material,
        positions,
        speeds: [0.3 + (i % 3) * 0.2],
      })
    }
  }

  /** Anillos concéntricos fractales que representan capas de conocimiento (Gran Sabio) */
  private createFractalRings(): void {
    for (let i = 0; i < FRACTAL_LAYERS; i++) {
      const ringRadius = 0.5 + i * 0.35
      const geometry = new THREE.RingGeometry(ringRadius - 0.03, ringRadius + 0.03, 128)
      const material = new THREE.ShaderMaterial({
        uniforms: {
          uFractalColor: { value: this.currentFractal.clone() },
          uTime: { value: 0 },
          uPulse: { value: 0 },
        },
        vertexShader: VERTEX_SHADER,
        fragmentShader: FRACTAL_FRAGMENT_SHADER,
        transparent: true,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        depthWrite: false,
        depthTest: false,
      })

      const mesh = new THREE.Mesh(geometry, material)
      mesh.rotation.x = (i * Math.PI) / FRACTAL_LAYERS
      mesh.rotation.z = (i * Math.PI) / (FRACTAL_LAYERS * 2)
      this.scene.add(mesh)
      this.fractalRings.push({ mesh, material })
    }
  }

  /** Rayos radiales que salen del orbe al hablar/pensar */
  private spawnBurst(): void {
    const count = 28
    const positions = new Float32Array(count * 6)
    for (let i = 0; i < count; i++) {
      const y = 1 - (i / (count - 1)) * 2
      const r = Math.sqrt(Math.max(0, 1 - y * y))
      const theta = Math.PI * (1 + Math.sqrt(5)) * i
      const dx = Math.cos(theta) * r
      const dz = Math.sin(theta) * r
      const inner = 1.05
      const outer = 1.35 + (i % 4) * 0.12
      positions.set([dx * inner, y * inner, dz * inner, dx * outer, y * outer, dz * outer], i * 6)
    }
    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    const material = new THREE.LineBasicMaterial({
      color: this.currentCore.clone(),
      transparent: true,
      opacity: 0.9,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    const lines = new THREE.LineSegments(geometry, material)
    this.scene.add(lines)
    this.bursts.push({ lines, material, life: 1 })
  }

  setPhase(phase: OrbPhase): void {
    if (phase === this.phase) return
    const previous = this.phase
    this.phase = phase
    this.targetCore.set(PHASE_COLORS[phase].core)
    this.targetGlow.set(PHASE_COLORS[phase].glow)
    this.targetFractal.set(PHASE_COLORS[phase].fractal)
    if (previous !== phase && (phase === 'thinking' || phase === 'responding')) this.spawnBurst()
  }

  setAnimated(animated: boolean): void {
    this.animated = animated
  }

  private resize(): void {
    const width = this.host.clientWidth || 320
    const height = this.host.clientHeight || 320
    this.renderer.setSize(width, height, false)
    this.camera.aspect = width / height
    this.camera.updateProjectionMatrix()
  }

  private animate = (): void => {
    this.raf = requestAnimationFrame(this.animate)
    const dt = Math.min(this.clock.getDelta(), 0.05)
    const t = this.clock.elapsedTime
    const motion = this.animated ? 1 : 0

    // Transición suave de color entre estados
    this.currentCore.lerp(this.targetCore, 1 - Math.pow(0.0015, dt))
    this.currentGlow.lerp(this.targetGlow, 1 - Math.pow(0.0015, dt))
    this.currentFractal.lerp(this.targetFractal, 1 - Math.pow(0.0025, dt))

    // Respiración (ciclo 1.5s)
    const breathe = 1 + Math.sin((t / BREATH_PERIOD) * Math.PI * 2) * 0.045 * motion
    this.scene.scale.setScalar(breathe)

    for (const layer of this.layers) {
      layer.mesh.rotation.x += layer.speed.x * dt * motion
      layer.mesh.rotation.y += layer.speed.y * dt * motion
      layer.mesh.rotation.z += layer.speed.z * dt * motion
      const uniforms = layer.material.uniforms
      ;(uniforms.uColor.value as THREE.Color).copy(this.currentCore)
      ;(uniforms.uGlow.value as THREE.Color).copy(this.currentGlow)
      const pulse = 0.92 + 0.08 * Math.sin((t / BREATH_PERIOD) * Math.PI * 2 + layer.mesh.rotation.y)
      uniforms.uOpacity.value = layer.opacity * pulse
    }

    const glowMaterial = this.glowSprite.material as THREE.SpriteMaterial
    glowMaterial.color.copy(this.currentCore)
    glowMaterial.opacity = 0.45 + 0.18 * Math.sin((t / BREATH_PERIOD) * Math.PI * 2) * motion

    // 12 partículas en órbita continua
    for (let i = 0; i < this.particles.length; i++) {
      const p = this.particles[i]
      const angle = p.phase + t * p.speed * (this.animated ? 1 : 0.02)
      const x = Math.cos(angle) * p.radius
      const z = Math.sin(angle) * p.radius
      const y = Math.sin(angle * 1.4 + p.phase) * p.tilt * 0.45 + p.height
      this.pointPositions[i * 3] = x
      this.pointPositions[i * 3 + 1] = y
      this.pointPositions[i * 3 + 2] = z
    }
    const positionAttribute = this.points.geometry.getAttribute('position') as THREE.BufferAttribute
    positionAttribute.needsUpdate = true
    ;(this.points.material as THREE.PointsMaterial).color.copy(this.currentCore)

    // Anillos de pulso expandiéndose cada 2s
    for (const ring of this.rings) {
      const cycle = ((t + ring.offset) % PULSE_PERIOD) / PULSE_PERIOD
      ring.mesh.scale.setScalar(1 + cycle * 1.1)
      ring.material.opacity = motion ? Math.max(0, 0.6 * (1 - cycle)) : 0
      ring.material.color.copy(this.currentCore)
    }

    // Rayos burst (se desvanecen hacia afuera)
    for (let i = this.bursts.length - 1; i >= 0; i--) {
      const burst = this.bursts[i]
      burst.life -= dt / 0.85
      if (burst.life <= 0) {
        this.scene.remove(burst.lines)
        burst.lines.geometry.dispose()
        burst.material.dispose()
        this.bursts.splice(i, 1)
        continue
      }
      const progress = 1 - burst.life
      burst.lines.scale.setScalar(1 + progress * 0.9)
      burst.material.opacity = burst.life * 0.9
      burst.material.color.copy(this.currentCore)
    }

    // Partículas de datos fluyendo espiralmente (inspirado en Ciel)
    for (const stream of this.dataStreams) {
      const speed = stream.speeds[0] * motion
      const pos = stream.positions
      const angle = t * speed
      const r = Math.sqrt(pos[0] * pos[0] + pos[2] * pos[2])
      const theta = Math.atan2(pos[2], pos[0]) + angle
      pos[0] = Math.cos(theta) * r * (0.5 + 0.5 * Math.sin(t + speed))
      pos[2] = Math.sin(theta) * r * (0.5 + 0.5 * Math.sin(t + speed))
      pos[1] = Math.sin(angle * 2) * 0.3
      ;(stream.geometry.getAttribute('position') as THREE.BufferAttribute).needsUpdate = true
      ;(stream.material as THREE.LineBasicMaterial).color.copy(this.currentCore)
    }

    // Anillos fractales girando y pulsando (Gran Sabio)
    for (let i = 0; i < this.fractalRings.length; i++) {
      const ring = this.fractalRings[i]
      ring.mesh.rotation.x += 0.05 * dt * motion
      ring.mesh.rotation.z += 0.03 * dt * motion
      const uniforms = ring.material.uniforms
      ;(uniforms.uTime.value as any) = t
      ;(uniforms.uPulse.value as any) = 0.7 + 0.3 * Math.sin(t * 1.3 + i)
      ;(uniforms.uFractalColor.value as THREE.Color).copy(this.currentFractal)
    }

    this.renderer.render(this.scene, this.camera)
  }

  /** Actualiza la animación (llamado desde el bucle de render externo) */
  update(): void {
    const dt = Math.min(this.clock.getDelta(), 0.05)
    const t = this.clock.elapsedTime
    const motion = this.animated ? 1 : 0

    // Transición suave de color entre estados
    this.currentCore.lerp(this.targetCore, 1 - Math.pow(0.0015, dt))
    this.currentGlow.lerp(this.targetGlow, 1 - Math.pow(0.0015, dt))
    this.currentFractal.lerp(this.targetFractal, 1 - Math.pow(0.0025, dt))

    // Respiración (ciclo 1.5s)
    const breathe = 1 + Math.sin((t / BREATH_PERIOD) * Math.PI * 2) * 0.045 * motion
    this.scene.scale.setScalar(breathe)

    for (const layer of this.layers) {
      layer.mesh.rotation.x += layer.speed.x * dt * motion
      layer.mesh.rotation.y += layer.speed.y * dt * motion
      layer.mesh.rotation.z += layer.speed.z * dt * motion
      const uniforms = layer.material.uniforms
      ;(uniforms.uColor.value as THREE.Color).copy(this.currentCore)
      ;(uniforms.uGlow.value as THREE.Color).copy(this.currentGlow)
      const pulse = 0.92 + 0.08 * Math.sin((t / BREATH_PERIOD) * Math.PI * 2 + layer.mesh.rotation.y)
      uniforms.uOpacity.value = layer.opacity * pulse
    }

    const glowMaterial = this.glowSprite.material as THREE.SpriteMaterial
    glowMaterial.color.copy(this.currentCore)
    glowMaterial.opacity = 0.45 + 0.18 * Math.sin((t / BREATH_PERIOD) * Math.PI * 2) * motion

    // 12 partículas en órbita continua
    for (let i = 0; i < this.particles.length; i++) {
      const p = this.particles[i]
      const angle = p.phase + t * p.speed * (this.animated ? 1 : 0.02)
      const x = Math.cos(angle) * p.radius
      const z = Math.sin(angle) * p.radius
      const y = Math.sin(angle * 1.4 + p.phase) * p.tilt * 0.45 + p.height
      this.pointPositions[i * 3] = x
      this.pointPositions[i * 3 + 1] = y
      this.pointPositions[i * 3 + 2] = z
    }
    const positionAttribute = this.points.geometry.getAttribute('position') as THREE.BufferAttribute
    positionAttribute.needsUpdate = true
    ;(this.points.material as THREE.PointsMaterial).color.copy(this.currentCore)

    // Anillos de pulso expandiéndose cada 2s
    for (const ring of this.rings) {
      const cycle = ((t + ring.offset) % PULSE_PERIOD) / PULSE_PERIOD
      ring.mesh.scale.setScalar(1 + cycle * 1.1)
      ring.material.opacity = motion ? Math.max(0, 0.6 * (1 - cycle)) : 0
      ring.material.color.copy(this.currentCore)
    }

    // Rayos burst (se desvanecen hacia afuera)
    for (let i = this.bursts.length - 1; i >= 0; i--) {
      const burst = this.bursts[i]
      burst.life -= dt / 0.85
      if (burst.life <= 0) {
        this.scene.remove(burst.lines)
        burst.lines.geometry.dispose()
        burst.material.dispose()
        this.bursts.splice(i, 1)
        continue
      }
      const progress = 1 - burst.life
      burst.lines.scale.setScalar(1 + progress * 0.9)
      burst.material.opacity = burst.life * 0.9
      burst.material.color.copy(this.currentCore)
    }

    // Partículas de datos fluyendo espiralmente (inspirado en Ciel)
    for (const stream of this.dataStreams) {
      const speed = stream.speeds[0] * motion
      const pos = stream.positions
      const angle = t * speed
      const r = Math.sqrt(pos[0] * pos[0] + pos[2] * pos[2])
      const theta = Math.atan2(pos[2], pos[0]) + angle
      pos[0] = Math.cos(theta) * r * (0.5 + 0.5 * Math.sin(t + speed))
      pos[2] = Math.sin(theta) * r * (0.5 + 0.5 * Math.sin(t + speed))
      pos[1] = Math.sin(angle * 2) * 0.3
      ;(stream.geometry.getAttribute('position') as THREE.BufferAttribute).needsUpdate = true
      ;(stream.material as THREE.LineBasicMaterial).color.copy(this.currentCore)
    }

    // Anillos fractales girando y pulsando (Gran Sabio)
    for (let i = 0; i < this.fractalRings.length; i++) {
      const ring = this.fractalRings[i]
      ring.mesh.rotation.x += 0.05 * dt * motion
      ring.mesh.rotation.z += 0.03 * dt * motion
      const uniforms = ring.material.uniforms
      ;(uniforms.uTime.value as any) = t
      ;(uniforms.uPulse.value as any) = 0.7 + 0.3 * Math.sin(t * 1.3 + i)
      ;(uniforms.uFractalColor.value as THREE.Color).copy(this.currentFractal)
    }
  }

  dispose(): void {
    cancelAnimationFrame(this.raf)
    this.observer?.disconnect()
    this.observer = null

    for (const burst of this.bursts) {
      this.scene.remove(burst.lines)
      burst.lines.geometry.dispose()
      burst.material.dispose()
    }
    this.bursts = []

    this.scene.traverse((object) => {
      const mesh = object as THREE.Mesh
      if (mesh.geometry) mesh.geometry.dispose()
      const material = mesh.material as THREE.Material | THREE.Material[] | undefined
      if (Array.isArray(material)) material.forEach((item) => item.dispose())
      else if (material) material.dispose()
    })

    this.renderer.dispose()
    const canvas = this.renderer.domElement
    if (canvas.parentNode === this.host) this.host.removeChild(canvas)
  }
}

export interface OrbVisualProps {
  phase: OrbPhase
  animated?: boolean
}

/**
 * Orbe 3D: 7 capas fresnel + 12 partículas orbitales + anillos de pulso (2s)
 * + rayos burst en thinking/responding. Render WebGL a 60fps.
 */
export function OrbVisual({ phase, animated = true }: OrbVisualProps) {
  const hostRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<OrbScene | null>(null)
  const composerRef = useRef<EffectComposer | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const scene = new OrbScene(host)
    sceneRef.current = scene
    setReady(true)
    return () => {
      scene.dispose()
      sceneRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!sceneRef.current || !ready) return
    const renderer = sceneRef.current.renderer
    const scene = sceneRef.current.scene
    const camera = sceneRef.current.camera
    const composer = new EffectComposer(renderer)
    composer.setSize(window.innerWidth, window.innerHeight)
    const renderPass = new RenderPass(scene, camera)
    composer.addPass(renderPass)
    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(window.innerWidth, window.innerHeight),
      1.5, 0.4, 0.85
    )
    composer.addPass(bloomPass)
    composerRef.current = composer
    const handleResize = () => composer.setSize(window.innerWidth, window.innerHeight)
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      composer.dispose()
      composerRef.current = null
    }
  }, [ready])

  useEffect(() => {
    sceneRef.current?.setPhase(phase)
  }, [phase])

  useEffect(() => {
    sceneRef.current?.setAnimated(animated)
  }, [animated])

  // Animation loop using composer
  useEffect(() => {
    if (!ready) return
    const animate = () => {
      requestAnimationFrame(animate)
      if (sceneRef.current) {
        sceneRef.current.update()
      }
      if (composerRef.current) {
        composerRef.current.render()
      } else if (sceneRef.current) {
        sceneRef.current.renderer.render(sceneRef.current.scene, sceneRef.current.camera)
      }
    }
    animate()
  }, [ready])

  return <div ref={hostRef} className="orb-canvas" aria-hidden="true" />
}

