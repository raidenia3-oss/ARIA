/**
 * ════════════════════════════════════════════════════════════════════════════════════════════════════
 *   STREAMING_CHAT — Módulo de Chat en Tiempo Real
 *   Interfaz táctica con respuesta háptica y auto-scroll inteligente
 *   AME Project — AURA
 * ════════════════════════════════════════════════════════════════════════════════════════════════════
 */

class StreamingChat {
    constructor() {
        this.container = null;
        this.chatContainer = null;
        this.messagesContainer = null;
        this.messageInput = null;
        this.sendButton = null;
        this.micButton = null;
        this.typingIndicator = null;
        this.streamingIndicator = null;
        this.messageQueue = [];
        this.isStreaming = false;
        this.scrollTimeout = null;
        this.lastScrollPosition = 0;
        this.hapticFeedbackEnabled = true;
        this.markdownRenderer = null;
        this.initMarkdownRenderer();
    }

    init() {
        // Crear contenedor principal
        this.container = document.createElement('div');
        this.container.className = 'streaming-chat-container';

        // Crear contenedor de mensajes
        this.chatContainer = document.createElement('div');
        this.chatContainer.className = 'streaming-chat';

        // Crear contenedor de mensajes
        this.messagesContainer = document.createElement('div');
        this.messagesContainer.className = 'streaming-chat-messages';
        this.messagesContainer.id = 'streaming-chat-messages';

        // Crear barra de entrada
        this.messageInput = document.createElement('textarea');
        this.messageInput.className = 'streaming-chat-input';
        this.messageInput.placeholder = 'Escribe tu mensaje...';
        this.messageInput.autocomplete = 'off';
        this.messageInput.autocorrect = 'off';
        this.messageInput.spellcheck = 'false';

        // Crear botón de enviar
        this.sendButton = document.createElement('button');
        this.sendButton.className = 'streaming-chat-send';
        this.sendButton.innerHTML = 'Enviar';
        this.sendButton.disabled = true;

        // Crear botón de micrófono
        this.micButton = document.createElement('button');
        this.micButton.className = 'mic-button';
        this.micButton.innerHTML = `
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
            </svg>
        `;
        this.micButton.title = 'Grabación de voz';

        // Crear indicador de escritura
        this.typingIndicator = document.createElement('div');
        this.typingIndicator.className = 'streaming-chat-typing-indicator';
        this.typingIndicator.textContent = 'Escribiendo...';

        // Crear indicador de streaming
        this.streamingIndicator = document.createElement('div');
        this.streamingIndicator.className = 'streaming-chat-streaming-indicator';
        this.streamingIndicator.innerHTML = `
            <div class="streaming-dots">
                <div class="dot"></div>
                <div class="dot"></div>
                <div class="dot"></div>
            </div>
            <span>AURA está procesando...</span>
        `;

        // Agregar elementos al contenedor
        this.chatContainer.appendChild(this.messagesContainer);
        this.chatContainer.appendChild(this.typingIndicator);
        this.chatContainer.appendChild(this.streamingIndicator);

        const inputContainer = document.createElement('div');
        inputContainer.className = 'streaming-chat-input-container';
        inputContainer.appendChild(this.messageInput);
        inputContainer.appendChild(this.sendButton);
        inputContainer.appendChild(this.micButton);

        this.container.appendChild(this.chatContainer);
        this.container.appendChild(inputContainer);

        // Agregar al DOM
        document.body.appendChild(this.container);

        // Event listeners
        this.messageInput.addEventListener('input', () => {
            this.sendButton.disabled = !this.messageInput.value.trim();
        });

        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        this.sendButton.addEventListener('click', () => this.sendMessage());
        this.micButton.addEventListener('click', () => this.toggleVoiceInput());

        // Ocultar por defecto
        this.container.style.display = 'none';
    }

    initMarkdownRenderer() {
        // Inicializar renderizador de Markdown
        this.markdownRenderer = {
            render: (text) => {
                if (!text) return text;

                // Procesar bloques de código
                text = this.processCodeBlocks(text);

                // Procesar Markdown básico
                text = text
                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    .replace(/\*(.*?)\*/g, '<em>$1</em>')
                    .replace(/\`(.*?)\`/g, '<code>$1</code>')
                    .replace(/\n/g, '<br>')
                    .replace(/\-\s(.*?)\n/g, '<li>$1</li>')
                    .replace(/\n\s*\n/g, '</ul><br><ul>');

                // Añadir listas
                text = text.replace(/^(\*\s|•\s|•\s|- )/gm, '<li>$1</li>');

                // Añadir listas ordenadas
                text = text.replace(/^(\d+\.\s)/gm, '<li>$1</li>');

                // Convertir a HTML seguro
                const div = document.createElement('div');
                div.innerHTML = text;

                // Procesar listas
                const lists = div.querySelectorAll('ul, ol');
                lists.forEach(list => {
                    const items = list.querySelectorAll('li');
                    items.forEach(item => {
                        item.innerHTML = item.innerHTML.replace(/^(\*\s|•\s|•\s|- )/g, '');
                    });
                });

                return div.innerHTML;
            },

            processCodeBlocks: (text) => {
                // Procesar bloques de código con resaltado de sintaxis
                const codeBlocks = text.match(/```(?:[a-z]+)?\n([\s\S]+?)```/g) || [];

                codeBlocks.forEach(block => {
                    const [, code] = block.match(/```(?:[a-z]+)?\n([\s\S]+?)```/);
                    const language = block.match(/```([a-z]+)/)?.[1] || 'text';

                    // Crear elemento de código con resaltado
                    const codeElement = document.createElement('div');
                    codeElement.className = 'code-block';
                    codeElement.innerHTML = this.highlightCode(code, language);

                    // Reemplazar el bloque de código en el texto
                    text = text.replace(block, codeElement.outerHTML);
                });

                return text;
            },

            highlightCode: (code, language) => {
                // Resaltado básico de sintaxis
                let highlighted = code;

                // Resaltar palabras clave
                if (language === 'javascript' || language === 'js') {
                    highlighted = highlighted
                        .replace(/\b(function|return|if|else|for|while|var|let|const|new|delete|typeof|instanceof|void|this|true|false|null|undefined|break|continue|debugger|try|catch|finally|throw|class|extends|import|from|export|super|static|async|await|yield)\b/g, '<span class="keyword">$1</span>')
                        .replace(/\b(console|log|alert|prompt|confirm)\b/g, '<span class="function">$1</span>');
                } else if (language === 'python') {
                    highlighted = highlighted
                        .replace(/\b(def|class|return|if|else|elif|for|while|try|except|finally|import|from|as|with|yield|lambda|None|True|False|and|or|not|is|in|del|break|continue|pass)\b/g, '<span class="keyword">$1</span>');
                } else if (language === 'bash') {
                    highlighted = highlighted
                        .replace(/\b(if|else|elif|for|while|do|done|case|esac|function|return|break|continue|export|source|cd|ls|grep|awk|sed|cat|echo|export|set|unset)\b/g, '<span class="keyword">$1</span>');
                }

                // Resaltar cadenas
                highlighted = highlighted
                    .replace(/(".*?")/g, '<span class="string">$1</span>')
                    .replace(/('.*?')/g, '<span class="string">$1</span>');

                // Resaltar comentarios
                if (language === 'javascript' || language === 'js') {
                    highlighted = highlighted.replace(/\/\/.*$/gm, '<span class="comment">$&</span>');
                    highlighted = highlighted.replace(/\/\*[\s\S]*?\*\//g, '<span class="comment">$&</span>');
                } else if (language === 'python') {
                    highlighted = highlighted.replace(/#.*$/gm, '<span class="comment">$&</span>');
                } else if (language === 'bash') {
                    highlighted = highlighted.replace(/#.*$/gm, '<span class="comment">$&</span>');
                }

                return highlighted;
            }
        };
    }

    open() {
        this.container.style.display = 'flex';
        this.messageInput.focus();
    }

    close() {
        this.container.style.display = 'none';
    }

    sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        // Vibración háptica al enviar mensaje
        this.triggerHapticFeedback('impact');

        // Mostrar mensaje del usuario
        this.addUserMessage(message);

        // Limpiar input
        this.messageInput.value = '';
        this.sendButton.disabled = true;

        // Simular respuesta de AURA
        this.simulateAuraResponse(message);
    }

    simulateAuraResponse(userMessage) {
        // Mostrar indicador de streaming
        this.typingIndicator.style.display = 'none';
        this.streamingIndicator.style.display = 'block';
        this.isStreaming = true;

        // Vibración háptica al iniciar streaming
        this.triggerHapticFeedback('notification');

        // Simular respuesta de AURA con streaming
        this.streamAuraResponse(userMessage);
    }

    async streamAuraResponse(userMessage) {
        // Simular procesamiento
        await new Promise(resolve => setTimeout(resolve, 800));

        // Mostrar mensaje inicial de AURA
        const auraMessageId = `aura-${Date.now()}`;
        this.addAuraMessage(auraMessageId, 'AURA está procesando tu mensaje...');

        // Simular streaming de respuesta
        const responseParts = [
            `Analizando tu mensaje: "${userMessage}"`,
            `Conectando a los nodos de inteligencia...`,
            `Consultando bases de datos tácticas...`,
            `Generando respuesta con contexto de seguridad...`
        ];

        // Simular respuesta en tiempo real
        for (let i = 0; i < responseParts.length; i++) {
            await new Promise(resolve => setTimeout(resolve, 1200 + Math.random() * 800));
            this.updateAuraMessage(auraMessageId, responseParts[i]);

            // Auto-scroll suave
            this.autoScrollToBottom();
        }

        // Respuesta final
        const finalResponse = this.generateAuraResponse(userMessage);
        await new Promise(resolve => setTimeout(resolve, 1500));
        this.updateAuraMessage(auraMessageId, finalResponse);

        // Ocultar indicador de streaming
        this.streamingIndicator.style.display = 'none';
        this.isStreaming = false;

        // Vibración háptica al finalizar respuesta
        this.triggerHapticFeedback('success');
    }

    generateAuraResponse(userMessage) {
        // Generar respuesta simulada basada en el mensaje del usuario
        const responses = {
            'hola': [
                'Hola. Soy AURA, tu asistente táctico de inteligencia. ¿En qué puedo ayudarte hoy?',
                'Detecté un saludo. ¿Necesitas asistencia con algún módulo específico?'
            ],
            'osint': [
                'Activando módulo de reconocimiento OSINT...',
                'Preparando búsquedas en redes sociales. ¿Qué término deseas analizar?',
                'El módulo OSINT está listo para realizar búsquedas en Twitter, Instagram, Facebook y LinkedIn.'
            ],
            'biometría': [
                'El sistema de autenticación biométrica está activo. Por favor, usa el botón de autenticación en la pantalla de bloqueo.',
                'La autenticación biométrica es obligatoria para acceder a funciones tácticas. ¿Necesitas ayuda con la configuración?'
            ],
            'default': [
                `Analizando tu mensaje: "${userMessage}"`,
                `Conectando a los nodos de inteligencia táctica...`,
                `Generando respuesta con contexto de seguridad y operacional...`,
                `Recomendación: ${this.generateRecommendation(userMessage)}`
            ]
        };

        // Buscar coincidencias en el mensaje
        for (const [keyword, responseSet] of Object.entries(responses)) {
            if (userMessage.toLowerCase().includes(keyword)) {
                return responseSet[Math.floor(Math.random() * responseSet.length)];
            }
        }

        return responses.default[Math.floor(Math.random() * responses.default.length)];
    }

    generateRecommendation(message) {
        const recommendations = [
            'Activa el módulo OSINT para realizar búsquedas en redes sociales.',
            'Verifica el estado de la conexión con el botón de prueba en la esquina inferior derecha.',
            'Usa el botón de grabación de audio para capturar información táctica en tiempo real.',
            'Accede a la configuración de biometría para ajustar el método de autenticación.',
            'Revisa los resultados de las últimas operaciones en el panel de control táctico.'
        ];

        return recommendations[Math.floor(Math.random() * recommendations.length)];
    }

    addUserMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'streaming-chat-message user-message';

        const messageContent = document.createElement('div');
        messageContent.className = 'streaming-chat-message-content';
        messageContent.innerHTML = this.markdownRenderer.render(message);

        const timestamp = document.createElement('div');
        timestamp.className = 'streaming-chat-message-timestamp';
        timestamp.textContent = this.formatTime(new Date());

        messageElement.appendChild(messageContent);
        messageElement.appendChild(timestamp);

        this.messagesContainer.appendChild(messageElement);

        // Auto-scroll suave
        this.autoScrollToBottom();
    }

    addAuraMessage(id, content) {
        const messageElement = document.createElement('div');
        messageElement.className = 'streaming-chat-message aura-message';
        messageElement.id = id;

        const messageContent = document.createElement('div');
        messageContent.className = 'streaming-chat-message-content';
        messageContent.innerHTML = this.markdownRenderer.render(content);

        const timestamp = document.createElement('div');
        timestamp.className = 'streaming-chat-message-timestamp';
        timestamp.textContent = this.formatTime(new Date());

        messageElement.appendChild(messageContent);
        messageElement.appendChild(timestamp);

        this.messagesContainer.appendChild(messageElement);

        // Auto-scroll suave
        this.autoScrollToBottom();
    }

    updateAuraMessage(id, content) {
        const messageElement = document.getElementById(id);
        if (messageElement) {
            const messageContent = messageElement.querySelector('.streaming-chat-message-content');
            if (messageContent) {
                messageContent.innerHTML = this.markdownRenderer.render(content);
            }
        }

        // Auto-scroll suave
        this.autoScrollToBottom();
    }

    autoScrollToBottom() {
        // Limpiar timeout anterior
        if (this.scrollTimeout) {
            clearTimeout(this.scrollTimeout);
        }

        // Guardar posición actual
        this.lastScrollPosition = this.messagesContainer.scrollHeight - this.messagesContainer.clientHeight;

        // Scroll suave a la posición final
        this.scrollTimeout = setTimeout(() => {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight - this.messagesContainer.clientHeight;
        }, 100);
    }

    toggleVoiceInput() {
        // Simular grabación de voz
        this.triggerHapticFeedback('impact');

        // Mostrar indicador de grabación
        const originalHTML = this.micButton.innerHTML;
        this.micButton.innerHTML = `
            <div class="recording-indicator"></div>
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
            </svg>
        `;

        // Simular grabación de 3 segundos
        setTimeout(() => {
            this.micButton.innerHTML = originalHTML;

            // Simular envío del mensaje de voz
            this.sendMessage('Comando de voz: Activar módulo táctico');
        }, 3000);
    }

    triggerHapticFeedback(type) {
        // Simulación de vibración háptica
        if (!this.hapticFeedbackEnabled) return;

        // Vibración de impacto (mensaje enviado)
        if (type === 'impact') {
            this.vibrateDevice(10, 50, 100); // Corta y ligera
        }
        // Vibración de notificación (streaming iniciado)
        else if (type === 'notification') {
            this.vibrateDevice(100, 100, 200); // Más fuerte
        }
        // Vibración de éxito (respuesta completada)
        else if (type === 'success') {
            this.vibrateDevice(50, 100, 150, 50, 100); // Patrón de éxito
        }
    }

    vibrateDevice(...pattern) {
        // Simulación de vibración en navegador
        if (navigator.vibrate) {
            try {
                navigator.vibrate(pattern);
            } catch (e) {
                console.log('Vibración no permitida:', e);
            }
        } else {
            // Simulación visual de vibración
            this.simulateVibration();
        }
    }

    simulateVibration() {
        // Efecto visual de vibración
        const messagesContainer = document.getElementById('streaming-chat-messages');
        if (messagesContainer) {
            messagesContainer.style.transform = 'translateY(2px)';
            setTimeout(() => {
                messagesContainer.style.transform = 'translateY(-2px)';
                setTimeout(() => {
                    messagesContainer.style.transform = 'translateY(0)';
                }, 50);
            }, 50);
        }
    }

    formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    // Método para integrar con el sistema de autenticación
    integrateWithAuth(authToken) {
        this.authToken = authToken;
    }
}

// Exportar la clase para uso global
window.StreamingChat = StreamingChat;
