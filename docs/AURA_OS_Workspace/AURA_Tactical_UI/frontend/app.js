// AURA Control Center - Three.js
const COLORS = { bg: 0x080408, crimson: 0xDC143C, gold: 0xFFD700, white: 0xF0F0F8 };
let scene, camera, renderer, controls, raycaster, mouse;
let cubes = [];
let activeIndex = 0;
let ws;
const keys = {};
const models = ['Llama-3-8B', 'Mistral-7B', 'Phi-3-Mini'];

function init() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(COLORS.bg);
  camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.set(0, 2, 8);
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  document.getElementById('canvas-container').appendChild(renderer.domElement);
  controls = new THREE.PointerLockControls(camera, renderer.domElement);
  renderer.domElement.addEventListener('click', () => controls.lock());
  scene.add(new THREE.AmbientLight(0xffffff, 0.15));
  const dir = new THREE.DirectionalLight(0xffffff, 0.6);
  dir.position.set(5, 10, 7);
  scene.add(dir);
  const grid = new THREE.GridHelper(30, 30, 0x220011, 0x110008);
  grid.position.y = -2;
  grid.material.transparent = true;
  grid.material.opacity = 0.4;
  scene.add(grid);
  const geo = new THREE.BoxGeometry(1.4, 1.4, 1.4);
  const spacing = 3.5;
  for (let i = 0; i < 3; i++) {
    const mat = new THREE.MeshStandardMaterial({
      color: i === activeIndex ? COLORS.crimson : 0x333333,
      roughness: 0.2,
      metalness: 0.8,
      emissive: i === activeIndex ? COLORS.crimson : 0x000000,
      emissiveIntensity: i === activeIndex ? 0.4 : 0
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(i * spacing - spacing, 0, 0);
    scene.add(mesh);
    cubes.push({ mesh, mat });
    const wire = new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ color: COLORS.gold, transparent: true, opacity: 0.4 }));
    mesh.add(wire);
  }
  raycaster = new THREE.Raycaster();
  mouse = new THREE.Vector2();
  renderer.domElement.addEventListener('pointerdown', (e) => {
    if (!controls.isLocked) return;
    mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(cubes.map(c => c.mesh));
    if (intersects.length) {
      const idx = cubes.findIndex(c => c.mesh === intersects[0].object);
      if (idx !== -1 && idx !== activeIndex) swapModel(idx);
    }
  });
  initWS();
  animate();
}

function swapModel(idx) {
  cubes[activeIndex].mat.color.setHex(0x333333);
  cubes[activeIndex].mat.emissive.setHex(0x000000);
  cubes[activeIndex].mat.emissiveIntensity = 0;
  activeIndex = idx;
  cubes[activeIndex].mat.color.setHex(COLORS.crimson);
  cubes[activeIndex].mat.emissive.setHex(COLORS.crimson);
  cubes[activeIndex].mat.emissiveIntensity = 0.4;
  const el = document.getElementById('model-name');
  if (el) el.textContent = models[activeIndex];

  // Usar la URL del backend en Railway
  const backendUrl = import.meta.env.VITE_API_URL || 'https://aura-backend.up.railway.app';
  fetch(`${backendUrl}/api/swap-model`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: models[activeIndex] }) });
}

function initWS() {
  // Usar la URL del backend en Railway
  const backendUrl = import.meta.env.VITE_API_URL || 'https://aura-backend.up.railway.app';
  ws = new WebSocket(`wss://${backendUrl.replace(/^https:/, '')}`);
  ws.onmessage = (ev) => {
    const d = JSON.parse(ev.data);
    const ramEl = document.getElementById('ram-used');
    const ramBar = document.getElementById('ram-bar');
    if (ramEl && d.ram !== undefined) { ramEl.textContent = d.ram.toFixed(1); if (ramBar) ramBar.style.width = (d.ram / 32 * 100) + '%'; }
    const vramEl = document.getElementById('vram-used');
    const vramBar = document.getElementById('vram-bar');
    if (vramEl && d.vram !== undefined) { vramEl.textContent = d.vram.toFixed(1); if (vramBar) vramBar.style.width = (d.vram / 12 * 100) + '%'; }
    if (d.active_model) { const idx = models.indexOf(d.active_model); if (idx !== -1 && idx !== activeIndex) swapModel(idx); }
  };
}

function animate() {
  requestAnimationFrame(animate);
  const t = performance.now() * 0.001;
  cubes.forEach((c, i) => {
    c.mesh.rotation.y = Math.sin(t * 0.5 + i) * 0.3;
    c.mesh.rotation.x = Math.cos(t * 0.4 + i) * 0.2;
    c.mesh.position.y = Math.sin(t + i) * 0.15;
  });
  const speed = 0.1;
  if (keys['KeyW']) controls.moveForward(speed);
  if (keys['KeyS']) controls.moveForward(-speed);
  if (keys['KeyA']) controls.moveRight(-speed);
  if (keys['KeyD']) controls.moveRight(speed);
  renderer.render(scene, camera);
}

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});
window.addEventListener('keydown', e => keys[e.code] = true);
window.addEventListener('keyup', e => keys[e.code] = false);
init();