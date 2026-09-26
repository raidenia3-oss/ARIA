/**
 * Sistema de partículas 3D para AURA.
 * Usa Three.js si está disponible; fallback a Canvas 2D.
 */

export type Particle = {
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  life: number;
  maxLife: number;
  color: string;
  size: number;
};

export type ParticleMode = "explosion" | "implosion" | "vortex" | "beam" | "aura" | "stream" | "domain_expansion" | "idle";

const JJK_COLORS = ["#7c4dff", "#00e5ff", "#8a2be2", "#ff4d4d"];

type ThreeModule = {
  Scene: new () => unknown;
  PerspectiveCamera: new (fov: number, aspect: number, near: number, far: number) => unknown;
  WebGLRenderer: new (opts: { alpha: boolean }) => unknown;
  BufferGeometry: new () => unknown;
  PointsMaterial: new (opts: Record<string, unknown>) => unknown;
  Points: new (geom: unknown, mat: unknown) => unknown;
  BufferAttribute: new (arr: Float32Array, size: number) => unknown;
};

export class ParticleSystem3D {
  private particles: Particle[] = [];
  private maxParticles = 5000;
  private mode: ParticleMode = "aura";
  private domainExpansion = false;
  private domainProgress = 0;
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;
  private threeScene: unknown = null;
  private threePoints: unknown = null;
  private threeGeometry: unknown = null;
  private threeMaterial: unknown = null;
  private threeRenderer: unknown = null;
  private threeCamera: unknown = null;
  private useThree = false;
  private THREE: ThreeModule | null = null;

  constructor(canvas?: HTMLCanvasElement) {
    if (canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.initThree();
    }
  }

  private async initThree() {
    try {
      const THREE = (await import("three")) as unknown as ThreeModule;
      if (!THREE) return;
      this.THREE = THREE;
      this.useThree = true;
      this.threeScene = new THREE.Scene();
      this.threeCamera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
      (this.threeCamera as { position: { z: number } }).position.z = 5;
      this.threeRenderer = new THREE.WebGLRenderer({ alpha: true });
      (this.threeRenderer as { setSize: (w: number, h: number) => void }).setSize(window.innerWidth, window.innerHeight);
      if (this.canvas) {
        this.canvas.parentElement?.appendChild((this.threeRenderer as { domElement: HTMLElement }).domElement);
      }
      this.threeGeometry = new THREE.BufferGeometry();
      this.threeMaterial = new THREE.PointsMaterial({
        color: 0x7c4dff,
        size: 0.05,
        transparent: true,
        opacity: 0.8,
      });
      this.threePoints = new THREE.Points(this.threeGeometry, this.threeMaterial);
      (this.threeScene as { add: (obj: unknown) => void }).add(this.threePoints);
    } catch {
      this.useThree = false;
    }
  }

  private randomColor(): string {
    return JJK_COLORS[Math.floor(Math.random() * JJK_COLORS.length)];
  }

  private addParticle(p: Particle) {
    if (this.particles.length >= this.maxParticles) {
      this.particles.shift();
    }
    this.particles.push(p);
  }

  spawnExplosion(x = 0, y = 0, z = 0, count = 50) {
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const speed = 1.5 + Math.random() * 2.5;
      this.addParticle({
        x, y, z,
        vx: Math.sin(phi) * Math.cos(theta) * speed,
        vy: Math.sin(phi) * Math.sin(theta) * speed,
        vz: Math.cos(phi) * speed,
        life: 1.5 + Math.random() * 2,
        maxLife: 3.5,
        color: this.randomColor(),
        size: 2 + Math.random() * 3,
      });
    }
  }

  spawnImplosion(x = 0, y = 0, z = 0, count = 50) {
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const radius = 3 + Math.random() * 5;
      const speed = 1 + Math.random() * 1.5;
      this.addParticle({
        x: x + Math.cos(angle) * radius,
        y: y + Math.sin(angle) * radius,
        z,
        vx: -Math.cos(angle) * speed,
        vy: -Math.sin(angle) * speed,
        vz: -speed * 0.5,
        life: 1 + Math.random() * 1.5,
        maxLife: 2.5,
        color: "#ff4d4d",
        size: 2 + Math.random() * 2.5,
      });
    }
  }

  spawnVortex(x = 0, y = 0, z = 0, count = 50) {
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const radius = 0.5 + Math.random() * 2;
      const height = (Math.random() - 0.5) * 4;
      const speed = 2 + Math.random() * 2;
      this.addParticle({
        x: x + Math.cos(angle) * radius,
        y: y + Math.sin(angle) * radius,
        z: z + height,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        vz: height * 0.5,
        life: 1.5 + Math.random() * 2,
        maxLife: 3.5,
        color: "#00e5ff",
        size: 1.5 + Math.random() * 2,
      });
    }
  }

  spawnBeam(x = 0, y = 0, z = 0, count = 50) {
    for (let i = 0; i < count; i++) {
      this.addParticle({
        x: x + (Math.random() - 0.5) * 0.5,
        y: y + (Math.random() - 0.5) * 0.5,
        z: z + Math.random() * 6,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        vz: 1 + Math.random() * 1.5,
        life: 0.8 + Math.random() * 1.2,
        maxLife: 2,
        color: "#7c4dff",
        size: 1 + Math.random() * 1.5,
      });
    }
  }

  spawnAura(x = 0, y = 0, z = 0, count = 50) {
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const radius = 0.8 + Math.random() * 1.5;
      const height = (Math.random() - 0.5) * 2.5;
      this.addParticle({
        x: x + Math.cos(angle) * radius,
        y: y + Math.sin(angle) * radius,
        z: z + height,
        vx: Math.cos(angle) * 0.4,
        vy: Math.sin(angle) * 0.4,
        vz: (Math.random() - 0.5) * 0.6,
        life: 1.2 + Math.random() * 1.8,
        maxLife: 3,
        color: "#8a2be2",
        size: 1.5 + Math.random() * 2.5,
      });
    }
  }

  spawnStream(x = 0, y = 0, z = 0, count = 50) {
    for (let i = 0; i < count; i++) {
      this.addParticle({
        x: x + (Math.random() - 0.5) * 3,
        y: y + (Math.random() - 0.5) * 3,
        z: z + Math.random() * 4,
        vx: (Math.random() - 0.5) * 2,
        vy: (Math.random() - 0.5) * 2,
        vz: 1 + Math.random() * 2,
        life: 1 + Math.random() * 1.5,
        maxLife: 2.5,
        color: this.randomColor(),
        size: 1.5 + Math.random() * 2,
      });
    }
  }

  setDomainExpansion(active: boolean, progress = 0) {
    this.domainExpansion = active;
    this.domainProgress = progress;
    if (active) {
      this.mode = "domain_expansion";
      for (let i = 0; i < 200; i++) {
        this.addParticle({
          x: (Math.random() - 0.5) * 6,
          y: (Math.random() - 0.5) * 6,
          z: (Math.random() - 0.5) * 6,
          vx: (Math.random() - 0.5) * 2,
          vy: (Math.random() - 0.5) * 2,
          vz: (Math.random() - 0.5) * 2,
          life: 2 + Math.random() * 3,
          maxLife: 5,
          color: "#8a2be2",
          size: 1.5 + Math.random() * 3,
        });
      }
    } else {
      this.mode = "idle";
    }
  }

  setMode(mode: ParticleMode) {
    this.mode = mode;
  }

  spawnFromGesture(gesture: string, x = 0, y = 0, z = 0, confidence = 0.5) {
    const count = Math.floor(20 + confidence * 80);
    switch (gesture) {
      case "open_hand": this.spawnExplosion(x, y, z, count); break;
      case "fist": this.spawnImplosion(x, y, z, count); break;
      case "peace": this.spawnVortex(x, y, z, count); break;
      case "index": this.spawnBeam(x, y, z, count); break;
      case "heart": this.spawnAura(x, y, z, count); break;
      case "swipe": this.spawnStream(x, y, z, count); break;
      default:
        if (confidence > 0.5) this.spawnAura(x, y, z, Math.max(10, Math.floor(confidence * 30)));
    }
  }

  update(dt: number) {
    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i];
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.z += p.vz * dt;
      p.life -= dt;
      p.vx *= 0.99;
      p.vy *= 0.99;
      p.vz *= 0.99;
      if (p.life <= 0) {
        this.particles.splice(i, 1);
      }
    }
    if (this.domainExpansion) {
      this.domainProgress = Math.min(1, this.domainProgress + dt * 0.5);
    }
    this.render();
  }

  private render() {
    if (this.useThree && this.threePoints && this.threeGeometry) {
      const positions = new Float32Array(this.particles.length * 3);
      this.particles.forEach((p, i) => {
        positions[i * 3] = p.x;
        positions[i * 3 + 1] = p.y;
        positions[i * 3 + 2] = p.z;
      });
      if (!this.THREE) return;
      (this.threeGeometry as { setAttribute: (name: string, attr: unknown) => void }).setAttribute(
        "position",
        new this.THREE.BufferAttribute(positions, 3),
      );
      (this.threeRenderer as { render: (scene: unknown, camera: unknown) => void }).render(this.threeScene, this.threeCamera);
      return;
    }
    if (!this.ctx || !this.canvas) return;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.particles.forEach((p) => {
      const alpha = Math.max(0, p.life / p.maxLife);
      this.ctx!.globalAlpha = alpha;
      this.ctx!.fillStyle = p.color;
      const scale = 50;
      this.ctx!.beginPath();
      this.ctx!.arc(
        this.canvas!.width / 2 + p.x * scale,
        this.canvas!.height / 2 + p.y * scale,
        p.size * alpha,
        0,
        Math.PI * 2,
      );
      this.ctx!.fill();
    });
    this.ctx.globalAlpha = 1;
  }

  getParticles(): Particle[] {
    return this.particles;
  }

  getCount(): number {
    return this.particles.length;
  }
}