/**
 * ghost_mode_toggle.js - Interruptor visual para el Ghost Mode
 * Controla el modo piloto automático de AURA: acciones de bajo riesgo sin aprobación humana
 */

// Variable global para el estado del Ghost Mode
let ghostModeActive = false;
const GHOST_MODE_API = 'http://localhost:5001/api/ghost_mode';

// Crear e insertar el interruptor Ghost Mode en el panel lateral del Dashboard
function createGhostModeToggle() {
    // Buscar el panel lateral o crear uno nuevo
    let sidebar = document.querySelector('.dashboard-sidebar');
    if (!sidebar) {
        sidebar = document.createElement('div');
        sidebar.className = 'dashboard-sidebar';
        sidebar.style.cssText = `
            position: fixed; top: 0; left: 0; width: 280px; height: 100vh;
            background: rgba(10, 10, 30, 0.95); backdrop-filter: blur(10px);
            border-right: 1px solid rgba(0, 255, 255, 0.2);
            padding: 20px; z-index: 1000;
            display: flex; flex-direction: column; gap: 20px;
            font-family: 'Courier New', monospace; color: #00ffff;
        `;
        document.body.appendChild(sidebar);
    }

    // Crear el contenedor del interruptor
    const toggleContainer = document.createElement('div');
    toggleContainer.className = 'ghost-toggle-container';
    toggleContainer.style.cssText = `
        background: rgba(0, 255, 255, 0.05); border: 1px solid rgba(0, 255, 255, 0.2);
        border-radius: 12px; padding: 16px; margin-bottom: 10px;
        transition: all 0.3s ease;
    `;

    // Título del interruptor
    const titleRow = document.createElement('div');
    titleRow.style.cssText = `
        display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;
    `;

    const title = document.createElement('div');
    title.style.cssText = `
        font-size: 16px; font-weight: bold; text-transform: uppercase;
        letter-spacing: 2px; display: flex; align-items: center; gap: 8px;
    `;
    title.innerHTML = `
        <span style="font-size: 18px;">👻</span>
        <span>GHOST MODE</span>
        <span id="ghost-status-badge" style="
            font-size: 10px; background: rgba(255, 0, 0, 0.2); color: #ff4444;
            padding: 2px 8px; border-radius: 10px; border: 1px solid #ff4444;
        ">OFF</span>
    `;

    // Crear el interruptor toggle
    const toggleSwitch = document.createElement('div');
    toggleSwitch.style.cssText = `
        position: relative; width: 50px; height: 28px; cursor: pointer;
        background: rgba(255, 0, 0, 0.3); border-radius: 14px;
        border: 1px solid rgba(255, 0, 0, 0.5); transition: all 0.3s ease;
    `;
    toggleSwitch.innerHTML = `
        <div id="ghost-toggle-knob" style="
            position: absolute; top: 2px; left: 2px; width: 22px; height: 22px;
            background: #ff4444; border-radius: 50%; transition: all 0.3s ease;
            box-shadow: 0 0 10px rgba(255, 0, 0, 0.5);
        "></div>
    `;

    titleRow.appendChild(title);
    titleRow.appendChild(toggleSwitch);

    // Descripción del estado
    const statusDesc = document.createElement('div');
    statusDesc.id = 'ghost-status-description';
    statusDesc.style.cssText = `
        font-size: 11px; color: rgba(255, 255, 255, 0.6);
        line-height: 1.4; margin-top: 8px; padding: 8px;
        background: rgba(0, 0, 0, 0.3); border-radius: 6px;
        border-left: 3px solid #ff4444;
    `;
    statusDesc.textContent = '⚠ BAJO: Acciones de bajo riesgo requieren aprobación manual';

    // Estadísticas del Ghost Mode
    const statsContainer = document.createElement('div');
    statsContainer.id = 'ghost-stats';
    statsContainer.style.cssText = `
        margin-top: 10px; padding: 8px; background: rgba(0, 0, 0, 0.2);
        border-radius: 6px; font-size: 11px; color: rgba(255, 255, 255, 0.5);
        display: none;
    `;
    statsContainer.innerHTML = `
        <div>Auto-ejecutadas: <span id="ghost-auto-count">0</span></div>
        <div>Requieren aprobación: <span id="ghost-pending-count">0</span></div>
        <div>Última acción: <span id="ghost-last-action">—</span></div>
    `;

    toggleContainer.appendChild(titleRow);
    toggleContainer.appendChild(statusDesc);
    toggleContainer.appendChild(statsContainer);

    // Evento de clic para el toggle
    toggleSwitch.addEventListener('click', () => {
        ghostModeActive = !ghostModeActive;
        updateGhostModeUI(ghostModeActive);
        notifyGhostModeChange(ghostModeActive);
    });

    // Insertar en el sidebar
    sidebar.insertBefore(toggleContainer, sidebar.firstChild);

    // Añadir estilos globales
    addGhostModeStyles();
}

// Actualizar la interfaz del Ghost Mode
function updateGhostModeUI(active) {
    const toggle = document.getElementById('ghost-toggle-knob');
    const badge = document.getElementById('ghost-status-badge');
    const desc = document.getElementById('ghost-status-description');
    const stats = document.getElementById('ghost-stats');
    const container = document.querySelector('.ghost-toggle-container');

    if (!toggle || !badge) return;

    if (active) {
        // Modo activo
        toggle.style.left = '24px';
        toggle.style.background = '#00ff88';
        toggle.style.boxShadow = '0 0 15px rgba(0, 255, 136, 0.7)';
        
        toggleSwitch.style.background = 'rgba(0, 255, 136, 0.3)';
        toggleSwitch.style.borderColor = 'rgba(0, 255, 136, 0.5)';
        
        badge.textContent = 'ON';
        badge.style.color = '#00ff88';
        badge.style.borderColor = '#00ff88';
        badge.style.background = 'rgba(0, 255, 136, 0.2)';
        
        desc.textContent = '✅ AUTO: Acciones de bajo riesgo se ejecutan sin aprobación';
        desc.style.borderLeftColor = '#00ff88';
        
        if (stats) stats.style.display = 'block';
        if (container) container.style.borderColor = 'rgba(0, 255, 136, 0.4)';
    } else {
        // Modo inactivo
        toggle.style.left = '2px';
        toggle.style.background = '#ff4444';
        toggle.style.boxShadow = '0 0 10px rgba(255, 0, 0, 0.5)';
        
        toggleSwitch.style.background = 'rgba(255, 0, 0, 0.3)';
        toggleSwitch.style.borderColor = 'rgba(255, 0, 0, 0.5)';
        
        badge.textContent = 'OFF';
        badge.style.color = '#ff4444';
        badge.style.borderColor = '#ff4444';
        badge.style.background = 'rgba(255, 0, 0, 0.2)';
        
        desc.textContent = '⚠ BAJO: Acciones de bajo riesgo requieren aprobación manual';
        desc.style.borderLeftColor = '#ff4444';
        
        if (stats) stats.style.display = 'none';
        if (container) container.style.borderColor = 'rgba(0, 255, 255, 0.2)';
    }
}

// Notificar al backend sobre el cambio de Ghost Mode
function notifyGhostModeChange(active) {
    try {
        fetch(GHOST_MODE_API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ghost_mode: active })
        }).then(response => {
            if (response.ok) {
                console.log(`Ghost Mode ${active ? 'activado' : 'desactivado'}`);
                // Mostrar notificación visual
                showGhostNotification(active);
            }
        }).catch(err => console.error('Error al notificar Ghost Mode:', err));
    } catch (e) {
        console.error('Error al comunicar Ghost Mode:', e);
    }
}

// Mostrar notificación visual cuando cambia el Ghost Mode
function showGhostNotification(active) {
    const notif = document.createElement('div');
    notif.style.cssText = `
        position: fixed; top: 20px; right: 20px; padding: 16px 24px;
        background: ${active ? 'rgba(0, 255, 136, 0.15)' : 'rgba(255, 68, 68, 0.15)'};
        border: 1px solid ${active ? '#00ff88' : '#ff4444'};
        border-radius: 8px; color: ${active ? '#00ff88' : '#ff4444'};
        font-family: 'Courier New', monospace; font-size: 14px;
        z-index: 9999; backdrop-filter: blur(10px);
        animation: slideInRight 0.3s ease;
    `;
    notif.innerHTML = `
        <div style="display: flex; align-items: center; gap: 12px;">
            <span>${active ? '👻' : '🔒'}</span>
            <div>
                <div style="font-weight: bold;">GHOST MODE ${active ? 'ACTIVADO' : 'DESACTIVADO'}</div>
                <div style="font-size: 11px; opacity: 0.7;">
                    ${active ? 'Acciones de bajo riesgo se ejecutan automáticamente' : 'Todas las acciones requieren aprobación manual'}
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(notif);
    setTimeout(() => {
        notif.style.animation = 'fadeOutRight 0.3s ease';
        setTimeout(() => notif.remove(), 300);
    }, 3000);
}

// Destello visual en nodo 3D correspondiente
function flashNode(nodeId, color = '#00ff88') {
    // Buscar el nodo en la escena 3D
    const node = document.querySelector(`[data-node-id="${nodeId}"]`);
    if (node) {
        // Añadir efecto de flash
        node.style.transition = 'filter 0.3s ease, box-shadow 0.3s ease';
        node.style.filter = `drop-shadow(0 0 20px ${color})`;
        node.style.boxShadow = `0 0 30px ${color}`;
        
        // Remover efecto después de 1 segundo
        setTimeout(() => {
            node.style.filter = '';
            node.style.boxShadow = '';
        }, 1500);
    }
}

// Registrar acción automática en los logs laterales
function logAutoAction(message, threatLevel) {
    const logContainer = document.getElementById('log-container') || document.querySelector('.log-panel');
    if (!logContainer) return;

    const logEntry = document.createElement('div');
    logEntry.style.cssText = `
        padding: 6px 10px; margin: 4px 0;
        background: rgba(0, 255, 136, 0.05);
        border-left: 3px solid #00ff88;
        font-size: 11px; color: #00ff88;
        animation: fadeIn 0.3s ease;
    `;
    
    const timestamp = new Date().toLocaleTimeString();
    logEntry.innerHTML = `
        <span style="color: rgba(255,255,255,0.4);">[${timestamp}]</span>
        <span style="color: #00ff88;">👻 AUTO</span>
        <span style="color: rgba(255,255,255,0.8);">${message}</span>
        <span style="color: rgba(255,255,255,0.4);">[T:${threatLevel}/10]</span>
    `;

    logContainer.appendChild(logEntry);
    logContainer.scrollTop = logContainer.scrollHeight;
}

// Añadir estilos globales para animaciones
function addGhostModeStyles() {
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideInRight {
            from { transform: translateX(100px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes fadeOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100px); opacity: 0; }
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-5px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulseGhost {
            0%, 100% { box-shadow: 0 0 10px rgba(0, 255, 136, 0.3); }
            50% { box-shadow: 0 0 20px rgba(0, 255, 136, 0.6); }
        }
        .ghost-mode-active {
            animation: pulseGhost 2s ease-in-out infinite;
        }
    `;
    document.head.appendChild(style);
}

// Actualizar estadísticas del Ghost Mode
function updateGhostStats(autoCount, pendingCount, lastAction) {
    const autoEl = document.getElementById('ghost-auto-count');
    const pendingEl = document.getElementById('ghost-pending-count');
    const lastEl = document.getElementById('ghost-last-action');
    
    if (autoEl) autoEl.textContent = autoCount || 0;
    if (pendingEl) pendingEl.textContent = pendingCount || 0;
    if (lastEl) lastEl.textContent = lastAction || '—';
}

// Inicializar el Ghost Mode cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Crear el toggle switch
    createGhostModeToggle();
    
    // Verificar estado actual del Ghost Mode desde el backend
    try {
        fetch('http://localhost:5001/api/ghost_mode')
            .then(response => response.json())
            .then(data => {
                if (data.ghost_mode !== undefined) {
                    ghostModeActive = data.ghost_mode;
                    updateGhostModeUI(ghostModeActive);
                }
            })
            .catch(() => {
                // Si no hay conexión, mantener el estado local
                console.log('Ghost Mode: No se pudo conectar con el backend');
            });
    } catch (e) {
        console.log('Ghost Mode: Error de conexión inicial');
    }
});

// Hacer accesibles las funciones globalmente
window.flashNode = flashNode;
window.logAutoAction = logAutoAction;
window.updateGhostStats = updateGhostStats;
window.ghostModeActive = ghostModeActive;