/**
 * Módulo para manejar el streaming de respuestas del modelo LLM usando WebSockets.
 * Incluye un componente de chat que renderiza el texto en tiempo real y soporta TTS.
 */

class StreamingChat {
    constructor() {
        this.socket = null;
        this.chatContainer = null;
        this.messageInput = null;
        this.modelSelect = null;
        this.ttsCheckbox = null;
        this.streamingActive = false;
        this.token = localStorage.getItem('aura_jwt_token');
        this.audioContext = null;
        this.audioSource = null;
        this.chatHistoryManager = new ChatHistoryManager();
    }

    /**
     * Inicializa el componente de chat.
     */
    init() {
        this.chatContainer = document.createElement('div');
        this.chatContainer.className = 'chat-container';

        this.messageInput = document.createElement('input');
        this.messageInput.type = 'text';
        this.messageInput.placeholder = 'Escribe tu mensaje...';
        this.messageInput.className = 'chat-input';

        this.modelSelect = document.createElement('select');
        this.modelSelect.className = 'model-select';
        const defaultOption = document.createElement('option');
        defaultOption.value = 'dolphin-llama3';
        defaultOption.textContent = 'dolphin-llama3';
        this.modelSelect.appendChild(defaultOption);

        this.ttsCheckbox = document.createElement('input');
        this.ttsCheckbox.type = 'checkbox';
        this.ttsCheckbox.id = 'tts-checkbox';
        const ttsLabel = document.createElement('label');
        ttsLabel.htmlFor = 'tts-checkbox';
        ttsLabel.textContent = 'TTS';

        const sendButton = document.createElement('button');
        sendButton.textContent = 'Enviar';
        sendButton.className = 'send-button';
        sendButton.addEventListener('click', () => this.sendMessage());

        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });

        const chatHeader = document.createElement('div');
        chatHeader.className = 'chat-header';
        chatHeader.appendChild(this.messageInput);
        chatHeader.appendChild(this.modelSelect);
        chatHeader.appendChild(this.ttsCheckbox);
        chatHeader.appendChild(ttsLabel);
        chatHeader.appendChild(sendButton);

        this.chatContainer.appendChild(chatHeader);

        document.body.appendChild(this.chatContainer);

        // Inicializar Web Audio API para TTS
        this.initAudioContext();

        // Inicializar el historial de chats
        this.chatHistoryManager.initSidebar();
    }

    /**
     * Inicializa el contexto de audio para reproducir TTS.
     */
    initAudioContext() {
        try {
            window.AudioContext = window.AudioContext || window.webkitAudioContext;
            this.audioContext = new AudioContext();
        } catch (e) {
            console.error("Error al inicializar AudioContext:", e);
        }
    }

    /**
     * Conecta al servidor WebSocket.
     */
    connectWebSocket() {
        if (this.socket) {
            this.socket.close();
        }

        const wsUrl = 'ws://localhost:8765';
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
            console.log('Conectado al servidor WebSocket');
        };

        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.error) {
                this.appendMessage(`Error: ${data.error}`, 'error');
            } else if (data.response) {
                this.appendMessage(data.response, 'response');
            } else if (data.tts) {
                this.handleTTSAudio(data.tts);
            } else if (typeof data === 'string') {
                this.appendStreamingText(data);
            }
        };

        this.socket.onclose = () => {
            console.log('Desconectado del servidor WebSocket');
            this.streamingActive = false;
        };

        this.socket.onerror = (error) => {
            console.error('Error en WebSocket:', error);
            this.appendMessage('Error de conexión con el servidor.', 'error');
        };
    }

    /**
     * Envía un mensaje al servidor WebSocket.
     */
    async sendMessage() {
        const prompt = this.messageInput.value.trim();
        if (!prompt || this.streamingActive) return;

        this.messageInput.value = '';
        const userMessageElement = this.appendMessage(prompt, 'user');

        // Guardar mensaje del usuario en la base de datos
        if (this.chatHistoryManager.currentChatId) {
            await this.chatHistoryManager.saveMessage(
                this.chatHistoryManager.currentChatId,
                'user',
                prompt
            );
        }

        const messageData = {
            token: this.token,
            prompt: prompt,
            model: this.modelSelect.value,
            stream: true,
            tts: this.ttsCheckbox.checked,
            conversation_id: this.chatHistoryManager.currentChatId
        };

        this.socket.send(JSON.stringify(messageData));
        this.streamingActive = true;
    }

    /**
     * Añade un mensaje al chat.
     */
    appendMessage(message, type) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${type}`;

        const contentElement = document.createElement('div');
        contentElement.className = 'message-content';
        contentElement.textContent = message;

        messageElement.appendChild(contentElement);
        this.chatContainer.appendChild(messageElement);
        this.chatContainer.scrollTop = this.chatContainer.scrollHeight;

        return messageElement;
    }

    /**
     * Añade texto en tiempo real al chat.
     */
    appendStreamingText(text) {
        const lastMessage = this.chatContainer.lastElementChild;
        if (lastMessage && lastMessage.classList.contains('response')) {
            const contentElement = lastMessage.querySelector('.message-content');
            contentElement.textContent += text;
        } else {
            this.appendMessage(text, 'response');
        }
    }

    /**
     * Maneja el audio TTS recibido del servidor.
     */
    handleTTSAudio(base64Audio) {
        if (!this.audioContext) {
            console.error("AudioContext no está inicializado");
            return;
        }

        try {
            const audioBlob = this.base64ToBlob(base64Audio, 'audio/wav');
            this.audioContext.decodeAudioData(audioBlob)
                .then((audioBuffer) => {
                    this.playAudioBuffer(audioBuffer);
                })
                .catch((error) => {
                    console.error("Error al decodificar audio:", error);
                });
        } catch (error) {
            console.error("Error al manejar audio TTS:", error);
        }
    }

    /**
     * Convierte una cadena base64 a un Blob.
     */
    base64ToBlob(base64Data, contentType) {
        const byteCharacters = atob(base64Data);
        const byteArrays = [];
        for (let i = 0; i < byteCharacters.length; i++) {
            byteArrays.push(byteCharacters.charCodeAt(i));
        }
        const byteArray = new Uint8Array(byteArrays);
        return new Blob([byteArray], { type: contentType });
    }

    /**
     * Reproduce un buffer de audio.
     */
    playAudioBuffer(audioBuffer) {
        if (!this.audioContext) return;

        if (this.audioSource) {
            this.audioSource.stop();
        }

        this.audioSource = this.audioContext.createBufferSource();
        this.audioSource.buffer = audioBuffer;
        this.audioSource.connect(this.audioContext.destination);
        this.audioSource.start();
    }
}

// Inicializar el chat al cargar la página
document.addEventListener('DOMContentLoaded', () => {
    const chat = new StreamingChat();
    chat.init();
    chat.connectWebSocket();
});