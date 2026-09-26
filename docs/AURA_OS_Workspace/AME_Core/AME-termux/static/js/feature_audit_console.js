/**
 * feature_audit_console.js - Panel de auditoría de funciones AURA
 * Permite ver funciones implementadas y enviar sugerencias de nuevas características.
 * Persiste en feature_roadmap.json para seguimiento del roadmap.
 */

// ===== CONFIGURACIÓN =====
const FEATURES = [
    { id: 'osint', name: 'OSINT Recon', status: 'implemented', desc: 'Búsqueda de inteligencia de fuentes abiertas' },
    { id: 'rss', name: 'Feed RSS', status: 'implemented', desc: 'Procesamiento de noticias de seguridad en tiempo real' },
    { id: 'llm', name: 'LLM Analyzer', status: 'implemented', desc: 'Análisis inteligente con modelos de lenguaje' },
    { id: 'executor', name: 'Action Executor', status: 'implemented', desc: 'Ejecución de acciones automáticas en el sistema' },
    { id: 'ghost_mode', name: 'Ghost Mode', status: 'implemented', desc: 'Modo piloto automático con bypass inteligente' },
    { id: 'decision_core', name: 'Decision Core', status: 'implemented', desc: 'Núcleo de toma de decisiones con IA' },
    { id: 'threat_scanner', name: 'Threat Scanner', status: 'implemented', desc: 'Escaneo activo de vulnerabilidades NVD' },
    { id: 'learning_profile', name: 'Perfil de Aprendizaje', status: 'implemented', desc: 'Sistema que aprende de tus aprobaciones' },
    { id: 'web_search', name: 'Búsqueda Web', status: 'implemented', desc: 'Búsqueda DuckDuckGo para contexto adicional' },
    { id: 'obsidian', name: 'Obsidian Sync', status: 'implemented', desc: 'Sincronización con tu bóveda de Obsidian' },
    { id: 'bloom_ui', name: 'Bloom Effect UI', status: 'implemented', desc: 'Efecto visual de resplandor en nodos 3D' },
    { id: 'hud_tactico', name: 'HUD Táctico', status: 'implemented', desc: 'Heads-Up Display con datos en tiempo real' },
    { id: 'camara_cine', name: 'Cámara Cinematográfica', status: 'implemented', desc: 'Órbita automática suave alrededor de nodos' },
    { id: 'action_queue', name: 'Action Queue', status: 'implemented', desc: 'Cola de acciones pendientes de aprobación' },
];

const ROADMAP_FILE = 'feature_roadmap.json';

// ===== CONTADOR DE FUNCIONES =====
function getFeatureStats() {
    const total = FEATURES.length;
    const implemented = FEATURES.filter(f => f.status === 'implemented').length;
    const planned = FEATURES.filter(f => f.status === 'planned').length;
    return { total, implemented, planned, progress: Math.round((implemented / total) * 100) };
}

// ===== CREAR BOTÓN [?] EN EL HUD =====
function addFeatureAuditButton() {
    const btn = document.createElement('div');
    btn.id = 'feature-audit-btn';
    btn.style.cssText = `
        position: fixed; bottom: 100px; right: 20px;
        width: 36px; height: 36px; border-radius: 50%;
        background: rgba(0, 255, 255, 0.1);
        border: 1px solid rgba(0, 255, 255, 0.3);
        color: #00ffff; font-size: 16px; font-weight: bold;
        display: flex; align-items: center; justify-content: center;
        cursor: pointer; z-index: 500;
        font-family: 'Courier New', monospace;
        transition: all 0.3s ease;
        backdrop-filter: blur(4px);
        box-shadow: 0 0 10px rgba(0, 255, 255, 0.1);
    `;
    btn.textContent = '?';
    btn.title = 'Auditoría de Funciones - Roadmap AURA';
    
    btn.addEventListener('mouseenter', () => {
        btn.style.background = 'rgba(0, 255, 255, 0.2)';
        btn.style.boxShadow = '0 0 20px rgba(0, 255, 255, 0.3)';
    });
    btn.addEventListener('mouseleave', () => {
        btn.style.background = 'rgba(0, 255, 255, 0.1)';
        btn.style.boxShadow = '0 0 10px rgba(0, 255, 255, 0.1)';
    });
    btn.addEventListener('click', toggleFeaturePanel);
    
    document.body.appendChild(btn);
    
    // Añadir badge con contador
    const stats = getFeatureStats();
    const badge = document.createElement('div');
    badge.id = 'feature-count-badge';
    badge.style.cssText = `
        position: fixed; bottom: 138px; right: 20px;
        font-size: 9px; color: rgba(0, 255, 255, 0.5);
        font-family: 'Courier New', monospace; z-index: 500;
        text-align: center; line-height: 1.3;
    `;
    badge.innerHTML = `${stats.implemented}/${stats.total}<br><span style="font-size:8px;">FEATURES</span>`;
    document.body.appendChild(badge);
}

// ===== PANEL DE AUDITORÍA =====
function createFeaturePanel() {
    // Verificar si ya existe
    let panel = document.getElementById('feature-audit-panel');
    if (panel) {
        panel.remove();
        document.getElementById('feature-audit-overlay')?.remove();
        return;
    }

    // Overlay
    const overlay = document.createElement('div');
    overlay.id = 'feature-audit-overlay';
    overlay.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.5); z-index: 300;
        backdrop-filter: blur(2px);
    `;
    overlay.addEventListener('click', closeFeaturePanel);
    document.body.appendChild(overlay);

    // Panel
    panel = document.createElement('div');
    panel.id = 'feature-audit-panel';
    panel.style.cssText = `
        position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
        width: 600px; max-height: 80vh;
        background: rgba(10, 10, 30, 0.95);
        border: 1px solid rgba(0, 255, 255, 0.2);
        border-radius: 12px; padding: 24px;
        z-index: 400; backdrop-filter: blur(20px);
        font-family: 'Courier New', monospace;
        overflow-y: auto;
        box-shadow: 0 0 40px rgba(0, 255, 255, 0.1);
    `;

    // Header
    const header = document.createElement('div');
    header.style.cssText = `
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 20px; padding-bottom: 12px;
        border-bottom: 1px solid rgba(0, 255, 255, 0.15);
    `;
    const stats = getFeatureStats();
    header.innerHTML = `
        <div>
            <div style="font-size: 16px; color: #00ffff; font-weight: bold; letter-spacing: 2px;">
                🗺️ ROADMAP AURA
            </div>
            <div style="font-size: 10px; color: rgba(0,255,255,0.4); margin-top: 4px;">
                Funciones implementadas: <span style="color: #00ff88;">${stats.implemented}</span> / ${stats.total} 
                (${stats.progress}%)
            </div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
            <div style="font-size: 10px; color: rgba(0,255,255,0.4);">
                <span style="color:#00ff88;">●</span> Implementado
            </div>
            <div id="feature-close-btn" style="
                width: 28px; height: 28px; border-radius: 50%;
                background: rgba(255,0,0,0.1); border: 1px solid rgba(255,0,0,0.3);
                color: #ff4444; display: flex; align-items: center; justify-content: center;
                cursor: pointer; font-size: 14px; transition: all 0.3s;
            ">✕</div>
        </div>
    `;
    panel.appendChild(header);

    // Barra de progreso
    const progressBar = document.createElement('div');
    progressBar.style.cssText = `
        height: 3px; background: rgba(0,255,255,0.1); border-radius: 2px;
        margin-bottom: 20px; overflow: hidden;
    `;
    progressBar.innerHTML = `<div style="
        height: 100%; width: ${stats.progress}%;
        background: linear-gradient(90deg, #00ffff, #00ff88);
        border-radius: 2px; transition: width 1s ease;
    "></div>`;
    panel.appendChild(progressBar);

    // Lista de funciones
    const list = document.createElement('div');
    list.style.cssText = `display: flex; flex-direction: column; gap: 6px; margin-bottom: 20px;`;

    FEATURES.forEach(feature => {
        const item = document.createElement('div');
        const isImplemented = feature.status === 'implemented';
        item.style.cssText = `
            display: flex; align-items: center; gap: 12px;
            padding: 8px 12px; border-radius: 6px;
            background: ${isImplemented ? 'rgba(0,255,136,0.05)' : 'rgba(255,255,0,0.05)'};
            border: 1px solid ${isImplemented ? 'rgba(0,255,136,0.15)' : 'rgba(255,255,0,0.1)'};
            transition: all 0.3s;
        `;
        item.innerHTML = `
            <span style="color: ${isImplemented ? '#00ff88' : '#ffff00'}; font-size: 10px;">
                ${isImplemented ? '✓' : '○'}
            </span>
            <div style="flex: 1;">
                <div style="font-size: 12px; color: ${isImplemented ? '#00ffff' : 'rgba(0,255,255,0.6)'};">
                    ${feature.name}
                </div>
                <div style="font-size: 9px; color: rgba(0,255,255,0.3);">
                    ${feature.desc}
                </div>
            </div>
            <span style="font-size: 9px; color: ${isImplemented ? '#00ff88' : '#ffff00'};
                background: ${isImplemented ? 'rgba(0,255,136,0.1)' : 'rgba(255,255,0,0.1)'};
                padding: 2px 8px; border-radius: 10px;">
                ${isImplemented ? 'LISTO' : 'PLAN'}
            </span>
        `;
        list.appendChild(item);
    });

    panel.appendChild(list);

    // Sección de sugerencias
    const suggestionsSection = document.createElement('div');
    suggestionsSection.style.cssText = `
        border-top: 1px solid rgba(0,255,255,0.15); padding-top: 16px;
    `;

    const suggestionTitle = document.createElement('div');
    suggestionTitle.style.cssText = `
        font-size: 11px; color: rgba(0,255,255,0.6); margin-bottom: 8px;
        letter-spacing: 1px; text-transform: uppercase;
    `;
    suggestionTitle.textContent = '💡 Nueva idea o sugerencia';
    suggestionsSection.appendChild(suggestionTitle);

    const textarea = document.createElement('textarea');
    textarea.id = 'feature-suggestion-input';
    textarea.placeholder = 'Describe tu idea aquí... (se guardará automáticamente)';
    textarea.style.cssText = `
        width: 100%; height: 80px;
        background: rgba(0,0,0,0.3); border: 1px solid rgba(0,255,255,0.2);
        border-radius: 6px; padding: 10px; color: #00ffff;
        font-family: 'Courier New', monospace; font-size: 11px;
        resize: vertical; outline: none;
    `;
    suggestionsSection.appendChild(textarea);

    // Historial de sugerencias
    const historyContainer = document.createElement('div');
    historyContainer.id = 'suggestion-history';
    historyContainer.style.cssText = `
        margin-top: 12px; max-height: 120px; overflow-y: auto;
    `;
    suggestionsSection.appendChild(historyContainer);

    // Botón guardar
    const saveBtn = document.createElement('button');
    saveBtn.style.cssText = `
        margin-top: 10px; padding: 6px 16px;
        background: rgba(0,255,255,0.1); border: 1px solid rgba(0,255,255,0.3);
        color: #00ffff; border-radius: 4px; cursor: pointer;
        font-family: 'Courier New', monospace; font-size: 11px;
        text-transform: uppercase; letter-spacing: 1px;
        transition: all 0.3s;
    `;
    saveBtn.textContent = '💾 Guardar Sugerencia';
    saveBtn.addEventListener('click', saveSuggestion);
    saveBtn.addEventListener('mouseenter', () => {
        saveBtn.style.background = 'rgba(0,255,255,0.2)';
        saveBtn.style.boxShadow = '0 0 15px rgba(0,255,255,0.2)';
    });
    saveBtn.addEventListener('mouseleave', () => {
        saveBtn.style.background = 'rgba(0,255,255,0.1)';
        saveBtn.style.boxShadow = 'none';
    });
    suggestionsSection.appendChild(saveBtn);

    panel.appendChild(suggestionsSection);

    // Cargar sugerencias previas
    loadSuggestions();

    document.body.appendChild(panel);

    // Evento cerrar
    document.getElementById('feature-close-btn').addEventListener('click', closeFeaturePanel);

    // Auto-guardar al escribir (debounced)
    let saveTimeout;
    textarea.addEventListener('input', () => {
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(() => {
            const text = textarea.value.trim();
            if (text) saveSuggestion();
        }, 2000);
    });
}

// ===== PERSISTENCIA =====
async function loadSuggestions() {
    try {
        // Intentar cargar desde localStorage (persistencia local)
        const stored = localStorage.getItem('aura_feature_roadmap');
        if (stored) {
            const data = JSON.parse(stored);
            renderSuggestions(data.suggestions || []);
        } else {
            renderSuggestions([]);
        }

        // Intentar cargar desde archivo JSON
        try {
            const response = await fetch(`../../${ROADMAP_FILE}?t=${Date.now()}`);
            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('aura_feature_roadmap', JSON.stringify(data));
                renderSuggestions(data.suggestions || []);
            }
        } catch (e) {
            // No hay conexión con el backend, usar localStorage
            console.log('Feature Roadmap: Usando almacenamiento local');
        }
    } catch (e) {
        console.warn('Error cargando sugerencias:', e);
    }
}

function renderSuggestions(suggestions) {
    const container = document.getElementById('suggestion-history');
    if (!container) return;

    if (!suggestions || suggestions.length === 0) {
        container.innerHTML = `
            <div style="font-size: 10px; color: rgba(0,255,255,0.3); padding: 8px; text-align: center;">
                Aún no hay sugerencias. ¡Escribe tu primera idea!
            </div>
        `;
        return;
    }

    container.innerHTML = suggestions.slice().reverse().map((s, i) => `
        <div style="
            padding: 8px; margin: 4px 0;
            background: rgba(0,255,255,0.03);
            border-left: 2px solid rgba(0,255,255,0.2);
            border-radius: 0 4px 4px 0;
        ">
            <div style="font-size: 10px; color: rgba(0,255,255,0.3);">
                ${new Date(s.date).toLocaleDateString('es-ES', {
                    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
                })}
            </div>
            <div style="font-size: 11px; color: rgba(255,255,255,0.7); margin-top: 2px;">
                ${s.text}
            </div>
            ${s.status ? `<span style="font-size: 8px; color: #ff6600; background: rgba(255,102,0,0.1); padding: 1px 6px; border-radius: 8px; margin-top: 4px; display: inline-block;">${s.status}</span>` : ''}
        </div>
    `).join('');
}

async function saveSuggestion() {
    const textarea = document.getElementById('feature-suggestion-input');
    const text = textarea?.value?.trim();
    if (!text) return;

    try {
        // Guardar en localStorage
        const stored = localStorage.getItem('aura_feature_roadmap');
        const data = stored ? JSON.parse(stored) : { suggestions: [], created_at: new Date().toISOString() };
        
        data.suggestions = data.suggestions || [];
        data.suggestions.push({
            id: Date.now(),
            text: text,
            date: new Date().toISOString(),
            status: 'pendiente',
            source: 'dashboard'
        });
        data.updated_at = new Date().toISOString();
        
        localStorage.setItem('aura_feature_roadmap', JSON.stringify(data));

        // Intentar persistir en backend
        try {
            await fetch(`../../${ROADMAP_FILE}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        } catch (e) {
            // Solo local es suficiente por ahora
        }

        // Actualizar UI
        renderSuggestions(data.suggestions);
        textarea.value = '';
        
        // Feedback visual
        const btn = document.querySelector('#feature-audit-panel button');
        if (btn) {
            btn.textContent = '✅ Guardado';
            setTimeout(() => { btn.textContent = '💾 Guardar Sugerencia'; }, 2000);
        }

        // Notificar al HUD
        if (window.addHUDLogEntry) {
            window.addHUDLogEntry('💡 Nueva sugerencia guardada en el Roadmap', 'success');
        }

        // Actualizar badge
        updateFeatureBadge();

    } catch (e) {
        console.error('Error guardando sugerencia:', e);
        if (window.addHUDLogEntry) {
            window.addHUDLogEntry('❌ Error guardando sugerencia', 'error');
        }
    }
}

function updateFeatureBadge() {
    try {
        const stored = localStorage.getItem('aura_feature_roadmap');
        if (stored) {
            const data = JSON.parse(stored);
            const count = data.suggestions?.length || 0;
            const btn = document.getElementById('feature-audit-btn');
            if (btn && count > 0) {
                btn.style.borderColor = '#ff6600';
                // Pequeño indicador de notificaciones
            }
        }
    } catch (e) {}
}

// ===== CONTROL DE PANEL =====
function toggleFeaturePanel() {
    const panel = document.getElementById('feature-audit-panel');
    if (panel) {
        closeFeaturePanel();
    } else {
        createFeaturePanel();
    }
}

function closeFeaturePanel() {
    document.getElementById('feature-audit-panel')?.remove();
    document.getElementById('feature-audit-overlay')?.remove();
}

// ===== INICIALIZACIÓN =====
function initFeatureAuditConsole() {
    console.log('🗺️ Inicializando Feature Audit Console...');
    
    // Esperar a que el HUD esté listo
    const checkHUD = setInterval(() => {
        if (document.getElementById('tactical-hud') || document.querySelector('.hud-value')) {
            clearInterval(checkHUD);
            
            // Añadir botón y badge
            addFeatureAuditButton();
            
            // Actualizar badge con conteo
            updateFeatureBadge();
            
            console.log('✅ Feature Audit Console lista');
            console.log(`  • ${getFeatureStats().implemented}/${getFeatureStats().total} funciones implementadas`);
        }
    }, 500);

    // Timeout de seguridad
    setTimeout(() => clearInterval(checkHUD), 10000);
}

// Exportar globalmente
window.initFeatureAuditConsole = initFeatureAuditConsole;
window.toggleFeaturePanel = toggleFeaturePanel;
window.getFeatureStats = getFeatureStats;