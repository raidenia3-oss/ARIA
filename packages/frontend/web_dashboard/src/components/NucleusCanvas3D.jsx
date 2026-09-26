import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Sphere, MeshDistortMaterial } from '@react-three/drei'

function ParticleSphere({ hex }) {
  const meshRef = useRef()
  const materialRef = useRef()
  const count = 1200
  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      const r = 2 + Math.random() * 0.3
      arr[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      arr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
      arr[i * 3 + 2] = r * Math.cos(phi)
    }
    return arr
  }, [])

  useFrame((state) => {
    const t = state.clock.getElapsedTime()
    if (meshRef.current) {
      meshRef.current.rotation.y = t * 0.05
      meshRef.current.rotation.x = Math.sin(t * 0.2) * 0.1
    }
    if (materialRef.current) {
      materialRef.current.distort = 0.3 + Math.sin(t * 0.5) * 0.1
    }
  })

  return (
    <group>
      <Sphere args={[2, 64, 64]} ref={meshRef}>
        <MeshDistortMaterial
          ref={materialRef}
          color={hex}
          wireframe
          transparent
          opacity={0.15}
          distort={0.4}
          speed={2}
        />
      </Sphere>
      <points>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={count}
            array={positions}
            itemSize={3}
          />
        </bufferGeometry>
        <pointsMaterial size={0.03} color={hex} transparent opacity={0.8} blending={2} depthWrite={false} />
      </points>
    </group>
  )
}

export default function NucleusCanvas3D({ hex = '#38bdf8' }) {
  return (
    <div className="h-[320px] w-full md:h-[420px]">
      <Canvas camera={{ position: [0, 0, 6], fov: 50 }} dpr={[1, 2]}>
        <color attach="background" args={['#05070a']} />
        <ambientLight intensity={0.5} />
        <ParticleSphere hex={hex} />
        <OrbitControls enablePan={false} enableZoom={true} autoRotate autoRotateSpeed={0.5} />
      </Canvas>
    </div>
  )
}
