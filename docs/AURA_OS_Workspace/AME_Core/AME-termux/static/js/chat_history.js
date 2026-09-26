/**
 * Módulo para manejar el historial de conversaciones.
 */

class ChatHistoryManager {
    constructor() {
        this.token = localStorage.getItem('aura_jwt_token');
        this.currentChatId = null;
        this.chatListContainer = null;
        this.chatSidebar = null;
        this.chatList = [];
    }

    /**
     * Inicializa el menú lateral para mostrar el historial de chats.
     */
    initSidebar() {
        // Crear el contenedor del sidebar
        this.chatSidebar = document.createElement('div');
        this.chatSidebar.className = 'chat-sidebar';

        // Crear el título del sidebar
        const sidebarTitle = document.createElement('h3');
        sidebarTitle.textContent = 'Historial de Chats';
        sidebarTitle.className = 'sidebar-title';

        // Crear el contenedor de la lista de chats
        this.chatListContainer = document.createElement('div');
        this.chatListContainer.className = 'chat-list-container';

        // Crear el botón para nuevo chat
        const newChatButton = document.createElement('button');
        newChatButton.textContent = 'Nuevo Chat';
        newChatButton.className = 'new-chat-button';
        newChatButton.addEventListener('click', () => this.createNewChat());

        // Añadir elementos al sidebar
        this.chatSidebar.appendChild(sidebarTitle);
        this.chatSidebar.appendChild(this.chatListContainer);
        this.chatSidebar.appendChild(newChatButton);

        // Añadir el sidebar al body
        document.body.appendChild(this.chatSidebar);

        // Cargar la lista de chats
        this.loadChatList();
    }

    /**
     * Carga la lista de chats desde el servidor.
     */
    async loadChatList() {
        try {
            const response = await fetch('/chats', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.token}`
                }
            });

            if (!response.ok) {
                throw new Error('Error al cargar la lista de chats');
            }

            const data = await response.json();
            this.chatList = data.chats;

            // Limpiar el contenedor actual
            this.chatListContainer.innerHTML = '';

            // Crear elementos para cada chat
            this.chatList.forEach(chat => {
                const chatItem = document.createElement('div');
                chatItem.className = `chat-item ${this.currentChatId === chat.id ? 'active' : ''}`;
                chatItem.textContent = chat.title;
                chatItem.dataset.chatId = chat.id;

                chatItem.addEventListener('click', () => this.loadChatMessages(chat.id));

                this.chatListContainer.appendChild(chatItem);
            });
        } catch (error) {
            console.error('Error al cargar chats:', error);
        }
    }

    /**
     * Crea un nuevo chat.
     */
    async createNewChat() {
        try {
            const title = prompt('Ingrese el título del nuevo chat:') || 'Nueva Conversación';

            const response = await fetch('/chats', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.token}`
                },
                body: JSON.stringify({ title: title })
            });

            if (!response.ok) {
                throw new Error('Error al crear el chat');
            }

            const data = await response.json();
            this.currentChatId = data.id;
            this.loadChatList();
            this.loadChatMessages(data.id);
        } catch (error) {
            console.error('Error al crear chat:', error);
        }
    }

    /**
     * Carga los mensajes de un chat específico.
     */
    async loadChatMessages(chatId) {
        this.currentChatId = chatId;

        try {
            const response = await fetch(`/chats/${chatId}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.token}`
                }
            });

            if (!response.ok) {
                throw new Error('Error al cargar los mensajes del chat');
            }

            const data = await response.json();
            const messages = data.messages;

            // Limpiar el chat actual
            const chatContainer = document.querySelector('.chat-container');
            if (chatContainer) {
                const messageElements = chatContainer.querySelectorAll('.message');
                messageElements.forEach(el => {
                    if (!el.classList.contains('user')) {
                        el.remove();
                    }
                });
            }

            // Añadir mensajes al chat
            messages.forEach(message => {
                const messageElement = document.createElement('div');
                messageElement.className = `message ${message.role}`;

                const contentElement = document.createElement('div');
                contentElement.className = 'message-content';
                contentElement.textContent = message.content;

                messageElement.appendChild(contentElement);
                chatContainer.appendChild(messageElement);
            });

            // Actualizar la lista de chats para resaltar el chat activo
            this.loadChatList();
        } catch (error) {
            console.error('Error al cargar mensajes:', error);
        }
    }

    /**
     * Guarda un mensaje en la base de datos.
     */
    async saveMessage(conversationId, role, content) {
        try {
            const response = await fetch('/messages', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.token}`
                },
                body: JSON.stringify({
                    conversation_id: conversationId,
                    role: role,
                    content: content
                })
            });

            if (!response.ok) {
                throw new Error('Error al guardar el mensaje');
            }

            return await response.json();
        } catch (error) {
            console.error('Error al guardar mensaje:', error);
            return null;
        }
    }
}