import React, { useEffect, useRef } from 'react'
import * as THREE from 'three'

export default function NucleusCanvas({ theme, telemetry }) {
  const containerRef = useRef(null)
  const sceneRef = useRef(null)
  const particlesRef = useRef([])

  useEffect(() => {
    if (!containerRef.current) return

    // Scene setup
    const scene = new THREE.Scene()
    sceneRef.current = scene

    const camera = new THREE.PerspectiveCamera(
      75,
      window.innerWidth / window.innerHeight,
      0.1,
      1000
    )
    camera.position.z = 30

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(window.innerWidth, window.innerHeight)
    renderer.setClearColor(0x000000, 0.1)
    containerRef.current.appendChild(renderer.domElement)

    // Convert hex to RGB
    const hexToRgb = (hex) => {
      const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
      return result
        ? [
            parseInt(result[1], 16) / 255,
            parseInt(result[2], 16) / 255,
            parseInt(result[3], 16) / 255,
          ]
        : [0.39, 0.4, 0.96]
    }

    // Create nucleus core
    const coreGeometry = new THREE.IcosahedronGeometry(2, 4)
    const coreMaterial = new THREE.MeshPhongMaterial({
      color: new THREE.Color(...hexToRgb(theme)),
      emissive: new THREE.Color(...hexToRgb(theme)),
      emissiveIntensity: 0.5,
      wireframe: false,
    })
    const coreMesh = new THREE.Mesh(coreGeometry, coreMaterial)
    scene.add(coreMesh)

    // Create particle system
    const particleCount = 1000
    const particleGeometry = new THREE.BufferGeometry()
    const positions = new Float32Array(particleCount * 3)
    const velocities = []

    for (let i = 0; i < particleCount; i++) {
      const i3 = i * 3
      positions[i3] = (Math.random() - 0.5) * 100
      positions[i3 + 1] = (Math.random() - 0.5) * 100
      positions[i3 + 2] = (Math.random() - 0.5) * 100

      velocities.push({
        x: (Math.random() - 0.5) * 0.5,
        y: (Math.random() - 0.5) * 0.5,
        z: (Math.random() - 0.5) * 0.5,
      })
    }

    particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))

    const particleMaterial = new THREE.PointsMaterial({
      color: new THREE.Color(...hexToRgb(theme)),
      size: 0.5,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.6,
    })

    const particles = new THREE.Points(particleGeometry, particleMaterial)
    scene.add(particles)

    particlesRef.current = {
      mesh: particles,
      positions,
      velocities,
    }

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5)
    scene.add(ambientLight)

    const pointLight = new THREE.PointLight(new THREE.Color(...hexToRgb(theme)), 1.5)
    pointLight.position.set(10, 10, 10)
    scene.add(pointLight)

    // Animation loop
    let animationId
    const animate = () => {
      animationId = requestAnimationFrame(animate)

      // Rotate core
      coreMesh.rotation.x += 0.001
      coreMesh.rotation.y += 0.002

      // Update particles
      const posAttr = particles.geometry.attributes.position
      for (let i = 0; i < particleCount; i++) {
        const i3 = i * 3
        const vel = velocities[i]

        positions[i3] += vel.x
        positions[i3 + 1] += vel.y
        positions[i3 + 2] += vel.z

        // Bounce at boundaries
        if (Math.abs(positions[i3]) > 50) vel.x *= -1
        if (Math.abs(positions[i3 + 1]) > 50) vel.y *= -1
        if (Math.abs(positions[i3 + 2]) > 50) vel.z *= -1
      }
      posAttr.needsUpdate = true

      // Update telemetry-based intensity
      if (telemetry?.cpu?.percent) {
        const intensity = 0.3 + (telemetry.cpu.percent / 100) * 0.7
        pointLight.intensity = intensity
        particleMaterial.opacity = 0.4 + intensity * 0.2
      }

      renderer.render(scene, camera)
    }
    animate()

    // Handle resize
    const handleResize = () => {
      const width = window.innerWidth
      const height = window.innerHeight
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      cancelAnimationFrame(animationId)
      renderer.dispose()
      containerRef.current?.removeChild(renderer.domElement)
    }
  }, [theme])

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
}
