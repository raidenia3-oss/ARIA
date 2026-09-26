/**
 * ════════════════════════════════════════════════════════════════════════════════════════════════════
 *   OSINT_RECON — Módulo de Reconocimiento OSINT
 *   Interfaz táctica para búsquedas en redes sociales
 *   AME Project — AURA
 * ════════════════════════════════════════════════════════════════════════════════════════════════════
 */

class OSINTRecon {
    constructor() {
        this.container = null;
        this.header = null;
        this.closeBtn = null;
        this.content = null;
        this.searchSection = null;
        this.searchInput = null;
        this.searchBtn = null;
        this.platformsSection = null;
        this.resultsSection = null;
        this.spinner = null;
        this.errorElement = null;
        this.successElement = null;
        this.statusElement = null;
        this.platformButtons = {};
        this.selectedPlatforms = [];
        this.osintApiUrl = 'https://aura-server-01.vercel.app/api/osint';
        this.osintLinksUrl = 'https://aura-server-01.vercel.app/api/osint/links';
        this.authToken = window.AURA_LockManager ? window.AURA_LockManager.getAuthToken() : null;
    }

    init() {
        // Crear el contenedor principal
        this.container = document.createElement('div');
        this.container.className = 'osint-container';
        this.container.id = 'osintReconContainer';

        // Crear header
        this.header = document.createElement('div');
        this.header.className = 'osint-header';

        this.title = document.createElement('div');
        this.title.className = 'osint-title';
        this.title.textContent = 'OSINT RECON';

        this.closeBtn = document.createElement('button');
        this.closeBtn.className = 'osint-close-btn';
        this.closeBtn.innerHTML = '&times;';
        this.closeBtn.addEventListener('click', () => this.close());

        this.header.appendChild(this.title);
        this.header.appendChild(this.closeBtn);

        // Crear contenido
        this.content = document.createElement('div');
        this.content.className = 'osint-content';

        // Sección de búsqueda
        this.searchSection = document.createElement('div');
        this.searchSection.className = 'osint-search-section';

        this.searchTitle = document.createElement('div');
        this.searchTitle.className = 'osint-search-title';
        this.searchTitle.textContent = 'Búsqueda OSINT';

        this.searchInput = document.createElement('input');
        this.searchInput.type = 'text';
        this.searchInput.className = 'osint-search-input';
        this.searchInput.placeholder = 'Ingrese el nombre o término a buscar (ej: Elon Musk)';

        this.searchBtn = document.createElement('button');
        this.searchBtn.className = 'osint-search-btn';
        this.searchBtn.innerHTML = `
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
            </svg>
            Buscar
        `;
        this.searchBtn.disabled = true;
        this.searchBtn.addEventListener('click', () => this.performSearch());

        this.searchSection.appendChild(this.searchTitle);
        this.searchSection.appendChild(this.searchInput);
        this.searchSection.appendChild(this.searchBtn);

        // Plataformas disponibles
        this.platformsSection = document.createElement('div');
        this.platformsSection.className = 'osint-platforms';

        const platforms = [
            { name: 'Twitter', value: 'twitter' },
            { name: 'Instagram', value: 'instagram' },
            { name: 'Facebook', value: 'facebook' },
            { name: 'LinkedIn', value: 'linkedin' },
            { name: 'Reddit', value: 'reddit' },
            { name: 'YouTube', value: 'youtube' }
        ];

        platforms.forEach(platform => {
            const btn = document.createElement('button');
            btn.className = 'osint-platform-btn';
            btn.textContent = platform.name;
            btn.dataset.value = platform.value;
            btn.addEventListener('click', () => this.togglePlatform(platform.value));
            this.platformButtons[platform.value] = btn;
            this.platformsSection.appendChild(btn);
        });

        // Resultados
        this.resultsSection = document.createElement('div');
        this.resultsSection.className = 'osint-results';

        this.resultsTitle = document.createElement('div');
        this.resultsTitle.className = 'osint-results-title';
        this.resultsTitle.textContent = 'Resultados OSINT';

        this.resultsEmpty = document.createElement('div');
        this.resultsEmpty.className = 'osint-results-empty';
        this.resultsEmpty.textContent = 'Realiza una búsqueda para ver resultados';

        this.resultsContent = document.createElement('div');
        this.resultsContent.id = 'osintResultsContent';

        this.resultsSection.appendChild(this.resultsTitle);
        this.resultsSection.appendChild(this.resultsEmpty);
        this.resultsSection.appendChild(this.resultsContent);

        // Spinner
        this.spinner = document.createElement('div');
        this.spinner.className = 'osint-spinner';

        // Status
        this.statusElement = document.createElement('div');
        this.statusElement.className = 'osint-status';
        this.statusElement.textContent = 'Listo para realizar búsquedas OSINT';

        // Error
        this.errorElement = document.createElement('div');
        this.errorElement.className = 'osint-error';
        this.errorElement.style.display = 'none';

        // Success
        this.successElement = document.createElement('div');
        this.successElement.className = 'osint-success';
        this.successElement.style.display = 'none';

        // Footer
        this.footer = document.createElement('div');
        this.footer.className = 'osint-footer';

        this.closeFooterBtn = document.createElement('button');
        this.closeFooterBtn.className = 'osint-footer-btn';
        this.closeFooterBtn.textContent = 'Cerrar';
        this.closeFooterBtn.addEventListener('click', () => this.close());

        this.footer.appendChild(this.closeFooterBtn);

        // Agregar todo al contenido
        this.content.appendChild(this.searchSection);
        this.content.appendChild(this.platformsSection);
        this.content.appendChild(this.spinner);
        this.content.appendChild(this.statusElement);
        this.content.appendChild(this.errorElement);
        this.content.appendChild(this.successElement);
        this.content.appendChild(this.resultsSection);
        this.content.appendChild(this.footer);

        // Agregar al contenedor principal
        this.container.appendChild(this.header);
        this.container.appendChild(this.content);

        // Agregar al DOM
        document.body.appendChild(this.container);

        // Event listeners
        this.searchInput.addEventListener('input', () => {
            this.searchBtn.disabled = !this.searchInput.value.trim();
        });

        // Ocultar por defecto
        this.container.style.display = 'none';
    }

    togglePlatform(platform) {
        if (this.selectedPlatforms.includes(platform)) {
            this.selectedPlatforms = this.selectedPlatforms.filter(p => p !== platform);
            this.platformButtons[platform].classList.remove('active');
        } else {
            this.selectedPlatforms.push(platform);
            this.platformButtons[platform].classList.add('active');
        }
    }

    async performSearch() {
        const target = this.searchInput.value.trim();
        if (!target) return;

        this.clearResults();
        this.showSpinner();
        this.hideError();
        this.hideSuccess();

        try {
            // Validar que hay al menos una plataforma seleccionada
            if (this.selectedPlatforms.length === 0) {
                this.showError('Selecciona al menos una plataforma');
                return;
            }

            // Realizar la búsqueda OSINT
            const response = await fetch(this.osintApiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.authToken}`
                },
                body: JSON.stringify({
                    target: target,
                    platforms: this.selectedPlatforms
                })
            });

            const data = await response.json();

            if (response.ok) {
                this.showSuccess(`Búsqueda completada para ${target}`);
                this.displayResults(data.results);
            } else {
                this.showError(data.message || 'Error al realizar la búsqueda');
            }
        } catch (error) {
            console.error('Error en búsqueda OSINT:', error);
            this.showError('Error de conexión con el servidor OSINT');
        } finally {
            this.hideSpinner();
        }
    }

    displayResults(results) {
        const resultsContainer = document.getElementById('osintResultsContent');
        resultsContainer.innerHTML = '';

        if (!results || results.length === 0) {
            this.resultsEmpty.textContent = 'No se encontraron resultados para esta búsqueda';
            this.resultsEmpty.style.display = 'block';
            return;
        }

        this.resultsEmpty.style.display = 'none';

        results.forEach((result, index) => {
            const resultItem = document.createElement('div');
            resultItem.className = 'osint-result-item';

            const resultHeader = document.createElement('div');
            resultHeader.className = 'osint-result-header';

            const resultTitle = document.createElement('div');
            resultTitle.className = 'osint-result-title';
            resultTitle.textContent = result.title || `Resultado ${index + 1}`;

            const resultUrl = document.createElement('div');
            resultUrl.className = 'osint-result-url';
            resultUrl.textContent = result.url;

            const resultPlatform = document.createElement('div');
            resultPlatform.className = 'osint-result-platform';
            resultPlatform.textContent = result.platform.toUpperCase();

            resultHeader.appendChild(resultTitle);
            resultHeader.appendChild(resultUrl);
            resultHeader.appendChild(resultPlatform);

            const resultContent = document.createElement('div');
            resultContent.className = 'osint-result-content';
            resultContent.textContent = result.content || 'No hay contenido disponible';

            const resultDescription = document.createElement('div');
            resultDescription.className = 'osint-result-description';
            resultDescription.textContent = result.description || 'No hay descripción disponible';

            resultItem.appendChild(resultHeader);
            resultItem.appendChild(resultContent);
            resultItem.appendChild(resultDescription);

            resultsContainer.appendChild(resultItem);
        });
    }

    clearResults() {
        const resultsContainer = document.getElementById('osintResultsContent');
        resultsContainer.innerHTML = '';
        this.resultsEmpty.style.display = 'block';
    }

    showSpinner() {
        this.spinner.style.display = 'block';
        this.statusElement.textContent = 'Realizando búsqueda OSINT...';
    }

    hideSpinner() {
        this.spinner.style.display = 'none';
    }

    showError(message) {
        this.errorElement.textContent = message;
        this.errorElement.style.display = 'block';
    }

    hideError() {
        this.errorElement.style.display = 'none';
    }

    showSuccess(message) {
        this.successElement.textContent = message;
        this.successElement.style.display = 'block';
    }

    hideSuccess() {
        this.successElement.style.display = 'none';
    }

    open() {
        this.container.style.display = 'flex';
        this.searchInput.focus();
    }

    close() {
        this.container.style.display = 'none';
        this.clearResults();
        this.hideError();
        this.hideSuccess();
        this.statusElement.textContent = 'Listo para realizar búsquedas OSINT';
    }

    // Método para integrar con el chat
    integrateWithChat(chatInstance) {
        if (!chatInstance) return;

        // Añadir comando al chat
        chatInstance.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && this.isCommand(e.target.value)) {
                e.preventDefault();
                this.handleCommand(e.target.value);
            }
        });

        // Añadir botón de OSINT al chat
        const osintBtn = document.createElement('button');
        osintBtn.className = 'mic-button';
        osintBtn.style.marginLeft = '8px';
        osintBtn.innerHTML = `
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
            </svg>
        `;
        osintBtn.title = 'Modo Reconocimiento OSINT';
        osintBtn.addEventListener('click', () => this.open());

        // Insertar el botón después del botón de micrófono
        const micButton = chatInstance.micButton;
        if (micButton) {
            micButton.parentNode.insertBefore(osintBtn, micButton.nextSibling);
        }
    }

    isCommand(text) {
        return text.trim().toLowerCase().startsWith('/osint');
    }

    handleCommand(text) {
        const command = text.trim().toLowerCase();
        const parts = command.split(' ');
        const target = parts.slice(1).join(' ');

        if (target) {
            this.searchInput.value = target;
            this.performSearch();
        } else {
            this.open();
        }
    }
}

// Exportar la clase para uso global
window.OSINTRecon = OSINTRecon;
