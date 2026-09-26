/**
 * file_handler.js — Interceptor de archivos compartidos vía Android Share Target
 * 
 * Escucha el bridge `window.onFileReceived` expuesto por ShareTargetHandler.java
 * y envía automáticamente el contenido al Cortex (Shadow-Core vía Cloudflare Tunnel).
 * 
 * Soporta: PDF, TXT, JPG, PNG
 * 
 * Modos de envío:
 *   - PDF   → Base64 → endpoint /api/mobile/share/analyze (RAG)
 *   - TXT   → Texto  → endpoint /api/mobile/share/analyze (text analysis)
 *   - Image → Base64 → endpoint /api/mobile/share/analyze (Vision)
 */

(function () {
    'use strict';

    const LOG_TAG = '[AURA-FileHandler]';

    // ─── Config ───────────────────────────────────────────────────────────
    // Se lee del endpoint del servidor (ajustar según despliegue)
    const SHARE_API = '/api/mobile/share/analyze';
    const QUEUE_KEY = 'aura_share_queue_v1';

    // ─── Cola offline ─────────────────────────────────────────────────────
    function readQueue() {
        try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]'); }
        catch (e) { return []; }
    }

    function writeQueue(q) {
        localStorage.setItem(QUEUE_KEY, JSON.stringify(q));
        updateQueueUI();
    }

    function enqueue(item) {
        const q = readQueue();
        q.push(item);
        writeQueue(q);
        console.log(LOG_TAG, '📦 File encolado offline:', item.fileName);
    }

    function dequeue() {
        const q = readQueue();
        if (!q.length) return null;
        const item = q.shift();
        writeQueue(q);
        return item;
    }

    function clearQueue() {
        localStorage.removeItem(QUEUE_KEY);
        updateQueueUI();
    }

    function updateQueueUI() {
        const q = readQueue();
        const indicator = document.getElementById('shareQueueIndicator');
        const count = document.getElementById('shareQueueCount');
        if (indicator && count) {
            count.textContent = q.length;
            indicator.style.display = q.length ? 'flex' : 'none';
        }
    }

    // ─── Detección de tipo de archivo ─────────────────────────────────────
    function isImageMime(mimeType) {
        return mimeType && (mimeType === 'image/jpeg' || mimeType === 'image/png' || mimeType === 'image/jpg');
    }

    function isPDFMime(mimeType) {
        return mimeType && mimeType === 'application/pdf';
    }

    function isTextMime(mimeType) {
        return mimeType && (mimeType === 'text/plain' || mimeType === 'text/html' || mimeType === 'text/markdown');
    }

    // ─── Payload builder ──────────────────────────────────────────────────
    function buildPayload(content, fileName, mimeType) {
        const basePayload = {
            fileName: fileName,
            mimeType: mimeType,
            timestamp: Date.now(),
            source: 'android_share_target',
            device: navigator.userAgent || 'unknown'
        };

        if (isImageMime(mimeType)) {
            // Imagen → base64 con data URI prefix
            return Object.assign({}, basePayload, {
                type: 'image',
                content: `data:${mimeType};base64,${content}`,
                analysis_mode: 'vision'
            });
        }

        if (isPDFMime(mimeType)) {
            // PDF → base64 puro
            return Object.assign({}, basePayload, {
                type: 'pdf',
                content: content, // ya es base64 desde Java
                analysis_mode: 'rag'
            });
        }

        if (isTextMime(mimeType)) {
            // Texto plano
            return Object.assign({}, basePayload, {
                type: 'text',
                content: content,
                analysis_mode: 'text'
            });
        }

        // Fallback: tipo desconocido, enviar como raw text si se puede
        return Object.assign({}, basePayload, {
            type: 'unknown',
            content: content,
            analysis_mode: 'text'
        });
    }

    // ─── Envío al Cortex ──────────────────────────────────────────────────
    async function sendToCortex(payload) {
        console.log(LOG_TAG, '📤 Enviando al Cortex:', payload.fileName, `(${payload.type})`);

        try {
            const resp = await fetch(SHARE_API, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                credentials: 'same-origin'
            });

            if (!resp.ok) {
                throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
            }

            const result = await resp.json();
            console.log(LOG_TAG, '✅ Respuesta del Cortex:', result);

            // Disparar evento para que otros módulos reaccionen
            window.dispatchEvent(new CustomEvent('aura:share:success', {
                detail: { payload, response: result }
            }));

            // Mostrar notificación
            showNotification('✅ Archivo analizado', result.summary || result.message || 'Resumen recibido');

            return result;
        } catch (err) {
            console.error(LOG_TAG, '❌ Error enviando al Cortex:', err);

            // Encolar para reintento offline
            enqueue(payload);

            // Disparar evento de error
            window.dispatchEvent(new CustomEvent('aura:share:offline', {
                detail: { payload, error: err.message }
            }));

            showNotification('📦 Sin conexión', 'Archivo guardado para envío posterior');
            return null;
        }
    }

    // ─── Flush de cola offline ────────────────────────────────────────────
    async function flushShareQueue() {
        const q = readQueue();
        if (!q.length) return;

        console.log(LOG_TAG, `🔄 Flushing ${q.length} archivo(s) de la cola offline...`);

        let successCount = 0;
        let failCount = 0;

        while (readQueue().length > 0) {
            const item = dequeue();
            if (!item) break;

            try {
                const resp = await fetch(SHARE_API, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(item),
                    credentials: 'same-origin'
                });

                if (resp.ok) {
                    successCount++;
                    console.log(LOG_TAG, '✅ Offline flush OK:', item.fileName);
                } else {
                    failCount++;
                    // Re-encolar si sigue fallando
                    enqueue(item);
                    break; // Parar para no saturar
                }
            } catch (e) {
                failCount++;
                enqueue(item);
                break;
            }
        }

        if (successCount > 0) {
            showNotification(`🔄 ${successCount} archivo(s) sincronizado(s)`, '');
        }

        if (failCount === 0) {
            const lastAction = document.getElementById('lastAction');
            if (lastAction) lastAction.textContent = 'Cola de archivos sincronizada';
        }

        updateQueueUI();
    }

    // ─── Notificaciones en UI ─────────────────────────────────────────────
    function showNotification(title, body) {
        // Intentar usar Notification API si está disponible
        if ('Notification' in window && Notification.permission === 'granted') {
            try {
                new Notification(title, { body, icon: '/favicon.ico' });
                return;
            } catch (e) { /* fallback */ }
        }

        // Fallback: toast en DOM
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed; bottom: 24px; right: 24px; z-index: 9999;
            background: #1a1a2e; color: #eee; padding: 12px 20px;
            border-radius: 12px; border: 1px solid #333;
            font-size: 14px; max-width: 320px; box-shadow: 0 4px 24px rgba(0,0,0,0.4);
            animation: slideIn 0.3s ease;
        `;
        toast.innerHTML = `<strong>${title}</strong><br><small>${body || ''}</small>`;
        document.body.appendChild(toast);
        setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.3s'; setTimeout(() => toast.remove(), 300); }, 4000);
    }

    // ─── Callback principal invocado desde Android ShareTargetHandler ─────
    window.onFileReceived = function (content, fileName, mimeType) {
        console.log(LOG_TAG, `📩 Archivo recibido: ${fileName} (${mimeType})`);

        // Mostrar indicador en UI
        const statusEl = document.getElementById('shareStatus');
        if (statusEl) {
            statusEl.textContent = `Procesando: ${fileName}`;
            statusEl.style.display = 'block';
        }

        // Construir payload y enviar
        const payload = buildPayload(content, fileName, mimeType);

        sendToCortex(payload).then((result) => {
            if (statusEl) {
                if (result) {
                    statusEl.textContent = `✅ ${fileName} analizado`;
                } else {
                    statusEl.textContent = `📦 ${fileName} encolado (offline)`;
                }
                setTimeout(() => { statusEl.style.display = 'none'; }, 5000);
            }
        });
    };

    // ─── Inicialización ───────────────────────────────────────────────────
    function init() {
        console.log(LOG_TAG, '🚀 File Handler inicializado');

        // Actualizar UI de cola
        updateQueueUI();

        // Flush automático si hay conexión
        if (navigator.onLine) {
            setTimeout(flushShareQueue, 1000);
        }

        // Escuchar cambios de conectividad
        window.addEventListener('online', () => {
            console.log(LOG_TAG, '🌐 Conexión restaurada — flusheando cola');
            setTimeout(flushShareQueue, 500);
        });

        // Solicitar permiso de notificaciones
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission().catch(() => {});
        }

        // Exponer API pública
        window.AURA_FileHandler = {
            sendToCortex,
            flushQueue: flushShareQueue,
            queueLength: () => readQueue().length,
            getQueue: readQueue
        };

        console.log(LOG_TAG, '✅ API expuesta en window.AURA_FileHandler');
    }

    // Ejecutar cuando el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
