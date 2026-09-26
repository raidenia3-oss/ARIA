/**
 * tactical_dashboard.js - Dashboard Táctico para AME/AURA
 * Proporciona visualización de nodos en tiempo real, Drag & Drop para asignar módulos,
 * y stream de terminal para monitorear tareas.
 * 
 * Dependencias: Socket.io (cargado vía CDN en dashboard.html)
 */

(function() {
    'use strict';

    // ========== CONFIGURACIÓN ==========
    const WS_URL = 'ws://localhost:3000';
    const MODULES = [
        { type: 'venice',  name: 'Venice OSINT',         icon: '🔍', color: 'blue' },
        { type: 'recon',   name: 'Reconnaissance',       icon: '🔎', color: 'purple' },
        { type: 'exploit', name: 'Exploit',              icon: '⚡', color: 'red' },
        { type: 'scan',    name: 'Network Scan',         icon: '📡', color: 'green' },
        { type: 'forensic',name: 'Forensic Analysis',    icon: '🔬', color: 'orange' },
        { type: 'analyze', name: 'Behavioral Analysis',  icon: '👁️', color: 'indigo' },
        { type: 'monitor', name: 'Network Monitor',      icon: '📊', color: 'teal' },
        { type: 'patch',   name: 'Patch Management',     icon: '🛡️', color: 'pink' },
        { type: 'update',  name: 'Firmware Update',      icon: '🔄', color: 'yellow' }
    ];

    // ========== ESTADO GLOBAL ==========
    const state = {
        socket: null,
        nodes: [],
        activeTask: null,
        terminalOutput: [],
        selectedNode: null,
        connectionStatus: 'connecting',
        lastUpdated: null,
        dragState: null  // { moduleType, startX, startY }
    };

    // ========== ELEMENTOS DEL DOM ==========
    const DOM = {};

    function cacheDOM() {
        DOM.connectionDot = document.getElementById('connectionDot');
        DOM.connectionLabel = document.getElementById('connectionLabel');
        DOM.lastUpdateLabel = document.getElementById('lastUpdateLabel');
        DOM.modulesGrid = document.getElementById('modulesGrid');
        DOM.nodesGrid = document.getElementById('nodesGrid');
        DOM.nodeStats = document.getElementById('nodeStats');
        DOM.taskPanel = document.getElementById('taskPanel');
        DOM.taskModuleName = document.getElementById('taskModuleName');
        DOM.taskNodeName = document.getElementById('taskNodeName');
        DOM.taskStatus = document.getElementById('taskStatus');
        DOM.taskProgressBar = document.getElementById('taskProgressBar');
        DOM.taskProgressText = document.getElementById('taskProgressText');
        DOM.taskRecentOutput = document.getElementById('taskRecentOutput');
        DOM.terminalStream = document.getElementById('terminalStream');
        DOM.cancelTaskBtn = document.getElementById('cancelTaskBtn');
        DOM.dndWrapper = document.getElementById('dnd-wrapper');
        DOM.tacticalDashboard = document.getElementById('tactical-dashboard');
    }

    // ========== UTILIDADES ==========
    function formatTimestamp(iso) {
        if (!iso) return 'N/A';
        try {
            return new Date(iso).toLocaleTimeString();
        } catch(e) {
            return 'N/A';
        }
    }

    function generateId() {
        return 'node-' + Math.random().toString(36).substr(2, 8);
    }

    function showNotification(message, type) {
        // Intentar usar notificaciones del sistema AURA si están disponibles
        if (window.AURA_BackgroundNotifications) {
            window.AURA_BackgroundNotifications.sendNotification(message, type);
        }
    }

    // ========== WEB SOCKET ==========
    function initWebSocket() {
        updateConnectionStatus('connecting');

        try {
            const socket = io(WS_URL, {
                transports: ['websocket'],
                reconnection: true,
                reconnectionAttempts: 10,
                reconnectionDelay: 1000,
                timeout: 5000
            });

            state.socket = socket;

            socket.on('connect', () => {
                console.log('[TacticalDashboard] WebSocket conectado');
                updateConnectionStatus('connected');
                socket.emit('subscribe', 'nodes');
                socket.emit('subscribe', 'tasks');
                socket.emit('get_task_history');
                state.lastUpdated = new Date().toISOString();
                updateLastUpdateLabel();
            });

            socket.on('node_update', (updatedNodes) => {
                state.nodes = updatedNodes;
                state.lastUpdated = new Date().toISOString();
                updateLastUpdateLabel();
                renderNodes();
                updateNodeStats();
            });

            socket.on('task_assigned', (task) => {
                state.activeTask = task;
                state.terminalOutput = [];
                state.lastUpdated = new Date().toISOString();
                renderTaskPanel(task);
                showNotification(`Tarea asignada a ${task.nodeId} (${task.module})`, 'info');
            });

            socket.on('task_output', (data) => {
                if (data.taskId === state.activeTask?.id) {
                    state.terminalOutput.push(data.output);
                    renderTerminal();
                }
            });

            socket.on('task_update', (task) => {
                if (task.id === state.activeTask?.id) {
                    state.activeTask = task;
                    state.lastUpdated = new Date().toISOString();
                    renderTaskPanel(task);

                    if (task.status === 'completed') {
                        const duration = task.completed_at && task.timestamp ?
                            ((new Date(task.completed_at) - new Date(task.timestamp)) / 1000) : 0;
                        const mins = Math.floor(duration / 60);
                        const secs = Math.floor(duration % 60);
                        showNotification(`Tarea completada en node ${task.nodeId} (${mins}m ${secs}s)`, 'success');
                    } else if (task.status === 'failed') {
                        showNotification(`Tarea falló en node ${task.nodeId}`, 'error');
                    } else if (task.status === 'cancelled') {
                        showNotification(`Tarea cancelada en node ${task.nodeId}`, 'warning');
                    }
                }
            });

            socket.on('task_history', (history) => {
                console.log(`[TacticalDashboard] Historial recibido: ${history.length} tareas`);
            });

            socket.on('disconnect', (reason) => {
                console.log('[TacticalDashboard] WebSocket desconectado:', reason);
                updateConnectionStatus('disconnected');
                showNotification('Desconectado del servidor WebSocket', 'warning');
            });

            socket.on('connect_error', (err) => {
                console.error('[TacticalDashboard] Error de conexión:', err.message);
                updateConnectionStatus('error');
                showNotification('Error de conexión WebSocket: ' + err.message, 'error');
            });

            socket.on('reconnect', () => {
                console.log('[TacticalDashboard] Reconectado');
                updateConnectionStatus('connected');
                socket.emit('subscribe', 'nodes');
                socket.emit('subscribe', 'tasks');
                showNotification('Reconectado al servidor WebSocket', 'info');
            });

        } catch (err) {
            console.error('[TacticalDashboard] Error init WebSocket:', err);
            updateConnectionStatus('error');
        }
    }

    // ========== CONEXIÓN ==========
    function updateConnectionStatus(status) {
        state.connectionStatus = status;
        if (DOM.connectionDot) {
            DOM.connectionDot.className = 'w-3 h-3 rounded-full';
            switch(status) {
                case 'connected': DOM.connectionDot.classList.add('bg-green-500'); break;
                case 'disconnected': DOM.connectionDot.classList.add('bg-red-500'); break;
                case 'error': DOM.connectionDot.classList.add('bg-red-500'); break;
                default: DOM.connectionDot.classList.add('bg-yellow-500');
            }
        }
        if (DOM.connectionLabel) {
            DOM.connectionLabel.textContent = status;
            DOM.connectionLabel.className = 'text-sm';
            switch(status) {
                case 'connected': DOM.connectionLabel.classList.add('text-green-600'); break;
                case 'disconnected': DOM.connectionLabel.classList.add('text-red-600'); break;
                case 'error': DOM.connectionLabel.classList.add('text-red-600'); break;
                default: DOM.connectionLabel.classList.add('text-yellow-600');
            }
        }
    }

    function updateLastUpdateLabel() {
        if (DOM.lastUpdateLabel && state.lastUpdated) {
            DOM.lastUpdateLabel.textContent = ' | Última actualización: ' + formatTimestamp(state.lastUpdated);
        }
    }

    // ========== RENDER MÓDULOS ==========
    function renderModules() {
        if (!DOM.modulesGrid) return;
        DOM.modulesGrid.innerHTML = '';

        MODULES.forEach(mod => {
            const icon = document.createElement('div');
            icon.className = `module-icon module-${mod.type} rounded-lg shadow-lg flex flex-col items-center justify-center cursor-move transition-all duration-200 hover:scale-105`;
            icon.draggable = true;
            icon.dataset.moduleType = mod.type;

            // Estilo según color
            const colors = {
                blue: 'bg-blue-100 text-blue-600',
                purple: 'bg-purple-100 text-purple-600',
                red: 'bg-red-100 text-red-600',
                green: 'bg-green-100 text-green-600',
                orange: 'bg-orange-100 text-orange-600',
                indigo: 'bg-indigo-100 text-indigo-600',
                teal: 'bg-teal-100 text-teal-600',
                pink: 'bg-pink-100 text-pink-600',
                yellow: 'bg-yellow-100 text-yellow-600'
            };
            icon.style.backgroundColor = mod.color ? '' : ''; // Will be overridden by class

            icon.innerHTML = `
                <div class="icon text-2xl mb-1 ${colors[mod.color] || 'text-gray-600'}">${mod.icon}</div>
                <div class="label text-xs font-medium text-gray-700">${mod.name}</div>
            `;

            // Eventos Drag & Drop
            icon.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', JSON.stringify({ type: mod.type }));
                icon.classList.add('opacity-50');
                state.dragState = { moduleType: mod.type };
                document.querySelectorAll('.node-card').forEach(card => {
                    card.classList.add('drag-active');
                });
            });

            icon.addEventListener('dragend', () => {
                icon.classList.remove('opacity-50');
                state.dragState = null;
                document.querySelectorAll('.node-card').forEach(card => {
                    card.classList.remove('drag-active');
                    card.classList.remove('drag-over');
                });
            });

            DOM.modulesGrid.appendChild(icon);
        });
    }

    // ========== RENDER NODOS ==========
    function renderNodes() {
        if (!DOM.nodesGrid) return;

        // Si no hay nodos, mostrar mensaje y usar datos simulados
        let nodes = state.nodes;
        if (!nodes || nodes.length === 0) {
            nodes = generateSampleNodes();
            state.nodes = nodes;
        }

        DOM.nodesGrid.innerHTML = '';

        nodes.forEach(node => {
            const card = document.createElement('div');
            card.className = `node-card bg-white rounded-lg shadow-lg border-2 border-transparent transition-all duration-200 hover:shadow-xl hover:-translate-y-1`;
            card.dataset.nodeId = node.id;

            const statusColor = {
                'available': 'bg-green-500',
                'busy': 'bg-yellow-500',
                'offline': 'bg-red-500'
            }[node.status] || 'bg-gray-500';

            card.innerHTML = `
                <div class="relative h-full p-4">
                    <div class="absolute top-3 right-3 w-3 h-3 rounded-full ${statusColor}"></div>
                    <div class="h-full flex flex-col">
                        <div class="flex-grow flex flex-col items-center justify-center">
                            <div class="node-id text-2xl font-bold text-gray-800">${node.id.substring(0, 6)}</div>
                            <div class="node-type text-xs text-gray-500 mt-1">${node.type || 'mobile'}</div>
                        </div>
                        <div class="text-sm font-bold text-gray-800 mt-2">${node.name || 'Nodo Desconocido'}</div>
                        <div class="text-xs text-gray-500 mt-1">${node.location || 'Ubicación Desconocida'}</div>
                        ${node.status === 'busy' && node.current_task ? `
                            <div class="text-xs text-gray-500 mt-1">
                                Task: ${node.current_task.substring(0, 8)}...
                            </div>
                        ` : ''}
                        <div class="flex justify-between text-xs text-gray-500 mt-3">
                            <div>
                                <div>🔋 ${node.battery !== undefined ? node.battery + '%' : 'N/A'}</div>
                            </div>
                            <div>
                                <div>📶 ${node.signal !== undefined ? node.signal : 'N/A'}</div>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Eventos Drag Over (soltar)
            card.addEventListener('dragover', (e) => {
                e.preventDefault();
                if (node.status === 'available') {
                    card.classList.add('drag-over', 'border-blue-500', 'ring-2', 'ring-blue-200');
                }
            });

            card.addEventListener('dragleave', () => {
                card.classList.remove('drag-over', 'border-blue-500', 'ring-2', 'ring-blue-200');
            });

            card.addEventListener('drop', (e) => {
                e.preventDefault();
                card.classList.remove('drag-over', 'border-blue-500', 'ring-2', 'ring-blue-200');

                if (node.status !== 'available') {
                    showNotification(`Nodo ${node.name} no disponible (${node.status})`, 'warning');
                    return;
                }

                try {
                    const data = JSON.parse(e.dataTransfer.getData('text/plain'));
                    const moduleType = data.type;

                    if (!moduleType) {
                        showNotification('Error: módulo no especificado', 'error');
                        return;
                    }

                    handleModuleDrop(node.id, moduleType);
                } catch(err) {
                    console.error('[TacticalDashboard] Error parsing drop data:', err);
                    showNotification('Error al procesar el módulo arrastrado', 'error');
                }
            });

            // Click para seleccionar nodo
            card.addEventListener('click', () => {
                state.selectedNode = node;
                document.querySelectorAll('.node-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected', 'ring-2', 'ring-blue-300');
            });

            DOM.nodesGrid.appendChild(card);
        });

        updateNodeStats();
    }

    function generateSampleNodes() {
        const locations = ['Sector A', 'Sector B', 'Sector C', 'Sector D', 'Sector E'];
        return Array.from({ length: 8 }, (_, i) => ({
            id: generateId(),
            name: `Nodo ${i + 1}`,
            type: 'mobile',
            status: i % 4 === 0 ? 'busy' : (i % 7 === 0 ? 'offline' : 'available'),
            location: locations[i % locations.length],
            battery: 70 + Math.floor(Math.random() * 30),
            signal: 60 + Math.floor(Math.random() * 40),
            current_task: i % 4 === 0 ? generateId() : null,
            last_seen: new Date().toISOString()
        }));
    }

    function updateNodeStats() {
        if (!DOM.nodeStats) return;
        const nodes = state.nodes;
        if (!nodes || nodes.length === 0) return;

        const available = nodes.filter(n => n.status === 'available').length;
        const busy = nodes.filter(n => n.status === 'busy').length;
        const offline = nodes.filter(n => n.status === 'offline').length;
        DOM.nodeStats.textContent = `${available} disponibles | ${busy} ocupados | ${offline} offline | ${nodes.length} total`;
    }

    // ========== MANEJAR ASIGNACIÓN DE TAREA ==========
    function handleModuleDrop(nodeId, moduleType) {
        const node = state.nodes.find(n => n.id === nodeId);
        if (!node) {
            showNotification(`Nodo no encontrado: ${nodeId}`, 'error');
            return;
        }

        if (node.status !== 'available') {
            showNotification(`Nodo ${node.name} no disponible`, 'warning');
            return;
        }

        const taskData = {
            nodeId: nodeId,
            module: moduleType,
            parameters: {
                target: moduleType === 'venice' ? 'example.com' : '192.168.1.0/24',
                depth: moduleType === 'venice' ? 2 : undefined
            },
            timestamp: new Date().toISOString()
        };

        if (state.socket && state.socket.connected) {
            state.socket.emit('assign_task', taskData);
        } else {
            // Fallback: simular asignación local
            simulateLocalTask(nodeId, moduleType);
        }
    }

    function simulateLocalTask(nodeId, moduleType) {
        const node = state.nodes.find(n => n.id === nodeId);
        if (!node) return;

        node.status = 'busy';
        node.current_task = generateId();
        renderNodes();

        const task = {
            id: generateId(),
            nodeId: nodeId,
            module: moduleType,
            timestamp: new Date().toISOString(),
            status: 'assigned',
            progress: 0,
            output: [],
            started_at: null,
            completed_at: null,
            success: null
        };

        state.activeTask = task;
        state.terminalOutput = [];
        renderTaskPanel(task);
        showNotification(`Tarea ${moduleType} asignada a ${node.name}`, 'info');

        // Simular progreso
        let progress = 0;
        const interval = setInterval(() => {
            progress += 10;

            const output = `[${new Date().toLocaleTimeString()}] ${moduleType.toUpperCase()} - Progress: ${progress}%`;
            task.output.push(output);
            state.terminalOutput.push(output);

            task.progress = progress;
            task.status = progress < 100 ? 'running' : 'completed';
            if (progress >= 100) {
                task.completed_at = new Date().toISOString();
                task.success = true;
                clearInterval(interval);
                node.status = 'available';
                renderNodes();
                showNotification(`Tarea ${moduleType} completada en ${node.name}`, 'success');
            }

            renderTaskPanel(task);
            renderTerminal();
        }, 1000);
    }

    // ========== RENDER PANEL DE TAREA ==========
    function renderTaskPanel(task) {
        if (!DOM.taskPanel) return;
        DOM.taskPanel.style.display = 'block';

        if (DOM.taskModuleName) DOM.taskModuleName.textContent = `Task: ${task.module || 'Unknown'}`;
        if (DOM.taskNodeName) DOM.taskNodeName.textContent = task.nodeId || 'N/A';
        if (DOM.taskProgressBar) DOM.taskProgressBar.style.width = `${task.progress || 0}%`;
        if (DOM.taskProgressText) DOM.taskProgressText.textContent = `${task.progress || 0}%`;

        if (DOM.taskStatus) {
            const statusColors = {
                'completed': 'text-green-600',
                'failed': 'text-red-600',
                'cancelled': 'text-gray-600',
                'running': 'text-yellow-600',
                'assigned': 'text-blue-600'
            };
            DOM.taskStatus.textContent = task.status;
            DOM.taskStatus.className = `task-status font-semibold ${statusColors[task.status] || 'text-gray-600'}`;
        }

        // Mostrar/ocultar botón de cancelar
        if (DOM.cancelTaskBtn) {
            DOM.cancelTaskBtn.style.display = (task.status === 'running' || task.status === 'assigned') ? 'block' : 'none';
        }

        // Renderizar salida reciente
        if (DOM.taskRecentOutput && task.output) {
            DOM.taskRecentOutput.innerHTML = task.output.slice(-3).map(line => {
                const isError = line.includes('[ERROR]') || line.includes('[CANCELLED]');
                const isComplete = line.includes('completed');
                return `<div class="${isError ? 'text-red-600 font-bold' : ''} ${isComplete ? 'text-green-600' : ''} mb-1">${line.split('|')[0].trim()}</div>`;
            }).join('');
        }
    }

    function renderTerminal() {
        if (!DOM.terminalStream) return;
        DOM.terminalStream.innerHTML = state.terminalOutput.map(line => {
            return `<div class="text-xs leading-relaxed">${escapeHtml(line)}</div>`;
        }).join('');

        // Scroll al final
        DOM.terminalStream.scrollTop = DOM.terminalStream.scrollHeight;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ========== CANCELAR TAREA ==========
    function cancelTask() {
        const task = state.activeTask;
        if (!task) return;

        if (!confirm('¿Estás seguro de querer cancelar esta tarea?')) return;

        if (state.socket && state.socket.connected) {
            state.socket.emit('cancel_task', {
                taskId: task.id,
                reason: 'Cancelada por el usuario desde Dashboard Táctico'
            });
        } else {
            // Simular cancelación local
            task.status = 'cancelled';
            task.progress = 0;
            task.completed_at = new Date().toISOString();
            task.success = false;
            task.reason = 'Cancelada por el usuario';

            const node = state.nodes.find(n => n.id === task.nodeId);
            if (node) {
                node.status = 'available';
                renderNodes();
            }

            showNotification(`Tarea cancelada en ${task.nodeId}`, 'warning');
            renderTaskPanel(task);
        }
    }

    // ========== INICIALIZACIÓN ==========
    function init() {
        cacheDOM();
        renderModules();
        renderNodes();
        initWebSocket();

        // Event listener para botón de cancelar
        if (DOM.cancelTaskBtn) {
            DOM.cancelTaskBtn.addEventListener('click', cancelTask);
        }

        console.log('[TacticalDashboard] Inicializado correctamente');
    }

    // Iniciar cuando el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // ========== EXPOSICIÓN DE API ==========
    window.TacticalDashboard = {
        getState: () => state,
        refreshNodes: renderNodes,
        refreshModules: renderModules,
        assignModule: handleModuleDrop,
        cancelTask: cancelTask,
        getNodes: () => state.nodes,
        getActiveTask: () => state.activeTask,
        getConnectionStatus: () => state.connectionStatus
    };

})();