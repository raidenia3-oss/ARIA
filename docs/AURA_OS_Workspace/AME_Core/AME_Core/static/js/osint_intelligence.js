/**
 * Módulo de Inteligencia OSINT para AME.
 * Gestiona la búsqueda en diferentes plataformas y muestra los resultados en tarjetas táctiles.
 */

// Configuración de la API
const OSINT_API_URL = 'https://aura-server-01.vercel.app/api/search';
const MASTER_API_KEY = 'AURA_MASTER_KEY_2026';

// Función para realizar la búsqueda OSINT
async function performOsintSearch(query, platform) {
    try {
        const response = await fetch(OSINT_API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-KEY': MASTER_API_KEY
            },
            body: JSON.stringify({
                query: query,
                target_platform: platform,
                max_results: 10
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'Error en la búsqueda OSINT');
        }

        const data = await response.json();
        return data.results || [];
    } catch (error) {
        console.error('Error al realizar la búsqueda:', error);
        return [];
    }
}

// Función para renderizar los resultados de la búsqueda
function renderSearchResults(results) {
    const resultsContainer = document.getElementById('osint-results-container');
    if (!resultsContainer) return;

    // Limpiar resultados anteriores
    resultsContainer.innerHTML = '';

    if (results.length === 0) {
        resultsContainer.innerHTML = '<div class="no-results">No se encontraron resultados.</div>';
        return;
    }

    // Renderizar cada resultado como una tarjeta táctil
    results.forEach(result => {
        const card = document.createElement('div');
        card.className = 'osint-result-card';
        card.innerHTML = `
            <div class="osint-card-header">
                <h3>${result.title || 'Sin título'}</h3>
                <span class="osint-card-platform">${result.platform || 'Web'}</span>
            </div>
            <div class="osint-card-body">
                <p>${result.snippet || 'No hay fragmento disponible'}</p>
            </div>
            <div class="osint-card-footer">
                <a href="${result.link || '#'}" class="osint-open-link-btn" target="_blank" rel="noopener noreferrer">
                    Abrir Enlace
                </a>
            </div>
        `;

        // Agregar evento para abrir el enlace
        const openLinkBtn = card.querySelector('.osint-open-link-btn');
        openLinkBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (result.link) {
                window.open(result.link, '_system', 'location=yes');
            }
        });

        resultsContainer.appendChild(card);
    });
}

// Función para manejar el estado de carga
function setSearchLoading(state) {
    const searchBtn = document.getElementById('osint-search-btn');
    const platformControls = document.querySelectorAll('.osint-platform-control');
    const searchInput = document.getElementById('osint-search-input');

    if (state) {
        // Estado de carga activado
        searchBtn.disabled = true;
        searchBtn.innerHTML = '<span class="spinner"></span> Rastreando Red...';
        platformControls.forEach(btn => btn.disabled = true);
        searchInput.disabled = true;
    } else {
        // Estado de carga desactivado
        searchBtn.disabled = false;
        searchBtn.innerHTML = '🔍 Iniciar Rastreo';
        platformControls.forEach(btn => btn.disabled = false);
        searchInput.disabled = false;
    }
}

// Función para manejar el cambio de plataforma
function handlePlatformChange(platform) {
    document.querySelectorAll('.osint-platform-control').forEach(btn => {
        btn.classList.remove('active');
    });

    const selectedBtn = document.querySelector(`.osint-platform-control[data-platform="${platform}"]`);
    if (selectedBtn) {
        selectedBtn.classList.add('active');
    }
}

// Inicialización del módulo
function initOsintModule() {
    // Crear el contenedor de resultados si no existe
    if (!document.getElementById('osint-results-container')) {
        const dashboardContainer = document.querySelector('.dashboard-container');
        if (dashboardContainer) {
            const osintModule = document.createElement('div');
            osintModule.id = 'osint-module';
            osintModule.className = 'dashboard-card osint-module-card';
            osintModule.innerHTML = `
                <h2>🔍 Módulo de Inteligencia</h2>
                <div class="osint-search-controls">
                    <input type="text" id="osint-search-input" class="osint-search-input" placeholder="Introducir objetivo o palabra clave...">
                    <div class="osint-platform-controls">
                        <button class="osint-platform-control active" data-platform="web">🌐 Web</button>
                        <button class="osint-platform-control" data-platform="twitter">🐦 X/Twitter</button>
                        <button class="osint-platform-control" data-platform="instagram">📸 Instagram</button>
                    </div>
                    <button id="osint-search-btn" class="btn btn-primary">🔍 Iniciar Rastreo</button>
                </div>
                <div id="osint-results-container" class="osint-results-container"></div>
            `;
            dashboardContainer.appendChild(osintModule);
        }
    }

    // Event listeners para los controles de plataforma
    document.querySelectorAll('.osint-platform-control').forEach(btn => {
        btn.addEventListener('click', () => {
            const platform = btn.getAttribute('data-platform');
            handlePlatformChange(platform);
        });
    });

    // Event listener para el botón de búsqueda
    const searchBtn = document.getElementById('osint-search-btn');
    if (searchBtn) {
        searchBtn.addEventListener('click', async () => {
            const searchInput = document.getElementById('osint-search-input');
            const platformBtn = document.querySelector('.osint-platform-control.active');
            const platform = platformBtn ? platformBtn.getAttribute('data-platform') : 'web';

            const query = searchInput.value.trim();
            if (!query) {
                alert('Por favor, introduce un objetivo o palabra clave.');
                return;
            }

            // Mostrar estado de carga
            setSearchLoading(true);

            try {
                // Realizar la búsqueda
                const results = await performOsintSearch(query, platform);
                renderSearchResults(results);
            } catch (error) {
                console.error('Error:', error);
                const resultsContainer = document.getElementById('osint-results-container');
                if (resultsContainer) {
                    resultsContainer.innerHTML = `<div class="error-message">Error: ${error.message}</div>`;
                }
            } finally {
                // Ocultar estado de carga
                setSearchLoading(false);
            }
        });
    }

    // Event listener para presionar Enter en el input
    const searchInput = document.getElementById('osint-search-input');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                searchBtn.click();
            }
        });
    }
}

// Inicializar el módulo cuando la página esté lista
document.addEventListener('DOMContentLoaded', initOsintModule);
