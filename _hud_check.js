
        const API = 'http://localhost:8000';
        const chatBox = document.getElementById('chatBox');
        const messageInput = document.getElementById('messageInput');
        const backendDot = document.getElementById('backendDot');
        const backendStatus = document.getElementById('backendStatus');
        const systemDot = document.getElementById('systemDot');
        const orbLabel = document.getElementById('orbLabel');
        const eventLog = document.getElementById('eventLog');
        const skillGrid = document.getElementById('skillGrid');
        const transcription = document.getElementById('transcription');
        let isListening = false;
        let recognition = null;
        // Fase 2: analizador de micrófono para energía del núcleo
        let orbAudioCtx = null, orbAnalyser = null, orbMicData = null, orbMicStream = null;

        // RELOJ DIGITAL
        function updateClock() {
            const now = new Date();
            let hours = now.getHours();
            const minutes = now.getMinutes().toString().padStart(2, '0');
            const seconds = now.getSeconds().toString().padStart(2, '0');
            const period = hours >= 12 ? 'PM' : 'AM';
            hours = hours % 12;
            if (hours === 0) hours = 12;
            const timeStr = hours + ':' + minutes;
            const clockTime = document.getElementById('clockTime');
            const clockSeconds = document.getElementById('clockSeconds');
            const clockPeriod = document.getElementById('clockPeriod');
            if (clockTime) clockTime.textContent = timeStr;
            if (clockSeconds) clockSeconds.textContent = seconds;
            if (clockPeriod) clockPeriod.textContent = period;
        }
        updateClock();
        setInterval(updateClock, 1000);

        // SKILLS DATA
        const SKILLS = [
            {name: 'status', label: '📊 Estado', color: '#38bdf8'},
            {name: 'time', label: '🕒 Hora', color: '#8a2be2'},
            {name: 'ping', label: '🌐 Ping', color: '#22c55e'},
            {name: 'scan', label: '🔍 Escanear', color: '#f59e0b'},
            {name: 'whois', label: '🔎 WHOIS', color: '#ef4444'},
            {name: 'weather', label: '🌤 Clima', color: '#38bdf8'},
            {name: 'open', label: '🚀 Abrir', color: '#8a2be2'},
            {name: 'volume', label: '🔊 Volumen', color: '#22c55e'},
            {name: 'screenshot', label: '📸 Captura', color: '#f59e0b'},
            {name: 'memory', label: '🧠 Memoria', color: '#ef4444'},
            {name: 'lock', label: '🔒 Bloquear', color: '#38bdf8'},
            {name: 'apps', label: '📱 Apps', color: '#8a2be2'},
        ];

        // Orb canvas animation — núcleo visual tipo "glowing core"
        // Estados: 'idle' | 'listening' | 'thinking' | 'speaking' | 'processing'
        let orbState = 'idle';
        let orbTime = 0;
        let orbReaction = 0;
        let orbEnergy = 0;          // 0..1 nivel de voz/actividad (Fase 2 lo alimenta)
        let orbEnergyTarget = 0;
        let orbReduced = false;     // prefers-reduced-motion
        let orbColorCur = { c1: [200, 230, 255], c2: [150, 190, 240] };
        try {
            const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
            orbReduced = !!(mq && mq.matches);
            if (mq && mq.addEventListener) mq.addEventListener('change', (e) => { orbReduced = !!e.matches; });
        } catch (e) { /* sin matchMedia: animación completa */ }
        let orbAnimationId = null;
        let mouseX = 0, mouseY = 0;
        let orbHover = false;
        let bgParticles = [];
        const chatHistory = [];   // contexto multi-turno para /api/chat/stream

        // Alineado 1:1 con NucleusCanvas (aura_app.py):
        //   _state_anim speed/amp   -> pulseSpeed / pulseAmp
        //   _status_colors hex      -> color1 / color2 (rgb)
        // Estados espejo de Tk: active, ready, listening, thinking, speaking,
        // processing, warning, error (los faltantes causaban fallback silencioso a idle).
        const STATE_CONFIG = {
            idle:      { pulseSpeed: 1.2, pulseAmp: 0.10, particleSpeed: 0.9, count: 12, ringSpeed: 0.25,  ringTilt: 0.42, color1: '56,189,248',  color2: '138,43,226'  }, // reposo (CSS .state-idle: cyan+violeta)
            ready:     { pulseSpeed: 1.2, pulseAmp: 0.10, particleSpeed: 0.9, count: 12, ringSpeed: 0.25,  ringTilt: 0.42, color1: '56,189,248',  color2: '138,43,226'  }, // = idle, halo verde (CSS .state-ready)
            active:    { pulseSpeed: 1.5, pulseAmp: 0.15, particleSpeed: 1.0, count: 14, ringSpeed: 0.45,  ringTilt: 0.40, color1: '124,77,255',  color2: '0,229,255'   }, // Tk ACCENT / ACCENT2
            listening: { pulseSpeed: 2.2, pulseAmp: 0.22, particleSpeed: 1.8, count: 16, ringSpeed: 0.9,   ringTilt: 0.38, color1: '34,211,238',  color2: '6,182,212'   }, // Tk #22d3ee / #06b6d4
            thinking:  { pulseSpeed: 0.9, pulseAmp: 0.12, particleSpeed: 1.3, count: 14, ringSpeed: -0.6,  ringTilt: 0.55, color1: '245,158,11',  color2: '217,119,6'   }, // Tk #f59e0b / #d97706
            speaking:  { pulseSpeed: 3.2, pulseAmp: 0.30, particleSpeed: 2.2, count: 16, ringSpeed: 1.4,   ringTilt: 0.33, color1: '244,114,182', color2: '236,72,153'  }, // Tk #f472b6 / #ec4899
            processing:{ pulseSpeed: 1.6, pulseAmp: 0.18, particleSpeed: 1.5, count: 15, ringSpeed: 0.7,   ringTilt: 0.47, color1: '167,139,250', color2: '139,92,246'  }, // Tk #a78bfa / #8b5cf6
            warning:   { pulseSpeed: 0.8, pulseAmp: 0.08, particleSpeed: 0.8, count: 12, ringSpeed: -0.3,  ringTilt: 0.50, color1: '255,234,0',   color2: '251,191,36'  }, // Tk YELLOW / #fbbf24
            error:     { pulseSpeed: 0.6, pulseAmp: 0.06, particleSpeed: 0.6, count: 10, ringSpeed: -0.45, ringTilt: 0.60, color1: '255,77,77',   color2: '239,68,68'   }, // Tk RED / #ef4444
        };
        function parseRGB(s) { const p = String(s).split(','); return [Number(p[0]) || 0, Number(p[1]) || 0, Number(p[2]) || 0]; }
        // API pública del núcleo (la usa la Fase 2: voz, streaming, eventos)
        function setOrbEnergy(v) { orbEnergyTarget = Math.max(0, Math.min(1, Number(v) || 0)); }

        // Background depth particles
        function initBgParticles() {
            bgParticles = [];
            for (let i = 0; i < 30; i++) {
                bgParticles.push({
                    x: Math.random() * 400,
                    y: Math.random() * 400,
                    vx: (Math.random() - 0.5) * 0.3,
                    vy: (Math.random() - 0.5) * 0.3,
                    size: Math.random() * 1.5 + 0.5,
                    alpha: Math.random() * 0.15 + 0.03,
                });
            }
        }

        // Mouse tracking
        const orbCanvas = document.getElementById('orbCanvas');
        if (orbCanvas) {
            orbCanvas.addEventListener('mousemove', (e) => {
                const rect = orbCanvas.getBoundingClientRect();
                mouseX = e.clientX - rect.left;
                mouseY = e.clientY - rect.top;
                orbHover = true;
            });
            orbCanvas.addEventListener('mouseleave', () => { orbHover = false; });
            orbCanvas.addEventListener('click', () => { orbReact(); orbReact(); });
        }

        function initOrb() {
            const canvas = document.getElementById('orbCanvas');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            let particles = [];
            const NUM_PARTICLES = 12;

            function resize() {
                const dpr = window.devicePixelRatio || 1;
                canvas.width = canvas.offsetWidth * dpr;
                canvas.height = canvas.offsetHeight * dpr;
                ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            }
            window.addEventListener('resize', resize);
            resize();

            const centerX = () => canvas.offsetWidth / 2;
            const centerY = () => canvas.offsetHeight / 2;

            // Inicializar partículas orbitantes con trail
            for (let i = 0; i < NUM_PARTICLES; i++) {
                particles.push({
                    angleOffset: (i / NUM_PARTICLES) * Math.PI * 2 + Math.random() * 0.3,
                    radiusOffset: 8 + Math.random() * 12,
                    sizeBase: 2 + Math.random() * 2,
                    speedMult: 0.7 + Math.random() * 0.6,
                    phase: Math.random() * Math.PI * 2,
                    trail: [],
                });
            }

            function draw() {
                orbTime += orbReduced ? 0.008 : 0.016;
                if (orbReaction > 0) orbReaction *= 0.92;
                if (orbReaction < 0.01) orbReaction = 0;
                // Energía suavizada (reacción a voz/actividad)
                orbEnergy += (orbEnergyTarget - orbEnergy) * 0.08;
                if (Math.abs(orbEnergyTarget - orbEnergy) < 0.001) orbEnergy = orbEnergyTarget;

                const w = canvas.offsetWidth;
                const h = canvas.offsetHeight;
                ctx.clearRect(0, 0, w, h);

                const cx = centerX();
                const cy = centerY();
                const cfg = STATE_CONFIG[orbState] || STATE_CONFIG.idle;
                // Transición suave de color entre estados (crossfade)
                const t1 = parseRGB(cfg.color1), t2 = parseRGB(cfg.color2);
                const k = 0.12;
                orbColorCur.c1[0] += (t1[0] - orbColorCur.c1[0]) * k;
                orbColorCur.c1[1] += (t1[1] - orbColorCur.c1[1]) * k;
                orbColorCur.c1[2] += (t1[2] - orbColorCur.c1[2]) * k;
                orbColorCur.c2[0] += (t2[0] - orbColorCur.c2[0]) * k;
                orbColorCur.c2[1] += (t2[1] - orbColorCur.c2[1]) * k;
                orbColorCur.c2[2] += (t2[2] - orbColorCur.c2[2]) * k;
                const c1 = orbColorCur.c1.map(Math.round).join(',');
                const c2 = orbColorCur.c2.map(Math.round).join(',');
                const energy = orbReduced ? 0 : orbEnergy;
                const pulseBase = Math.sin(orbTime * cfg.pulseSpeed) * cfg.pulseAmp + (1 - cfg.pulseAmp);
                const pulse = Math.max(0.3, pulseBase + orbReaction * 0.3 + energy * 0.25);
                const radius = 50 + Math.sin(orbTime * cfg.pulseSpeed * 0.4) * 4 + orbReaction * 6 + energy * 10;

                // --- Fondo: partículas de profundidad (menos en modo reducido) ---
                const bgCount = orbReduced ? bgParticles.slice(0, 8) : bgParticles;
                for (let bp of bgCount) {
                    bp.x += bp.vx;
                    bp.y += bp.vy;
                    if (bp.x < 0 || bp.x > w) bp.vx *= -1;
                    if (bp.y < 0 || bp.y > h) bp.vy *= -1;
                    ctx.fillStyle = `rgba(56,189,248,${bp.alpha})`;
                    ctx.beginPath();
                    ctx.arc(bp.x, bp.y, bp.size, 0, Math.PI * 2);
                    ctx.fill();
                }

                // Connection line from mouse to orb center
                if (orbHover) {
                    const dx = cx - mouseX;
                    const dy = cy - mouseY;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < 200) {
                        const lineAlpha = (1 - dist / 200) * 0.25 * pulse;
                        const grad = ctx.createLinearGradient(mouseX, mouseY, cx, cy);
                        grad.addColorStop(0, `rgba(${c1},${lineAlpha})`);
                        grad.addColorStop(1, `rgba(${c2},${lineAlpha * 0.3})`);
                        ctx.strokeStyle = grad;
                        ctx.lineWidth = 1;
                        ctx.beginPath();
                        ctx.moveTo(mouseX, mouseY);
                        ctx.lineTo(cx, cy);
                        ctx.stroke();
                    }
                }

                // Outer glow
                const outerR = radius * 2.2 + orbReaction * 20;
                const outerGrad = ctx.createRadialGradient(cx, cy, radius * 0.5, cx, cy, outerR);
                outerGrad.addColorStop(0, `rgba(${c1},${0.08 * pulse})`);
                outerGrad.addColorStop(0.5, `rgba(${c2},${0.04 * pulse})`);
                outerGrad.addColorStop(1, 'rgba(0,0,0,0)');
                ctx.fillStyle = outerGrad;
                ctx.beginPath();
                ctx.arc(cx, cy, outerR, 0, Math.PI * 2);
                ctx.fill();

                // Glow principal - más intenso estilo Tensura
                const mainGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
                mainGrad.addColorStop(0, `rgba(${c1},${0.35 * pulse})`);
                mainGrad.addColorStop(0.3, `rgba(${c1},${0.20 * pulse})`);
                mainGrad.addColorStop(0.7, `rgba(${c2},${0.12 * pulse})`);
                mainGrad.addColorStop(1, 'rgba(0,0,0,0)');
                ctx.fillStyle = mainGrad;
                ctx.beginPath();
                ctx.arc(cx, cy, radius, 0, Math.PI * 2);
                ctx.fill();

                // --- Anillos orbitales inclinados (2, con cometas luminosos) ---
                if (!orbReduced) {
                    const rings = [
                        { r: radius * 1.18, tilt: cfg.ringTilt, speed: cfg.ringSpeed, dots: 2 },
                        { r: radius * 1.42, tilt: -cfg.ringTilt * 0.7, speed: -cfg.ringSpeed * 0.6, dots: 1 },
                    ];
                    for (const rg of rings) {
                        ctx.save();
                        ctx.translate(cx, cy);
                        ctx.rotate(0.5);
                        ctx.scale(1, Math.cos(rg.tilt));
                        ctx.strokeStyle = `rgba(${c1},${0.35 * pulse})`;
                        ctx.lineWidth = 1.2;
                        ctx.beginPath();
                        ctx.arc(0, 0, rg.r, 0, Math.PI * 2);
                        ctx.stroke();
                        for (let d = 0; d < rg.dots; d++) {
                            const a = orbTime * rg.speed + d * (Math.PI * 2 / rg.dots);
                            const dx = Math.cos(a) * rg.r, dy = Math.sin(a) * rg.r;
                            const g2 = ctx.createRadialGradient(dx, dy, 0, dx, dy, 8);
                            g2.addColorStop(0, `rgba(255,255,255,${0.9 * pulse})`);
                            g2.addColorStop(1, `rgba(${c1},0)`);
                            ctx.fillStyle = g2;
                            ctx.beginPath();
                            ctx.arc(dx, dy, 8, 0, Math.PI * 2);
                            ctx.fill();
                        }
                        ctx.restore();
                    }
                }

                // Anillo exterior
                ctx.strokeStyle = `rgba(${c1},${0.30 * pulse})`;
                ctx.lineWidth = 1.5 + Math.sin(orbTime * cfg.pulseSpeed * 2) * 0.8;
                ctx.beginPath();
                ctx.arc(cx, cy, radius * 0.92, 0, Math.PI * 2);
                ctx.stroke();

                // Partículas orbitantes con trail (cantidad según estado)
                const numParticles = orbReduced ? 6 : (cfg.count || 12);
                for (let i = 0; i < numParticles; i++) {
                    const pAngle = (i / numParticles) * Math.PI * 2;
                    const angle = orbTime * cfg.particleSpeed * 0.8 + pAngle + orbReaction * 0.1;
                    const dist = radius * 0.85 + 8 + (i % 3) * 6 + Math.sin(orbTime * 0.7 + i) * 6;
                    const px = cx + Math.cos(angle) * dist;
                    const py = cy + Math.sin(angle) * dist;
                    const size = 2 + (i % 3) + Math.sin(orbTime * 2 + i) * 1.2;

                    // Trail
                    if (!particles[i]) particles[i] = { trail: [] };
                    particles[i].trail.push({ x: px, y: py, life: 1 });
                    if (particles[i].trail.length > 8) particles[i].trail.shift();
                    for (let t of particles[i].trail) {
                        t.life -= 0.08;
                        if (t.life <= 0) continue;
                        ctx.fillStyle = `rgba(${c1},${t.life * 0.3})`;
                        ctx.beginPath();
                        ctx.arc(t.x, t.y, size * t.life * 0.5, 0, Math.PI * 2);
                        ctx.fill();
                    }

                    // Partícula principal - punto brillante con halo
                    ctx.fillStyle = `rgba(255,255,255,${0.7 + pulse * 0.3})`;
                    ctx.shadowColor = `rgba(${c1},${0.9})`;
                    ctx.shadowBlur = 12 + pulse * 8;
                    ctx.beginPath();
                    ctx.arc(px, py, size, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.shadowBlur = 0;
                }

                // Inner core (núcleo translúcido brillante estilo Tensura)
                const coreR = radius * 0.20 + orbReaction * 0.04;
                const innerGrad = ctx.createRadialGradient(cx - coreR * 0.3, cy - coreR * 0.3, 0, cx, cy, coreR);
                innerGrad.addColorStop(0, `rgba(255,255,255,${0.98 * pulse})`);
                innerGrad.addColorStop(0.2, `rgba(${c1},${0.85 * pulse})`);
                innerGrad.addColorStop(0.6, `rgba(${c1},${0.50 * pulse})`);
                innerGrad.addColorStop(1, `rgba(${c2},${0.15 * pulse})`);
                ctx.fillStyle = innerGrad;
                ctx.shadowColor = `rgba(${c1},${1.0})`;
                ctx.shadowBlur = 25 + pulse * 18;
                ctx.beginPath();
                ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
                ctx.fill();
                ctx.shadowBlur = 0;

                // Destello interno central
                const hotSpot = ctx.createRadialGradient(cx - coreR * 0.25, cy - coreR * 0.25, 0, cx, cy, coreR * 0.55);
                hotSpot.addColorStop(0, `rgba(255,255,255,${0.7 * pulse})`);
                hotSpot.addColorStop(0.5, `rgba(${c1},${0.3 * pulse})`);
                hotSpot.addColorStop(1, 'rgba(255,255,255,0)');
                ctx.fillStyle = hotSpot;
                ctx.beginPath();
                ctx.arc(cx, cy, coreR * 0.55, 0, Math.PI * 2);
                ctx.fill();

                // Efecto "scan" rotatorio (rayo de luz)
                // createConicGradient: soportado en Chromium/WebView2; si no, se omite la capa
                if (typeof ctx.createConicGradient === 'function') {
                    const scanAngle = orbTime * 0.5;
                    ctx.save();
                    ctx.translate(cx, cy);
                    ctx.rotate(scanAngle);
                    const scanGrad = ctx.createConicGradient(0, 0, 0);
                    scanGrad.addColorStop(0, `rgba(${c1},${0.18 * pulse})`);
                    scanGrad.addColorStop(0.08, `rgba(${c1},${0.10 * pulse})`);
                    scanGrad.addColorStop(0.5, 'rgba(0,0,0,0)');
                    scanGrad.addColorStop(1, `rgba(${c1},${0.18 * pulse})`);
                    ctx.fillStyle = scanGrad;
                    ctx.beginPath();
                    ctx.arc(0, 0, radius * 1.1, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.restore();
                }

                orbAnimationId = requestAnimationFrame(draw);
            }
            draw();
        }

        // Cambiar estado visual del orb (espejo de NucleusCanvas.set_status)
        // 'ready' comparte el aspecto de reposo con 'idle' (halo azul) pero con
        // etiqueta verde; el mapeo es explícito (antes: colapso silencioso).
        const ORB_WRAPPER_CLASS = { ready: 'idle' };
        function setOrbState(state) {
            if (!STATE_CONFIG[state]) state = 'idle';   // estado desconocido -> reposo (explícito)
            orbState = state;
            const wrapper = document.getElementById('orbWrapper');
            if (wrapper) wrapper.className = 'orb-wrapper state-' + (ORB_WRAPPER_CLASS[state] || state);
            const label = document.getElementById('orbLabel');
            const labels = {
                idle:      { text: 'Listo y operativo',   cls: 'state-ready' },
                ready:     { text: 'Listo y operativo',   cls: 'state-ready' },
                active:    { text: 'Núcleo activo',       cls: 'state-active' },
                listening: { text: 'Escuchando...',       cls: 'state-listening' },
                thinking:  { text: 'Razonando...',        cls: 'state-thinking' },
                speaking:  { text: 'Hablando...',         cls: 'state-speaking' },
                processing:{ text: 'Procesando...',       cls: 'state-processing' },
                warning:   { text: 'Atención: degradado', cls: 'state-warning' },
                error:     { text: 'Sin conexión',        cls: 'state-error' },
            };
            if (label && labels[state]) {
                label.textContent = labels[state].text;
                label.className = 'orb-label ' + labels[state].cls;
            }
        }

        // Estado del enlace con el backend reflejado en el núcleo (ok | degraded | down).
        // Solo pisa estados de reposo: nunca interrumpe thinking/speaking/listening.
        const RESTING_STATES = { idle: 1, ready: 1, active: 1, warning: 1, error: 1 };
        let orbLinkLevel = null;
        function setOrbLinkState(level) {
            if (orbLinkLevel === level) return;
            const prev = orbLinkLevel;
            orbLinkLevel = level;
            if (prev === null) { /* primer sondeo: sin ruido en el log */ }
            else if (level === 'down') logEvent('Backend sin conexión', 'error');
            else if (prev === 'down' && level === 'ok') logEvent('Backend reconectado', 'success');
            else if (level === 'degraded') logEvent('Sistema degradado', 'warn');
            if (!RESTING_STATES[orbState]) return;   // hay un flujo activo: no interferir
            setOrbState(level === 'down' ? 'error' : level === 'degraded' ? 'warning' : 'ready');
        }

        // Reacción visual ante evento (flash)
        function orbReact() {
            orbReaction = 1;
        }

        function renderSkills() {
            skillGrid.innerHTML = '';
            SKILLS.forEach(skill => {
                const card = document.createElement('div');
                card.className = 'skill-card';
                card.innerHTML = `<div style="font-size:22px">${skill.label.split(' ')[0]}</div><div class="skill-name">${skill.label.slice(2)}<span class="skill-status ready"></span></div>`;
                card.onclick = () => runSkill(skill.name);
                skillGrid.appendChild(card);
            });
        }

        function logEvent(msg, type = 'info') {
            const line = document.createElement('div');
            line.className = 'event-item';
            const time = new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'});
            const cls = type === 'info' ? 'event-info' : type === 'success' ? 'event-success' : type === 'error' ? 'event-error' : 'event-warn';
            line.innerHTML = `<span class="event-time">${time}</span><span class="${cls}">${msg}</span>`;
            eventLog.prepend(line);
            while (eventLog.children.length > 50) eventLog.removeChild(eventLog.lastChild);
        }

        async function updateStatus() {
            try {
                const res = await fetch(API + '/api/system/status');
                const data = await res.json();
                backendStatus.textContent = data.backend;
                backendDot.classList.toggle('warning', data.backend !== 'running');
                setOrbLinkState('ok');
                document.getElementById('cpuVal').textContent = data.cpu !== undefined ? data.cpu + '%' : '--';
                // RAM llega como % (número). Si viene un objeto/undefined se usa un valor neutro.
                const ramPct = typeof data.memory === 'number' ? data.memory : 50;
                document.getElementById('ramVal').textContent = ramPct.toFixed(0) + '%';
                document.getElementById('cpuMetric').textContent = data.cpu !== undefined ? data.cpu + '%' : '--';
                const cpuPct = typeof data.cpu === 'number' ? data.cpu : 20;
                document.getElementById('cpuFill').style.width = cpuPct + '%';
                document.getElementById('ramFill').style.width = ramPct + '%';
                document.getElementById('diskMetric').textContent = (data.disk || 0).toFixed(0) + '%';
                document.getElementById('diskFill').style.width = (data.disk || 0) + '%';
            } catch (e) {
                backendStatus.textContent = 'offline';
                backendDot.classList.add('warning');
                setOrbLinkState('down');
            }
        }

        async function updateHealth() {
            const g = document.getElementById('hGlobal');
            const gf = document.getElementById('hGlobalFill');
            if (!g) return;
            const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
            const colorOf = (st) => st === 'up' || st === 'healthy' || st === 'synced' ? '#22c55e'
                        : st === 'down' || st === 'unhealthy' ? '#ef4444'
                        : st === 'idle' || st === 'independent' ? '#f59e0b' : '#8a2be2';
            try {
                const res = await fetch(API + '/api/system/health', { cache: 'no-store' });
                if (!res.ok) throw new Error('HTTP ' + res.status);
                const d = await res.json();
                const st = d.status || 'unknown';
                g.textContent = st;
                g.style.color = colorOf(st);
                // Solo degradación: la conectividad "down" la decide updateStatus (sondeo más frecuente),
                // así los dos sondeos no se pisan y el núcleo no parpadea.
                if (st !== 'healthy') setOrbLinkState('degraded');
                gf.style.width = (d.status === 'healthy' ? 100 : d.status === 'degraded' ? 60 : 30) + '%';
                gf.style.background = d.status === 'healthy' ? '#22c55e' : d.status === 'degraded' ? '#f59e0b' : '#ef4444';
                const bk = (d.services && d.services.backend) || {};
                set('hBackend', (bk.state || '--'));
                set('hJan', (d.jan && (d.jan.healthy ? 'up' : 'down')) || '--');
                set('hWs', (d.websocket && d.websocket.status) || '--');
                set('hMdns', (d.mdns_peers && d.mdns_peers.count) || 0);
                set('hSd', (d.mobile_sync && d.mobile_sync.status) || '--');
            } catch (e) {
                g.textContent = 'offline';
                g.style.color = colorOf('down');
                gf.style.width = '0%';
            }
        }

        async function updateP2P() {
            const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
            try {
                const res = await fetch(API + '/api/sync/reconcile/status', { cache: 'no-store' });
                if (!res.ok) throw new Error('HTTP ' + res.status);
                const d = await res.json();
                const sum = d.last_summary || {};
                set('p2pDocs', (d.tracked_docs ?? 0) + ' (' + (sum.received ?? 0) + ' últ. lote)');
                set('p2pConflicts', String(sum.conflicts ?? 0));
                set('p2pBackups', String(d.backups_count ?? 0));
                set('p2pLast', d.last_reconcile || '--');
            } catch (e) {
                set('p2pDocs', 'offline');
            }
        }

        function rememberTurn(userText, assistantText) {
            // Conserva el contexto multi-turno hacia el backend (máx. 10 turnos).
            if (!userText) return;
            chatHistory.push([userText, assistantText || ""]);
            while (chatHistory.length > 10) chatHistory.shift();
        }

        function addMessage(text, sender, meta) {
            const div = document.createElement('div');
            div.className = 'message ' + sender;
            div.textContent = text;
            if (meta) {
                const m = document.createElement('div');
                m.className = 'meta';
                m.textContent = meta;
                div.appendChild(m);
            }
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        async function sendMessage() {
            const text = messageInput.value.trim();
            if (!text) return;
            addMessage(text, 'user');
            logEvent('Mensaje enviado: ' + text.slice(0, 40), 'info');
            messageInput.value = '';
            const thinking = document.createElement('div');
            thinking.className = 'message aura';
            thinking.id = 'thinking-' + Date.now();
            thinking.textContent = '';
            chatBox.appendChild(thinking);
            chatBox.scrollTop = chatBox.scrollHeight;
            setOrbState('thinking');
            orbReact();
            const startedAt = performance.now();
            let streamed = false;
            try {
                // Fase 2: streaming SSE directo desde Ollama (token a token)
                // Fase 3: voiceFeed() hace TTS incremental por frases (no espera al final).
                voiceCancel();
                setOrbState('speaking');
                setOrbEnergy(0.35);
                const res = await fetch(API + '/api/chat/stream', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, mode: 'text', history: chatHistory })
                });
                if (!res.ok || !res.body) throw new Error('stream no disponible');
                const reader = res.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buf = '', full = '', lastEnergy = 0;
                for (;;) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buf += decoder.decode(value, { stream: true });
                    let idx;
                    while ((idx = buf.indexOf('\n\n')) >= 0) {
                        const raw = buf.slice(0, idx).trim();
                        buf = buf.slice(idx + 2);
                        if (!raw.startsWith('data:')) continue;
                        const payload = raw.slice(5).trim();
                        if (payload === '[DONE]') continue;
                        try {
                            const ev = JSON.parse(payload);
                            if (ev.token) {
                                full += ev.token;
                                thinking.textContent = full;
                                chatBox.scrollTop = chatBox.scrollHeight;
                                streamed = true;
                                lastEnergy = performance.now();
                                setOrbEnergy(0.35 + Math.min(0.6, full.length % 120 / 200));
                                voiceFeed(ev.token);   // Fase 3: TTS token-a-token
                            } else if (ev.error) {
                                throw new Error(ev.error);
                            }
                        } catch (e) { /* fragmento parcial, seguir */ }
                    }
                    if (performance.now() - lastEnergy > 1500) setOrbEnergy(0.2);
                }
                document.getElementById(thinking.id).remove();
                const ms = Math.round(performance.now() - startedAt);
                const meta = ['ollama · stream', ms + 'ms'].filter(Boolean).join(' · ');
                addMessage(full || 'Sin respuesta', 'aura', meta);
                rememberTurn(text, full);
                orbReact();
                setOrbEnergy(0);
                setOrbState('ready');
                voiceFlush();   // Fase 3: habla el resto (ya no speak(full) al final)
                logEvent('Respuesta stream: ' + (full || 'error').slice(0, 40), 'success');
                return;
            } catch (e) {
                // Fallback clásico no-streaming
                try { document.getElementById(thinking.id).remove(); } catch (_) {}
            }
            const thinking2 = document.createElement('div');
            thinking2.className = 'message aura';
            thinking2.id = 'thinking-' + Date.now();
            thinking2.textContent = 'Pensando...';
            chatBox.appendChild(thinking2);
            chatBox.scrollTop = chatBox.scrollHeight;
            setOrbState('thinking');
            orbReact();
            try {
                const res = await fetch(API + '/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, mode: 'text', history: chatHistory })
                });
                const data = await res.json();
                document.getElementById(thinking2.id).remove();
                const meta = [data.provider, data.latency + 'ms'].filter(Boolean).join(' · ');
                addMessage(data.response || 'Sin respuesta', 'aura', meta);
                rememberTurn(text, data.response);
                orbReact();
                setOrbState('ready');
                if (data.response) speak(data.response);
                logEvent('Respuesta: ' + (data.response || 'error').slice(0, 40), 'success');
            } catch (e) {
                try { document.getElementById(thinking2.id).remove(); } catch (_) {}
                addMessage('Error de conexión', 'aura');
                orbReact();
                setOrbState('ready');
                logEvent('Error: ' + e.message, 'error');
            }
        }

        // ============ Fase 3: Voz en streaming (TTS token-a-token) ============
        // TTS incremental: los tokens del stream se acumulan y se hablan por frases,
        // sin esperar al final de la respuesta. Cola secuencial de utterances.
        const VOICE_WAKE = ['hey aura', 'hola aura', 'ok aura', 'oye aura', 'aura'];
        let voiceBuf = '', voiceQueue = [], voiceSpeaking = false, voiceStreaming = false;
        let voiceAuto = true, wakeMode = false, wakeRec = null;

        function voiceNorm(s) {
            return String(s || '').toLowerCase()
                .replace(/[\u00e1\u00e4]/g, 'a').replace(/[\u00e9\u00eb]/g, 'e').replace(/[\u00ed\u00ef]/g, 'i')
                .replace(/[\u00f3\u00f6]/g, 'o').replace(/[\u00fa\u00fc]/g, 'u').replace(/\u00f1/g, 'n')
                .replace(/\s+/g, ' ').trim();
        }

        // Devuelve [frasesCompletas, resto]. Corta en . ! ? ellipsis \n (min 24 chars).
        function voiceSplit(buf, final) {
            const out = [];
            let rest = buf;
            for (;;) {
                let cut = -1;
                for (let i = 0; i < rest.length; i++) {
                    const ch = rest[i];
                    if ('.!?\u2026\n'.includes(ch)) {
                        const nxt = rest[i + 1] || '';
                        const okNext = nxt === '' || ' \n\t\r"\'),]:;\u00bb'.includes(nxt);
                        const chunk = rest.slice(0, i + 1).trim();
                        if (okNext && (final || chunk.length >= 24)) { cut = i + 1; break; }
                    }
                }
                if (cut < 0) {
                    if (rest.length >= 200) cut = 200; else break;
                }
                const piece = rest.slice(0, cut).trim();
                rest = rest.slice(cut).replace(/^\s+/, '');
                if (piece) out.push(piece);
            }
            return [out, rest];
        }

        function voiceFeed(token) {
            if (!voiceAuto || !token) return;
            voiceStreaming = true;
            voiceBuf += token;
            const split = voiceSplit(voiceBuf, false);
            voiceBuf = split[1];
            split[0].forEach(s => voiceQueue.push(s));
            voicePump();
        }

        function voiceFlush() {
            if (!voiceAuto) { voiceBuf = ''; voiceQueue = []; voiceStreaming = false; return; }
            const split = voiceSplit(voiceBuf, true);
            voiceBuf = '';
            split[0].forEach(s => voiceQueue.push(s));
            if (split[1]) voiceQueue.push(split[1]);
            voiceStreaming = false;
            voicePump();
        }

        function voiceCancel() {
            try { speechSynthesis.cancel(); } catch (_) {}
            voiceBuf = ''; voiceQueue = []; voiceSpeaking = false; voiceStreaming = false;
        }

        function toggleVoiceAuto() {
            voiceAuto = !voiceAuto;
            if (!voiceAuto) voiceCancel();
            const b = document.getElementById('muteBtn');
            if (b) b.textContent = voiceAuto ? '🔊' : '🔇';
            logEvent('Voz automática: ' + (voiceAuto ? 'ON' : 'OFF'), 'info');
        }

        function voicePump() {
            if (voiceSpeaking || !voiceQueue.length) { voiceSettled(); return; }
            if (!('speechSynthesis' in window)) { voiceQueue = []; voiceSettled(); return; }
            const text = voiceQueue.shift();
            voiceSpeaking = true;
            setOrbState('speaking');
            orbReact();
            const utter = new SpeechSynthesisUtterance(text);
            utter.lang = 'es-ES';
            utter.onstart = () => { setOrbState('speaking'); orbReact(); setOrbEnergy(0.4); };
            utter.onboundary = () => { setOrbEnergy(0.3 + Math.random() * 0.5); };
            utter.onend = () => { voiceSpeaking = false; setOrbEnergy(0.2); voicePump(); };
            utter.onerror = () => { voiceSpeaking = false; voicePump(); };
            speechSynthesis.speak(utter);
        }

        // Cuando no hay stream activo ni cola, el núcleo vuelve a reposo.
        function voiceSettled() {
            if (!voiceStreaming && !voiceQueue.length && !voiceSpeaking && !wakeMode && !isListening) {
                setOrbState('ready');
                setOrbEnergy(0);
            }
        }

        // Modo escucha continua: solo envía al chat si detecta el wake word
        // (misma lista que WakeWordDetector.WAKE_WORDS del backend y VoiceEngine).
        function voiceDetectWake(rawText) {
            const norm = voiceNorm(rawText);
            let best = '', pos = -1;
            const words = [...VOICE_WAKE].sort((a, b) => b.length - a.length);
            for (const w of words) {
                const idx = norm.indexOf(voiceNorm(w));
                if (idx >= 0 && (pos < 0 || idx < pos)) { best = w; pos = idx; }
            }
            if (pos < 0) return null;
            const cmd = norm.slice(pos + voiceNorm(best).length).replace(/^[,.:;¡!¿?\- ]+/, '');
            return { wake: best, command: cmd };
        }

        function toggleWake() {
            if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
                alert('Tu navegador no soporta reconocimiento de voz.');
                return;
            }
            const btn = document.getElementById('wakeBtn');
            if (wakeMode) {
                wakeMode = false;
                try { wakeRec && wakeRec.stop(); } catch (_) {}
                if (btn) btn.classList.remove('listening');
                transcription.classList.remove('active');
                logEvent('Modo wake-word desactivado', 'info');
                voiceSettled();
                return;
            }
            wakeMode = true;
            voiceCancel();
            if (isListening && recognition) { try { recognition.stop(); } catch (_) {} }
            wakeRec = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
            wakeRec.lang = 'es-ES';
            wakeRec.interimResults = true;
            wakeRec.continuous = true;
            wakeRec.onstart = () => {
                if (btn) btn.classList.add('listening');
                transcription.classList.add('active');
                transcription.textContent = 'Escucha continua: di "aura" + tu pedido…';
                setOrbState('listening');
                orbReact();
                logEvent('Modo wake-word activado (di "aura" + pedido)', 'info');
            };
            wakeRec.onresult = (event) => {
                let interim = '';
                const finals = [];
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const t = event.results[i][0].transcript;
                    if (event.results[i].isFinal) finals.push(t); else interim += t;
                }
                for (const f of finals) {
                    const hit = voiceDetectWake(f);
                    if (hit && hit.command) {
                        transcription.textContent = '⏵ ' + hit.command;
                        messageInput.value = hit.command;
                        orbReact();
                        sendMessage();
                    } else if (hit) {
                        transcription.textContent = 'Sí, te escucho…';
                        orbReact();
                    } else {
                        transcription.textContent = '…(sin wake word, ignorado)';
                    }
                }
                if (interim) transcription.textContent = interim;
            };
            wakeRec.onerror = (event) => {
                if (event.error === 'not-allowed') {
                    logEvent('Micrófono bloqueado por el navegador', 'error');
                    toggleWake();
                }
            };
            wakeRec.onend = () => {
                // Chrome corta el continuo: reanudar mientras siga el modo.
                if (wakeMode) { try { wakeRec.start(); } catch (_) {} }
                else if (btn) btn.classList.remove('listening');
            };
            wakeRec.start();
        }

        function toggleVoice() {
            if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
                alert('Tu navegador no soporta reconocimiento de voz.');
                return;
            }
            if (isListening) {
                recognition.stop();
                return;
            }
            recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
            recognition.lang = 'es-ES';
            recognition.interimResults = true;
            recognition.continuous = false;
            // Fase 2: energía del micrófono -> núcleo (visualizador de voz)
            try {
                const AC = window.AudioContext || window.webkitAudioContext;
                if (AC) {
                    orbAudioCtx = orbAudioCtx || new AC();
                    if (orbAudioCtx.state === 'suspended') orbAudioCtx.resume();
                    if (!orbMicStream) {
                        navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
                            orbMicStream = stream;
                            const src = orbAudioCtx.createMediaStreamSource(stream);
                            orbAnalyser = orbAudioCtx.createAnalyser();
                            orbAnalyser.fftSize = 512;
                            src.connect(orbAnalyser);
                            orbMicData = new Uint8Array(orbAnalyser.frequencyBinCount);
                            const pump = () => {
                                if (!isListening) { setOrbEnergy(Math.max(0, orbEnergyTarget - 0.3)); return; }
                                orbAnalyser.getByteFrequencyData(orbMicData);
                                let sum = 0;
                                for (let i = 0; i < orbMicData.length; i++) sum += orbMicData[i];
                                const level = sum / orbMicData.length / 255;
                                setOrbEnergy(0.15 + Math.min(0.85, level * 2.2));
                                requestAnimationFrame(pump);
                            };
                            pump();
                        }).catch(() => { /* sin permiso de micro: el orbe igual cambia de estado */ });
                    }
                }
            } catch (e) { /* audio no disponible */ }
            recognition.onstart = () => {
                isListening = true;
                document.getElementById('voiceBtn').classList.add('listening');
                setOrbState('listening');
                orbReact();
                transcription.classList.add('active');
                logEvent('Micrófono activado', 'info');
            };
            recognition.onresult = (event) => {
                let interim = '';
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        messageInput.value = transcript;
                        sendMessage();
                    } else {
                        interim += transcript;
                    }
                }
                transcription.textContent = interim || 'Escuchando...';
                orbReact();
            };
            recognition.onerror = (event) => {
                logEvent('Error voz: ' + event.error, 'error');
                isListening = false;
                document.getElementById('voiceBtn').classList.remove('listening');
                setOrbState('ready');
                orbReact();
                transcription.classList.remove('active');
            };
            recognition.onend = () => {
                isListening = false;
                document.getElementById('voiceBtn').classList.remove('listening');
                setOrbState('ready');
                orbReact();
                transcription.classList.remove('active');
            };
            recognition.start();
        }

        function speak(text) {
            if (!text) return;
            if ('speechSynthesis' in window) {
                const utter = new SpeechSynthesisUtterance(text);
                utter.lang = 'es-ES';
                utter.onstart = () => { setOrbState('speaking'); orbReact(); setOrbEnergy(0.4); };
                utter.onboundary = () => { setOrbEnergy(0.3 + Math.random() * 0.5); };
                utter.onend = () => { setOrbState('idle'); orbReact(); setOrbEnergy(0); };
                utter.onerror = () => { setOrbState('idle'); setOrbEnergy(0); };
                speechSynthesis.speak(utter);
            }
        }

        async function runSkill(skill) {
            logEvent('Ejecutando skill: ' + skill, 'info');
            setOrbState('thinking');
            orbReact();
            try {
                const res = await fetch(API + '/api/skills/' + skill, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: '{}'
                });
                const data = await res.json();
                if (data.result) {
                    const text = JSON.stringify(data.result);
                    addMessage(text, 'aura', 'skill: ' + skill);
                    logEvent('Skill completada: ' + skill, 'success');
                } else {
                    addMessage(JSON.stringify(data), 'aura', 'skill: ' + skill);
                }
            } catch (e) {
                addMessage('Skill no disponible: ' + skill, 'aura');
                logEvent('Error skill: ' + skill, 'error');
            }
            orbReact();
            setOrbState('ready');
        }

        function toggleTheme() {
            const isDark = document.body.style.getPropertyValue('--theme') !== 'light';
            if (isDark) {
                document.body.style.setProperty('--theme', 'light');
                document.documentElement.style.filter = 'invert(0.9) hue-rotate(180deg)';
                document.getElementById('themeToggle').textContent = 'Tema oscuro';
            } else {
                document.documentElement.style.filter = 'none';
                document.getElementById('themeToggle').textContent = 'Tema claro';
            }
        }

        // Init
        initOrb();
        renderSkills();
        updateStatus();
        updateHealth();
        updateP2P();
        setInterval(updateStatus, 3000);
        setInterval(updateHealth, 5000);
        setInterval(updateP2P, 8000);
        logEvent('AURA UI lista', 'success');

        // === Bloque 91: Motor de Refactorización Autónoma ===
        async function auditEvolutionCode() {
            try {
                const r = await fetch(`${API}/api/evolution/patch/audit?root=backend/evolution&max_files=50`);
                const data = await r.json();
                document.getElementById('evoFindings').textContent = data.count;
                addMessage(`Auditoría AST completada: ${data.count} hallazgos en codebase.`, 'system', 'bloque91');
            } catch (e) {
                console.error('Audit error:', e);
                addMessage('Error al auditar código.', 'system', 'error');
            }
        }

        async function proposeRefactor() {
            try {
        setInterval(updateEvolutionPanel, 6000);
                const p = await fetch(`${API}/api/evolution/patch/propose`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        target_file: 'backend/evolution/models.py',
                        old_snippet: '',
                        new_snippet: 'X_REFACTOR_BLOQUE91 = 1\n',
                        description: 'Refactorización autónoma Bloque 91',
                        patch_type: 'refactor'
                    })
                });
                const data = await p.json();
                if (data.patch_id) {
                    addMessage(`Propuesta de parche creada: ${data.patch_id}`, 'system', 'bloque91');
                    document.getElementById('evoPatches').textContent = '1+';
                }
            } catch (e) {
                console.error('Propose error:', e);
                addMessage('Error al proponer refactorización.', 'system', 'error');
            }
        }

        async function updateEvolutionPanel() {
            try {
                const r = await fetch(`${API}/api/evolution/patch/status`);
                const data = await r.json();
                if (data.status === 'ok' && data.engine) {
                    document.getElementById('evoStatus').textContent = data.engine.patches_total > 0 ? 'Activo' : 'Idle';
                    document.getElementById('evoPatches').textContent = data.engine.patches_total || 0;
                    document.getElementById('evoApplied').textContent = data.engine.patches_applied || 0;
                    document.getElementById('evoRollbacks').textContent = data.engine.rollbacks || 0;
                }
            } catch (e) {
                console.error('Evolution status error:', e);
            }
        }
        // === Bloque 92: Planificador de Objetivos ===
        async function decomposeGoal() {
            try {
                const title = prompt('Título del objetivo:', 'Nuevo Objetivo');
                if (!title) return;
                const desc = prompt('Descripción:', '');
                const r = await fetch(`${API}/api/planner/goals/decompose`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        title: title,
                        description: desc || '',
                        milestones: [{title: 'Planificar', description: 'Planificar la ejecución'},
                                     {title: 'Ejecutar', description: 'Implementar solución'},
                                     {title: 'Verificar', description: 'Validar resultados'}]
                    })
                });
                const data = await r.json();
                if (data.goal_id) {
                    addMessage(`Goal creado: ${data.title} (${data.goal_id.substring(0,12)}...)`, 'system', 'bloque92');
                    document.getElementById('planGoals').textContent = '1+';
                    updatePlannerPanel();
                }
            } catch (e) {
                console.error('Decompose goal error:', e);
                addMessage('Error al descomponer objetivo.', 'system', 'error');
            }
        }

        async function updatePlannerPanel() {
            try {
                const r = await fetch(`${API}/api/planner/goals/status`);
                const data = await r.json();
                if (data.goals_total !== undefined) {
                    document.getElementById('planGoals').textContent = data.goals_total || 0;
                    document.getElementById('planDone').textContent = data.goals_done || 0;
                    document.getElementById('planInProgress').textContent = data.goals_in_progress || 0;
                    document.getElementById('planBlocked').textContent = data.goals_blocked || 0;
                    const pct = data.goals_total > 0 ? Math.round((data.goals_done / data.goals_total) * 100) : 0;
                    document.getElementById('planProgressPct').textContent = pct + '%';
                    document.getElementById('planEngineStatus').textContent = data.goals_total > 0 ? 'Activo' : 'Idle';
                }
            } catch (e) {
                console.error('Planner status error:', e);
            }
        }
        // === Fin Bloque 92 ===
        // Fin Bloque 91
        // === Bloque 93: Mercado de Habilidades ===
        async function publishSkill() {
            try {
                const name = prompt('Nombre de la habilidad:', 'NewSkill');
                if (!name) return;
                const cat = prompt('Categoría (code/security/rag/vision/data/network/audio):', 'code');
                const desc = prompt('Descripción:', '');
                const r = await fetch(`${API}/api/swarm/marketplace/publish`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name: name, category: cat || 'code', description: desc || '', owner: 'local'})
                });
                const data = await r.json();
                if (data.skill_id) {
                    addMessage(`Habilidad publicada: ${data.name} (${data.skill_id.substring(0,12)}...)`, 'system', 'bloque93');
                    document.getElementById('swarmSkills').textContent = '1+';
                }
            } catch (e) {
                console.error('Publish skill error:', e);
                addMessage('Error al publicar habilidad.', 'system', 'error');
            }
        }

        async function discoverSkills() {
            try {
                const cat = prompt('Categoría a buscar (vacío=todas):', '');
                const url = `${API}/api/swarm/marketplace/discover` + (cat ? `?category=${cat}` : '');
                const r = await fetch(url);
                const data = await r.json();
                if (data.skills) {
                    const names = data.skills.map(s => s.name).join(', ') || '(vacío)';
                    addMessage(`Habilidades encontradas (${data.count}): ${names}`, 'system', 'bloque93');
                }
            } catch (e) {
                console.error('Discover skills error:', e);
                addMessage('Error al descubrir habilidades.', 'system', 'error');
            }
        }

        async function updateSwarmPanel() {
            try {
                const r = await fetch(`${API}/api/swarm/marketplace/status`);
                const data = await r.json();
                if (data.nodes !== undefined) {
                    document.getElementById('swarmNodes').textContent = data.nodes || 0;
                    document.getElementById('swarmSkills').textContent = data.skills || 0;
                    document.getElementById('swarmAssign').textContent = data.assignments || 0;
                    document.getElementById('swarmRep').textContent = (data.avg_reputation || 1.0).toFixed(2);
                    document.getElementById('swarmStatus').textContent = (data.nodes > 0) ? 'Activo' : 'Idle';
                }
            } catch (e) {
                console.error('Swarm status error:', e);
            }
        }
        // === Bloque 94: ZKP y Auditoría ===
        let _zk_last_proof = null;

        async function generateZKP() {
            try {
                const r = await fetch(`${API}/api/security/zkp/prove`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({node_id: 'local-node', claim: 'identity'})
                });
                const data = await r.json();
                if (data.proof) {
                    _zk_last_proof = data.proof;
                    addMessage(`Prueba ZKP generada: ${data.proof.proof_id.substring(0,12)}...`, 'system', 'bloque94');
                    document.getElementById('zkProofs').textContent = '1+';
                    updateZKPanel();
                }
            } catch (e) {
                console.error('ZKP prove error:', e);
                addMessage('Error al generar prueba ZKP.', 'system', 'error');
            }
        }

        async function verifyZKP() {
            try {
                if (!_zk_last_proof) {
                    await generateZKP();
                    return;
                }
                const r = await fetch(`${API}/api/security/zkp/verify`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        proof_id: _zk_last_proof.proof_id,
                        commitment: _zk_last_proof.commitment,
                        challenge: _zk_last_proof.challenge,
                        response: _zk_last_proof.response,
                        public_y: _zk_last_proof.public_y,
                        claim: _zk_last_proof.claim
                    })
                });
                const data = await r.json();
                if (data.valid) {
                    addMessage(`Prueba ZKP VÁLIDA - verificada correctamente`, 'system', 'bloque94');
                } else {
                    addMessage(`Prueba ZKP INVÁLIDA`, 'system', 'error');
                }
            } catch (e) {
                console.error('ZKP verify error:', e);
                addMessage('Error al verificar prueba ZKP.', 'system', 'error');
            }
        }

        async function updateZKPanel() {
            try {
                const r = await fetch(`${API}/api/security/zkp/status`);
                const data = await r.json();
                if (data.zkp_scheme) {
                    document.getElementById('zkScheme').textContent = data.zkp_scheme;
                    document.getElementById('zkAuditEntries').textContent = data.audit_entries || 0;
                    document.getElementById('zkEngineStatus').textContent = data.status || 'ok';
                }
                const ar = await fetch(`${API}/api/security/zkp/audit/verify`);
                const adata = await ar.json();
                document.getElementById('zkChainValid').textContent = adata.chain_valid ? 'Sí' : 'No';
            } catch (e) {
                console.error('ZKP status error:', e);
            }
        }
        // === Bloque 95: Sincronización Cross-Device ===
        async function syncRegisterPeer() {
            try {
                const peerId = prompt('ID del par:', 'peer_' + Date.now().toString(36));
                if (!peerId) return;
                const ip = prompt('IP (vacío=auto):', '');
                const r = await fetch(`${API}/api/daemon/sync/peers/register`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({peer_id: peerId, ip_address: ip || '192.168.1.0', capabilities: ['code', 'rag']})
                });
                const data = await r.json();
                if (data.node_id) {
                    addMessage(`Par registrado: ${data.node_id}`, 'system', 'bloque95');
                    document.getElementById('syncPeers').textContent = '1+';
                }
            } catch (e) {
                console.error('Register peer error:', e);
                addMessage('Error al registrar par.', 'system', 'error');
            }
        }

        async function syncWithPeer() {
            try {
                const peerId = prompt('ID del par a sincronizar:', '');
                if (!peerId) return;
                const r = await fetch(`${API}/api/daemon/sync/sync`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({peer_id: peerId, state_data: {memory: Date.now(), status: 'active'}})
                });
                const data = await r.json();
                if (data.sync) {
                    addMessage(`Sincronización exitosa con ${peerId}`, 'system', 'bloque95');
                }
            } catch (e) {
                console.error('Sync error:', e);
                addMessage('Error en sincronización.', 'system', 'error');
            }
        }

        async function updateSyncPanel() {
            try {
                const r = await fetch(`${API}/api/daemon/sync/status`);
                const data = await r.json();
                if (data.sync) {
                    document.getElementById('syncNodeId').textContent = (data.sync.local_node_id || '').substring(0, 12);
                    document.getElementById('syncPeers').textContent = data.sync.peers_count || 0;
                    document.getElementById('syncDaemonStatus').textContent = data.daemon.running ? 'Running' : 'Stopped';
                    document.getElementById('syncUptime').textContent = Math.round(data.daemon.uptime_seconds || 0) + 's';
                }
                const hr = await fetch(`${API}/api/daemon/sync/health`);
                const hd = await hr.json();
                document.getElementById('syncHealth').textContent = hd.healthy ? 'OK' : 'FAIL';
            } catch (e) {
                console.error('Sync status error:', e);
            }
        }
        // === Fin Bloque 95 ===
        // === Fin Bloque 94 ===
        // === Fin Bloque 93 ===
        // Fin Bloque 91
        addMessage('Sistemas en línea. Núcleo activo, 16 habilidades operativas.', 'aura', 'v2.0.0');

        // === ARIA Widget Integration ===
        (function() {
            const ariaBtn = document.createElement('div');
            ariaBtn.id = 'aria-float-btn';
            ariaBtn.innerHTML = '<span style="font-size:20px">💎</span>';
            ariaBtn.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;width:48px;height:48px;background:radial-gradient(circle,#1a2332,#0f172a);border:1px solid rgba(56,189,248,0.4);border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 0 20px rgba(56,189,248,0.3);transition:all 0.3s;font-size:20px;';
            ariaBtn.title = 'ARIA — Asistente Visual';
            document.body.appendChild(ariaBtn);
            ariaBtn.addEventListener('mouseenter', function() {
                ariaBtn.style.boxShadow = '0 0 40px rgba(56,189,248,0.6)';
                ariaBtn.style.transform = 'scale(1.1)';
            });
            ariaBtn.addEventListener('mouseleave', function() {
                ariaBtn.style.boxShadow = '0 0 20px rgba(56,189,248,0.3)';
                ariaBtn.style.transform = 'scale(1)';
            });
            ariaBtn.addEventListener('click', function() {
                window.open('/aria_widget.html', 'ARIA', 'width=440,height=560,top=100,left=100');
            });
        })();
    