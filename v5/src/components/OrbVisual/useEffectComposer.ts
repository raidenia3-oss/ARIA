import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { EffectComposer } from 'three-stdlib'
import { RenderPass } from 'three-stdlib'
import { UnrealBloomPass } from 'three-stdlib'

export function useEffectComposer(
  renderer: THREE.WebGLRenderer | null,
  scene: THREE.Scene | null,
  camera: THREE.PerspectiveCamera | null
) {
  const composerRef = useRef<EffectComposer | null>(null)

  useEffect(() => {
    if (!renderer || !scene || !camera) return

    const composer = new EffectComposer(renderer)
    composer.setSize(window.innerWidth, window.innerHeight)

    const renderPass = new RenderPass(scene, camera)
    composer.addPass(renderPass)

    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(window.innerWidth, window.innerHeight),
      1.5,    // strength
      0.4,    // radius
      0.85    // threshold
    )
    composer.addPass(bloomPass)

    composerRef.current = composer

    const handleResize = () => {
      composer.setSize(window.innerWidth, window.innerHeight)
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      composer.dispose()
    }
  }, [renderer, scene, camera])

  return composerRef.current
}