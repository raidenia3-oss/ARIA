"use client";

import { useRef, useMemo, useEffect, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Sphere, MeshDistortMaterial, PointsMaterial, BufferGeometry, Float32BufferAttribute } from "@react-three/drei";
import * as THREE from "three";

export type CoreState = "idle" | "listening" | "thinking" | "speaking" | "processing";

interface CoreVisualizerProps {
  state?: CoreState;
  className?: string;
  hex?: string;
  onStateChange?: (state: CoreState) => void;
}

const STATE_COLORS: Record<CoreState, string> = {
  idle: "#38bdf8",
  listening: "#22d3ee",
  thinking: "#fbbf24",
  speaking: "#f472b6",
  processing: "#a78bfa",
};

const STATE_PARTICLE_COUNTS: Record<CoreState, number> = {
  idle: 800,
  listening: 1200,
  thinking: 1500,
  speaking: 1400,
  processing: 1600,
};

const STATE_DISTORT: Record<CoreState, { base: number; amplitude: number; speed: number }> = {
  idle: { base: 0.3, amplitude: 0.05, speed: 0.5 },
  listening: { base: 0.4, amplitude: 0.15, speed: 1.2 },
  thinking: { base: 0.5, amplitude: 0.2, speed: 0.8 },
  speaking: { base: 0.45, amplitude: 0.25, speed: 2.0 },
  processing: { base: 0.6, amplitude: 0.15, speed: 1.5 },
};

const STATE_ROTATION_SPEED: Record<CoreState, number> = {
  idle: 0.02,
  listening: 0.03,
  thinking: 0.015,
  speaking: 0.04,
  processing: 0.025,
};

const STATE_PULSE: Record<CoreState, { enabled: boolean; speed: number; intensity: number }> = {
  idle: { enabled: true, speed: 1.0, intensity: 0.1 },
  listening: { enabled: true, speed: 2.5, intensity: 0.25 },
  thinking: { enabled: true, speed: 1.5, intensity: 0.2 },
  speaking: { enabled: true, speed: 3.0, intensity: 0.3 },
  processing: { enabled: true, speed: 2.0, intensity: 0.15 },
};

function ParticleField({ hex, count, state }: { hex: string; count: number; state: CoreState }) {
  const pointsRef = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    const velocities = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = 2.2 + Math.random() * 1.5;
      arr[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      arr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      arr[i * 3 + 2] = r * Math.cos(phi);
      velocities[i * 3] = (Math.random() - 0.5) * 0.002;
      velocities[i * 3 + 1] = (Math.random() - 0.5) * 0.002;
      velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.002;
    }
    return { positions: arr, velocities };
  }, [count]);

  useFrame((stateFrame) => {
    const t = stateFrame.clock.getElapsedTime();
    if (pointsRef.current) {
      const positions = pointsRef.current.geometry.attributes.position.array as Float32Array;
      const velocities = (pointsRef.current.geometry.attributes as any).velocity?.array as Float32Array || positions;
      const baseRadius = 2.5;
      
      for (let i = 0; i < count; i++) {
        const theta = t * 0.15 + i * 0.01;
        const phi = Math.sin(t * 0.1 + i * 0.05) * 0.5 + Math.PI / 2;
        const r = baseRadius + Math.sin(t * 0.7 + i * 0.1) * 0.4;
        
        positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        positions[i * 3 + 2] = r * Math.cos(phi);
      }
      pointsRef.current.geometry.attributes.position.needsUpdate = true;
      pointsRef.current.rotation.y = t * 0.02;
      pointsRef.current.rotation.x = Math.sin(t * 0.1) * 0.05;
    }
  });

  const particleColor = new THREE.Color(hex);
  const sizes = useMemo(() => {
    const arr = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      arr[i] = 0.02 + Math.random() * 0.03;
    }
    return arr;
  }, [count]);

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" count={count} array={positions.positions} itemSize={3} />
        <bufferAttribute attach="attributes-size" count={count} array={sizes} itemSize={1} />
        <bufferAttribute attach="attributes-velocity" count={count} array={positions.velocities} itemSize={3} />
      </bufferGeometry>
      <PointsMaterial
        size={0.04}
        color={particleColor}
        transparent
        opacity={0.9}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        sizeAttenuation={true}
      />
    </points>
  );
}

function CoreSphere({ hex, state, intensity }: { hex: string; state: CoreState; intensity: number }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.Material>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const distortionConfig = STATE_DISTORT[state];
  const pulseConfig = STATE_PULSE[state];
  const rotationSpeed = STATE_ROTATION_SPEED[state];

  useFrame((stateFrame) => {
    const t = stateFrame.clock.getElapsedTime();
    
    if (meshRef.current) {
      meshRef.current.rotation.y += rotationSpeed;
      meshRef.current.rotation.x = Math.sin(t * 0.1) * 0.05;
    }

    if (materialRef.current && "distort" in materialRef.current) {
      (materialRef.current as any).distort = distortionConfig.base + Math.sin(t * distortionConfig.speed) * distortionConfig.amplitude;
    }

    if (pulseConfig.enabled && ringRef.current) {
      const pulse = 1 + Math.sin(t * pulseConfig.speed * Math.PI * 2) * pulseConfig.intensity;
      ringRef.current.scale.setScalar(pulse * intensity);
      ringRef.current.material.opacity = 0.15 + Math.sin(t * pulseConfig.speed * Math.PI * 2) * 0.1;
    }
  });

  return (
    <group>
      <Sphere args={[1.8, 64, 64]} ref={meshRef}>
        <MeshDistortMaterial
          ref={materialRef}
          color={hex}
          wireframe
          transparent
          opacity={0.12 + intensity * 0.08}
          distort={distortionConfig.base}
          speed={distortionConfig.speed}
        />
      </Sphere>
      <mesh ref={ringRef} rotationX={-Math.PI / 2}>
        <torusGeometry args={[2.2, 0.02, 16, 64]} />
        <meshBasicMaterial
          color={hex}
          transparent
          opacity={0.15}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
      <mesh>
        <sphereGeometry args={[1.2, 32, 32]} />
        <meshBasicMaterial
          color={hex}
          transparent
          opacity={0.05 + intensity * 0.03}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
    </group>
  );
}

function StateIndicator({ state, hex }: { state: CoreState; hex: string }) {
  const labels: Record<CoreState, string> = {
    idle: "ESPERA",
    listening: "ESCUCHANDO",
    thinking: "RAZONANDO",
    speaking: "HABLANDO",
    processing: "PROCESANDO",
  };

  const pulseColors: Record<CoreState, string> = {
    idle: "#38bdf8",
    listening: "#06b6d4",
    thinking: "#f59e0b",
    speaking: "#ec4899",
    processing: "#8b5cf6",
  };

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 pointer-events-none">
      <div
        className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-black/60 backdrop-blur-sm border"
        style={{ borderColor: hex + "80" }}
      >
        <span
          className="w-2 h-2 rounded-full animate-pulse"
          style={{ backgroundColor: pulseColors[state], boxShadow: `0 0 8px ${pulseColors[state]}` }}
        />
        <span className="text-xs font-mono tracking-widest text-white/90 uppercase">
          {labels[state]}
        </span>
      </div>
      <div className="flex gap-1">
        {Object.entries(STATE_COLORS).map(([key, color]) => (
          <div
            key={key}
            className="w-2 h-2 rounded-full transition-all duration-300"
            style={{
              backgroundColor: key === state ? color : color + "33",
              transform: key === state ? "scale(1.3)" : "scale(1)",
              boxShadow: key === state ? `0 0 8px ${color}` : "none",
            }}
          />
        ))}
      </div>
    </div>
  );
}

export default function CoreVisualizer({
  state = "idle",
  className = "",
  hex: customHex,
  onStateChange,
}: CoreVisualizerProps) {
  const [currentState, setCurrentState] = useState<CoreState>(state);
  const hex = customHex || STATE_COLORS[currentState];
  const particleCount = STATE_PARTICLE_COUNTS[currentState];
  const distortionConfig = STATE_DISTORT[currentState];
  const intensity = distortionConfig.base > 0.4 ? 1 : 0.5;

  useEffect(() => {
    setCurrentState(state);
    onStateChange?.(state);
  }, [state, onStateChange]);

  return (
    <div className={`relative w-full h-[400px] md:h-[500px] ${className}`}>
      <Canvas
        camera={{ position: [0, 0, 6.5], fov: 50 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true, preserveDrawingBuffer: false }}
      >
        <color attach="background" args={["#05070a"]} />
        <fog attach="fog" args={["#05070a", 5, 15]} />
        <ambientLight intensity={0.4} />
        <directionalLight position={[2, 3, 4]} intensity={0.6} color={hex} />
        <pointLight position={[-2, 2, 3]} intensity={0.4} color={hex} decay={2} />
        
        <CoreSphere hex={hex} state={currentState} intensity={intensity} />
        <ParticleField hex={hex} count={particleCount} state={currentState} />
        
        <OrbitControls
          enablePan={false}
          enableZoom={true}
          autoRotate
          autoRotateSpeed={0.3}
          minZoom={0.5}
          maxZoom={3}
          enableDamping
          dampingFactor={0.05}
        />
      </Canvas>
      <StateIndicator state={currentState} hex={hex} />
    </div>
  );
}

export { CoreVisualizer, type CoreState, STATE_COLORS };