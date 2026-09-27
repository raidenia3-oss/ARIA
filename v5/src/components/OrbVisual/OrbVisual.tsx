import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import type { OrbPhase } from '../../hooks/useOrbState'
import { EffectComposer } from 'three-stdlib'
import { RenderPass } from 'three-stdlib'
import { UnrealBloomPass } from 'three-stdlib'

/**
 * ARIA v6.0 - Gran Sabio Core Visual
 * 
 * Inspirado en el Gran Sabio / Raphael / Ciel de Tensura
 * 
 * Elementos visuales:
 * 1. Ojo fractal infinito — "El que ve todo"
 * 2. Partículas de datos en espiral de Fibonacci — Conocimiento infinito
 * 3. Capas concéntricas de evolución — Evolución del Gran Sabio → Raphael → Ciel
 * 4. Infons (partículas de energía fundamental) — Manipulación de información
 * 5. Pulsos concéntricos Shinkirō — Onda de desafío del Gran Sabio
 * 6. Núcleo fractal Mandlebrot — Patrón infinitamente detallado
 */

const PHASE_COLORS: Record<OrbPhase, {
  core: string
  glow: string
  fractal: string
  eye: string
  infon: string
  evolution: string
}> = {
  idle: {
    core: '#38bdf8',
    glow: '#0284c7',
    fractal: '#1e40af',
    eye: '#60a5fa',
    infon: '#38bdf8',
    evolution: '#1e3a8a',
  },
  thinking: {
    core: '#f59e0b',
    glow: '#b45309',
    fractal: '#7c2d12',
    eye: '#fbbf24',
    infon: '#f59e0b',
    evolution: '#78350f',
  },
  responding: {
    core: '#00d4ff',
    glow: '#0e7490',
    fractal: '#083344',
    eye: '#67e8f4',
    infon: '#00d4ff',
    evolution: '#0c4a6e',
  },
  listening: {
    core: '#b066ff',
    glow: '#7c3aed',
    fractal: '#311b92',
    eye: '#c49afe',
    infon: '#b066ff',
    evolution: '#4c1d92',
  },
  wisdom: {
    core: '#ffffff',
    glow: '#a78bfa',
    fractal: '#4c1d99',
    eye: '#ffffff',
    infon: '#fbbf24',
    evolution: '#7e22ce',
  },
}

const PARTICLE_COUNT = 12
const BREATH_PERIOD = 1.5
const PULSE_PERIOD = 2.0
const FIBONACCI_COUNT = 89
const INFON_COUNT = 34
const EVOLUTION_RINGS = 3

interface LayerConfig {
  radius: number
  opacity: number
  intensity: number
  speed: [number, number, number]
}

const LAYERS: LayerConfig[] = [
  { radius: 0.5, opacity: 0.98, intensity: 0.55, speed: [0.1, 0.26, 0.04] },
  { radius: 0.6, opacity: 0.72, intensity: 0.85, speed: [-0.16, 0.2, 0.08] },
  { radius: 0.72, opacity: 0.52, intensity: 1.1, speed: [0.22, -0.18, -0.06] },
  { radius: 0.86, opacity: 0.38, intensity: 1.35, speed: [-0.12, 0.14, 0.1] },
  { radius: 1.02, opacity: 0.26, intensity: 1.6, speed: [0.18, -0.1, 0.05] },
  { radius: 1.2, opacity: 0.16, intensity: 1.85, speed: [-0.08, 0.12, -0.07] },
  { radius: 1.42, opacity: 0.1, intensity: 2.1, speed: [0.06, 0.08, 0.03] },
]

/** Shader del ojo fractal — patrón infinitamente detallado inspirado en el Gran Sabio */
const VERTEX_SHADER = `
  varying vec3 vNormal;
  varying vec3 vView;
  varying vec3 vPosition;
  void main() {
    vPosition = position;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vView = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`

/** Shader fractal del Gran Sabio — espiral logarítmica infinita (patrón de ojo) */
const FRACTAL_FRAGMENT_SHADER = `
  uniform vec3 uFractalColor;
  uniform vec3 uEyeColor;
  uniform float uTime;
  uniform float uPulse;
  uniform int uEvolutionPhase;
  varying vec3 vNormal;
  varying vec3 vView;
  varying vec3 vPosition;
  
  // Patrón de espiral de Fibonacci (conocimiento infinito)
  float spiral(vec2 p, float scale, float speed) {
    float r = length(p);
    float theta = atan(p.y, p.x) + uTime * speed;
    float spiral = sin(theta * scale - r * 12.0) * 0.5 + 0.5;
    return spiral;
  }
  
  void main() {
    float facing = abs(dot(normalize(vNormal), normalize(vView)));
    float fres = pow(1.0 - facing, 2.2);
    
    // Coordinadas esféricas para el patrón fractal
    vec2 uv = vec2(
      atan(vPosition.z, vPosition.x) / (3.14159 * 2.0) + 0.5,
      acos(clamp(vPosition.y / length(vPosition), -1.0, 1.0)) / 3.14159
    );
    
    // Ojo fractal central — patrón de espiral infinita
    float eye = spiral(vPosition.xy * 10.0, 8.0, 0.5);
    eye *= spiral(vPosition.yz * 8.0, 6.0, -0.3);
    eye *= (1.0 - length(vPosition.xy) * 0.3);
    
    // Evolución del conocimiento — capas concéntricas
    float r = length(vPosition);
    float evolution = sin(r * 30.0 - uTime * 2.0) * 0.5 + 0.5;
    evolution *= uPulse;
    
    // Combinar patrones
    float intensity = eye * 0.6 + evolution * 0.4;
    intensity *= fres * uPulse;
    
    vec3 col = mix(uFractalColor, uEyeColor, intensity);
    col += uEyeColor * intensity * 0.5;
    
    float alpha = intensity * (0.3 + 0.7 * fres);
    gl_FragColor = vec4(col, clamp(alpha, 0.0, 0.8));
  }
`


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

interface Infon {
  mesh: THREE.Sprite
  phase: number
  speed: number
  radius: number
}

interface EvolutionRing {
  mesh: THREE.Mesh
  material: THREE.MeshBasicMaterial
  geometry?: THREE.BufferGeometry
}

interface DataParticle {
  geometry: THREE.BufferGeometry
  material: THREE.ShaderMaterial
  count: number
}

/**
 * Orbe 3D del Gran Sabio:
 * - 7 capas fresnel con rotación propia
 * - Ojo fractal infinito en el núcleo
 * - 89 partículas en espiral de Fibonacci (conocimiento infinito)
 * - 34 infons fluyendo (energía fundamental)
 * - 3 anillos de evolución concentricos (Gran Sabio → Raphael → Ciel)
 * - 24 partículas orbitales
 * - Anillos de pulso con ondas Shinkirō
 */
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
  private points!: THREE.Points
  private pointPositions!: Float32Array
  private rings: PulseRing[] = []
  private bursts: Burst[] = []
  private infons: Infon[] = []
  private evolutionRings: EvolutionRing[] = []
  private dataParticles: DataParticle[] = []
  private fractalCore!: THREE.Mesh
  private fractalMaterial!: THREE.ShaderMaterial
  private targetCore = new THREE.Color(PHASE_COLORS.idle.core)
  private targetGlow = new THREE.Color(PHASE_COLORS.idle.glow)
  private targetEye = new THREE.Color(PHASE_COLORS.idle.eye)
  private targetFractal = new THREE.Color(PHASE_COLORS.idle.fractal)
  private currentCore = new THREE.Color(PHASE_COLORS.idle.core)
  private currentGlow = new THREE.Color(PHASE_COLORS.idle.glow)
  private currentEye = new THREE.Color(PHASE_COLORS.idle.eye)
  private currentFractal = new THREE.Color(PHASE_COLORS.idle.fractal)
  private animated = true
  private phase: OrbPhase = 'idle'

  constructor(host: HTMLElement) {
    this.host = host
    this.renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
    })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    this.renderer.setClearColor(0x000000, 0)
    this.renderer.outputEncoding = THREE.sRGBEncoding
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    this.host.appendChild(this.renderer.domElement)

    this.scene = new THREE.Scene()
    this.camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100)
    this.camera.position.set(0, 0, 4.2)

    this.setupLighting()
    this.createFractalCore()
    this.createLayers()
    this.createDataSpiral()
    this.createInfons()
    this.createEvolutionRings()
    this.createParticles()
    this.createPulseRings()

    this.resize()
    this.observer = new ResizeObserver(() => this.resize())
    this.observer.observe(this.host)
    this.animate()
  }

  private setupLighting(): void {
    const ambient = new THREE.AmbientLight(0x404040, 2)
    this.scene.add(ambient)
    const dirLight = new THREE.DirectionalLight(0xffffff, 1)
    dirLight.position.set(5, 5, 5)
    this.scene.add(dirLight)
  }

  /** Núcleo fractal: esfera con shader del Gran Sabio */
  private createFractalCore(): void {
    const geometry = new THREE.SphereGeometry(0.45, 128, 128)
    this.fractalMaterial = new THREE.ShaderMaterial({
      uniforms: {
        uFractalColor: { value: this.currentFractal.clone() },
        uEyeColor: { value: this.currentEye.clone() },
        uTime: { value: 0 },
        uPulse: { value: 1 },
        uEvolutionPhase: { value: 0 },
      },
      vertexShader: VERTEX_SHADER,
      fragmentShader: FRACTAL_FRAGMENT_SHADER,
      transparent: true,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
      depthWrite: false,
    })
    this.fractalCore = new THREE.Mesh(geometry, this.fractalMaterial)
    this.scene.add(this.fractalCore)
  }

  /** Capas fresnel con rotación */
  private createLayers(): void {
    for (const cfg of LAYERS) {
      const geometry = new THREE.SphereGeometry(cfg.radius, 64, 64)
      const material = new THREE.ShaderMaterial({
        uniforms: {
          uColor: { value: this.currentCore.clone() },
          uGlow: { value: this.currentGlow.clone() },
          uIntensity: { value: cfg.intensity },
          uOpacity: { value: cfg.opacity },
        },
        vertexShader: VERTEX_SHADER,
        fragmentShader: `
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
        `,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      })
      const mesh = new THREE.Mesh(geometry, material)
      this.scene.add(mesh)
      this.layers.push({ mesh, material, speed: new THREE.Vector3(...cfg.speed), opacity: cfg.opacity })
    }
  }

  /** Partículas orbitales (12) — el núcleo de conocimiento */
  private createParticles(): void {
    const positions = new Float32Array(PARTICLE_COUNT * 3)
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      this.particles.push({
        radius: 1.4 + (i % 4) * 0.22,
        speed: 0.35 + (i % 5) * 0.14,
        phase: (i / PARTICLE_COUNT) * Math.PI * 2,
        tilt: 0.35 + (i % 3) * 0.28,
        height: ((i % 5) - 2) * 0.12,
      })
    }
    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    const spriteTexture = radialTexture(64, 2.4)
    const material = new THREE.PointsMaterial({
      size: 0.12,
      map: spriteTexture,
      color: this.currentCore.clone(),
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      sizeAttenuation: true,
    })
    this.points = new THREE.Points(geometry, material)
    this.points.frustumCulled = false
    this.scene.add(this.points)
    this.pointPositions = positions
  }

  /** Anillos de pulso Shinkirō (ondas concéntricas) */
  private createPulseRings(): void {
    for (let i = 0; i < 3; i++) {
      const geometry = new THREE.RingGeometry(0.98, 1.05, 128)
      const material = new THREE.MeshBasicMaterial({
        color: this.currentCore.clone(),
        transparent: true,
        opacity: 0,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        depthWrite: false,
      })
      const mesh = new THREE.Mesh(geometry, material)
      mesh.rotation.x = Math.PI / 2
      this.scene.add(mesh)
      this.rings.push({ mesh, material, offset: (i * PULSE_PERIOD) / 3 })
    }
  }

  /** Partículas de datos en espiral de Fibonacci (89 = número de Fibonacci) */
  private createDataSpiral(): void {
    const positions = new Float32Array(FIBONACCI_COUNT * 3)
    const phases = new Float32Array(FIBONACCI_COUNT)
    
    for (let i = 0; i < FIBONACCI_COUNT; i++) {
      const phi = i * 2.399963 // Golden angle
      const scale = 0.8 + (i / FIBONACCI_COUNT) * 0.8
      const angle = phi
      const r = scale * 0.02
      
      positions[i * 3] = Math.cos(angle) * r
      positions[i * 3 + 1] = Math.sin(angle * 0.7) * r * 0.3
      positions[i * 3 + 2] = Math.sin(angle) * r
      
      phases[i] = i / FIBONACCI_COUNT
    }

    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    
    const material = new THREE.PointsMaterial({
      size: 0.06,
      map: radialTexture(32, 2.0),
      color: this.currentCore.clone(),
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      sizeAttenuation: true,
    })
    
    const pts = new THREE.Points(geometry, material)
    pts.frustumCulled = false
    this.scene.add(pts)
    this.dataParticles.push({ geometry, material: material as any, count: FIBONACCI_COUNT })
    
    // Store reference for animation
    ;(pts as any)._positions = positions
    ;(pts as any)._phases = phases
    ;(pts as any)._material = material
    ;(this.scene as any)._dataPoints = pts
  }

  /** Infons (partículas de energía fundamental) — 34 = número de Fibonacci */
  private createInfons(): void {
    const infonTexture = radialTexture(48, 1.8)
    
    for (let i = 0; i < INFON_COUNT; i++) {
      const material = new THREE.SpriteMaterial({
        map: infonTexture,
        color: this.currentCore.clone(),
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        opacity: 0.6,
      })
      
      const sprite = new THREE.Sprite(material)
      sprite.scale.set(0.08, 0.08, 1)
      
      const angle = (i / INFON_COUNT) * Math.PI * 2
      const radius = 1.5 + (i % 5) * 0.25
      
      sprite.position.set(
        Math.cos(angle) * radius,
        Math.sin(angle * 0.6) * radius * 0.2,
        Math.sin(angle) * radius
      )
      
      this.scene.add(sprite)
      this.infons.push({
        mesh: sprite,
        phase: (i / INFON_COUNT) * Math.PI * 2,
        speed: 0.3 + (i % 7) * 0.05,
        radius: radius,
      })
    }
  }

  /** Anillos de evolución concéntricos (Gran Sabio → Raphael → Ciel) */
  private createEvolutionRings(): void {
    for (let i = 0; i < EVOLUTION_RINGS; i++) {
      const ringRadius = 0.55 + i * 0.32
      const geometry = new THREE.RingGeometry(ringRadius - 0.04, ringRadius + 0.04, 256)
      
      const material = new THREE.MeshBasicMaterial({
        color: new THREE.Color(this.currentFractal).multiplyScalar(0.4 + i * 0.2),
        transparent: true,
        opacity: 0.15,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        depthWrite: false,
        depthTest: false,
      })
      
      const mesh = new THREE.Mesh(geometry, material)
      mesh.rotation.x = (i * Math.PI) / (EVOLUTION_RINGS * 2)
      mesh.rotation.y = (i * Math.PI) / EVOLUTION_RINGS
      this.scene.add(mesh)
      this.evolutionRings.push({ mesh, material: material as any })
    }
  }

  /** Rayos radiales que salen del orbe al hablar/pensar */
  private spawnBurst(): void {
    const count = 42
    const positions = new Float32Array(count * 6)
    for (let i = 0; i < count; i++) {
      const y = 1 - (i / (count - 1)) * 2
      const r = Math.sqrt(Math.max(0, 1 - y * y))
      const theta = Math.PI * (1 + Math.sqrt(5)) * i
      const dx = Math.cos(theta) * r
      const dz = Math.sin(theta) * r
      const inner = 1.05
      const outer = 1.5 + (i % 4) * 0.15
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
    this.targetEye.set(PHASE_COLORS[phase].eye)
    this.targetFractal.set(PHASE_COLORS[phase].fractal)
    if (previous !== phase && (phase === 'thinking' || phase === 'responding' || phase === 'wisdom')) {
      this.spawnBurst()
    }
  }

  setAnimated(animated: boolean): void {
    this.animated = animated
  }

  private resize(): void {
    const width = this.host.clientWidth || 360
    const height = this.host.clientHeight || 360
    this.renderer.setSize(width, height, false)
    this.camera.aspect = width / height
    this.camera.updateProjectionMatrix()
  }

  private animate = (): void => {
    this.raf = requestAnimationFrame(this.animate)
    const dt = Math.min(this.clock.getDelta(), 0.05)
    const t = this.clock.elapsedTime
    const motion = this.animated ? 1 : 0

    // Suave transición de color entre estados
    this.currentCore.lerp(this.targetCore, 1 - Math.pow(0.0015, dt))
    this.currentGlow.lerp(this.targetGlow, 1 - Math.pow(0.0015, dt))
    this.currentEye.lerp(this.targetEye, 1 - Math.pow(0.002, dt))
    this.currentFractal.lerp(this.targetFractal, 1 - Math.pow(0.0018, dt))

    // Respiración del Gran Sabio (ciclo 1.5s)
    const breathe = 1 + Math.sin((t / BREATH_PERIOD) * Math.PI * 2) * 0.035 * motion
    this.scene.scale.setScalar(breathe)

    // Capas con rotación propia
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

    // Núcleo fractal — ojo infinito
    const fractalUniforms = this.fractalMaterial.uniforms
    ;(fractalUniforms.uTime.value as number) = t
    ;(fractalUniforms.uPulse.value as number) = 0.7 + 0.3 * Math.sin(t * 1.3) * motion
    ;(fractalUniforms.uFractalColor.value as THREE.Color).copy(this.currentFractal)
    ;(fractalUniforms.uEyeColor.value as THREE.Color).copy(this.currentEye)
    ;(fractalUniforms.uEvolutionPhase.value as number) = this.phase === 'wisdom' ? 3 : this.phase === 'responding' ? 2 : 1

    // Partículas orbitales (12)
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

    // Anillos de pulso Shinkirō (ondas concéntricas)
    for (const ring of this.rings) {
      const cycle = ((t + ring.offset) % PULSE_PERIOD) / PULSE_PERIOD
      ring.mesh.scale.setScalar(1 + cycle * 1.4)
      ring.material.opacity = motion ? Math.max(0, 0.7 * (1 - cycle)) : 0
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

    // Partículas de datos en espiral de Fibonacci (89)
    const dataPoints = (this.scene as any)._dataPoints as THREE.Points | undefined
    if (dataPoints) {
      const pos = (dataPoints as any)._positions as Float32Array
      const phases = (dataPoints as any)._phases as Float32Array
      for (let i = 0; i < FIBONACCI_COUNT; i++) {
        const phi = t * 0.3 + phases[i] * Math.PI * 2
        const scale = 0.8 + (i / FIBONACCI_COUNT) * 0.8
        const r = scale * 0.02
        pos[i * 3] = Math.cos(phi) * r
        pos[i * 3 + 1] = Math.sin(phi * 0.7) * r * 0.3
        pos[i * 3 + 2] = Math.sin(phi) * r
      }
      dataPoints.geometry.attributes.position.needsUpdate = true
      ;(dataPoints.material as THREE.PointsMaterial).color.copy(this.currentCore)
      ;(dataPoints.material as THREE.PointsMaterial).opacity = 0.4 + 0.1 * Math.sin(t * 2 + phases[0])
    }

    // Infons (partículas de energía fundamental) — 34
    for (const infon of this.infons) {
      const angle = t * infon.speed + infon.phase
      const r = infon.radius * (0.9 + 0.1 * Math.sin(t + infon.phase))
      infon.mesh.position.set(
        Math.cos(angle) * r,
        Math.sin(angle * 0.6 + t) * r * 0.2,
        Math.sin(angle) * r
      )
      const scale = 0.8 + 0.2 * Math.sin(t * 3 + infon.phase)
      infon.mesh.scale.setScalar(scale)
      ;(infon.mesh.material as THREE.SpriteMaterial).color.copy(this.currentEye)
      ;(infon.mesh.material as THREE.SpriteMaterial).opacity = 0.3 + 0.3 * Math.sin(t + infon.phase)
    }

    // Anillos de evolución concéntricos (Gran Sabio → Raphael → Ciel)
    for (let i = 0; i < this.evolutionRings.length; i++) {
      const ring = this.evolutionRings[i]
      ring.mesh.rotation.x += 0.03 * dt * motion
      ring.mesh.rotation.z += 0.02 * dt * motion
      const pulse = 0.1 + 0.05 * Math.sin(t * 1.3 + i)
      ;(ring.material as THREE.MeshBasicMaterial).opacity = pulse
      ;(ring.material as THREE.MeshBasicMaterial).color.copy(this.currentFractal)
      ring.mesh.scale.setScalar(1 + 0.02 * Math.sin(t * 2 + i))
    }

    this.renderer.render(this.scene, this.camera)
  }

  /** Actualiza la animación (llamado desde el bucle de render externo) */
  update(): void {
    const dt = Math.min(this.clock.getDelta(), 0.05)
    const t = this.clock.elapsedTime
    const motion = this.animated ? 1 : 0

    this.currentCore.lerp(this.targetCore, 1 - Math.pow(0.0015, dt))
    this.currentGlow.lerp(this.targetGlow, 1 - Math.pow(0.0015, dt))
    this.currentEye.lerp(this.targetEye, 1 - Math.pow(0.002, dt))
    this.currentFractal.lerp(this.targetFractal, 1 - Math.pow(0.0018, dt))

    const breathe = 1 + Math.sin((t / BREATH_PERIOD) * Math.PI * 2) * 0.035 * motion
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

    const fractalUniforms = this.fractalMaterial.uniforms
    ;(fractalUniforms.uTime.value as number) = t
    ;(fractalUniforms.uPulse.value as number) = 0.7 + 0.3 * Math.sin(t * 1.3) * motion
    ;(fractalUniforms.uFractalColor.value as THREE.Color).copy(this.currentFractal)
    ;(fractalUniforms.uEyeColor.value as THREE.Color).copy(this.currentEye)
    ;(fractalUniforms.uEvolutionPhase.value as number) = this.phase === 'wisdom' ? 3 : this.phase === 'responding' ? 2 : 1

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

    for (const ring of this.rings) {
      const cycle = ((t + ring.offset) % PULSE_PERIOD) / PULSE_PERIOD
      ring.mesh.scale.setScalar(1 + cycle * 1.4)
      ring.material.opacity = motion ? Math.max(0, 0.7 * (1 - cycle)) : 0
      ring.material.color.copy(this.currentCore)
    }

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

    const dataPoints = (this.scene as any)._dataPoints as THREE.Points | undefined
    if (dataPoints) {
      const pos = (dataPoints as any)._positions as Float32Array
      const phases = (dataPoints as any)._phases as Float32Array
      for (let i = 0; i < FIBONACCI_COUNT; i++) {
        const phi = t * 0.3 + phases[i] * Math.PI * 2
        const scale = 0.8 + (i / FIBONACCI_COUNT) * 0.8
        const r = scale * 0.02
        pos[i * 3] = Math.cos(phi) * r
        pos[i * 3 + 1] = Math.sin(phi * 0.7) * r * 0.3
        pos[i * 3 + 2] = Math.sin(phi) * r
      }
      dataPoints.geometry.attributes.position.needsUpdate = true
      ;(dataPoints.material as THREE.PointsMaterial).color.copy(this.currentCore)
    }

    for (const infon of this.infons) {
      const angle = t * infon.speed + infon.phase
      const r = infon.radius * (0.9 + 0.1 * Math.sin(t + infon.phase))
      infon.mesh.position.set(
        Math.cos(angle) * r,
        Math.sin(angle * 0.6 + t) * r * 0.2,
        Math.sin(angle) * r
      )
      ;(infon.mesh.material as THREE.SpriteMaterial).color.copy(this.currentEye)
    }

    for (let i = 0; i < this.evolutionRings.length; i++) {
      const ring = this.evolutionRings[i]
      ring.mesh.rotation.x += 0.03 * dt * motion
      ring.mesh.rotation.z += 0.02 * dt * motion
      ;(ring.material as THREE.MeshBasicMaterial).color.copy(this.currentFractal)
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

    for (const infon of this.infons) {
      this.scene.remove(infon.mesh)
      ;(infon.mesh.material as THREE.SpriteMaterial).dispose()
    }
    this.infons = []

    for (const dp of this.dataParticles) {
      dp.geometry.dispose()
      dp.material.dispose()
    }
    this.dataParticles = []

    for (const er of this.evolutionRings) {
      this.scene.remove(er.mesh)
      er.geometry?.dispose()
      er.material.dispose()
    }
    this.evolutionRings = []

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

interface Burst {
  lines: THREE.LineSegments
  material: THREE.LineBasicMaterial
  life: number
}

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

export interface OrbVisualProps {
  phase: OrbPhase
  animated?: boolean
}

/**
 * Orbe 3D del Gran Sabio:
 * - 7 capas fresnel con rotación propia
 * - Ojo fractal infinito en el núcleo (patrón de espiral logarítmica)
 * - 89 partículas en espiral de Fibonacci (conocimiento infinito)
 * - 34 infons fluyendo (energía fundamental de Ciel)
 * - 3 anillos de evolución concéntricos (Gran Sabio → Raphael → Ciel)
 * - 24 partículas orbitales
 * - Anillos de pulso con ondas Shinkirō
 * - Rayos burst al activarse
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
