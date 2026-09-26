# 📋 Chrome Extension Setup para AURA/AME

Este documento proporciona instrucciones detalladas para configurar, desarrollar y probar la extensión de Chrome para AURA/AME.

---

## 📌 Introducción

La extensión de Chrome para AURA/AME permite a los usuarios interactuar con el sistema desde cualquier página web, mostrando noticias relevantes, recomendaciones personalizadas y controles del avatar AURA.

---

## 📂 Estructura del Proyecto

La extensión se encuentra en la carpeta `chrome-extension-aura/` con los siguientes archivos:

```
chrome-extension-aura/
├── manifest.json          # Configuración de la extensión
├── background.js          # Lógica en segundo plano
├── content.js             # Scripts que se inyectan en las páginas web
├── popup.html             # Interfaz de la ventana emergente
├── popup.js               # Lógica de la ventana emergente
└── styles/
    └── popup.css          # Estilos para la ventana emergente
```

---

## 🛠 Configuración Inicial

### 1. Requisitos Previos

- Google Chrome (versión reciente)
- Node.js (para desarrollo local)
- Editor de código (VS Code recomendado)

### 2. Cargar la Extensión en Chrome

1. **Abre Chrome y ve a la página de extensiones:**

   ```
   chrome://extensions/
   ```

2. **Habilita el modo desarrollador:**
   - Marca la casilla **"Modo desarrollador"** en la esquina superior derecha.

3. **Carga la extensión no empaquetada:**
   - Haz clic en **"Cargar extensión no empaquetada"**.
   - Selecciona la carpeta `chrome-extension-aura` desde tu proyecto.

---

## 📝 Configuración de manifest.json

El archivo `manifest.json` es la configuración principal de la extensión. Aquí está su estructura básica:

```json
{
  "manifest_version": 3,
  "name": "AURA/AME Assistant",
  "version": "1.0",
  "description": "Asistente de noticias y automatización de AURA/AME",
  "permissions": ["storage", "activeTab", "scripting"],
  "host_permissions": [
    "*://*.google.com/*",
    "*://*.vercel.app/*",
    "*://*.aura-ame.com/*"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "action": {
    "default_popup": "popup.html",
    "default_icon": {
      "16": "icons/icon16.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  }
}
```

### 🔹 Permisos Explicados

| Permiso            | Descripción                                                              |
| ------------------ | ------------------------------------------------------------------------ |
| `storage`          | Acceso al almacenamiento local de Chrome para guardar datos del usuario. |
| `activeTab`        | Permite interactuar con la pestaña activa.                               |
| `scripting`        | Permite inyectar scripts en páginas web.                                 |
| `host_permissions` | Dominios permitidos para la extensión (ajustar según tus necesidades).   |

---

## 🖥 Implementación de Funcionalidades

### 1. background.js

Este archivo contiene la lógica que se ejecuta en segundo plano, incluso cuando la extensión no está abierta.

```javascript
// background.js
console.log("🚀 AURA/AME Chrome Extension - Background script loaded");

// Escuchar mensajes desde el popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getNews") {
    // Lógica para obtener noticias desde el backend de AURA/AME
    fetchNewsFromAuraAME().then((news) => {
      sendResponse({ news: news });
    });
    return true; // Necesario para usar sendResponse asíncronamente
  }
});

// Función simulada para obtener noticias
async function fetchNewsFromAuraAME() {
  // En un entorno real, esto conectaría con el backend de AURA/AME
  return [
    {
      title: "Nuevo avance en inteligencia artificial",
      source: "TechCrunch",
      summary:
        "Google presenta Gemini 2.0 con capacidades mejoradas de razonamiento...",
      relevance: 9,
    },
    {
      title: "Anime del mes: Cyberpunk: Edgerunners",
      source: "MyAnimeList",
      summary: "La nueva serie de anime basada en el juego Cyberpunk 2077...",
      relevance: 8,
    },
  ];
}

// Escuchar cambios en las pestañas activas
chrome.tabs.onActivated.addListener((activeInfo) => {
  chrome.tabs.get(activeInfo.tabId, (tab) => {
    if (tab.url.includes("news") || tab.url.includes("anime")) {
      // Notificar al popup que hay una pestaña relevante abierta
      chrome.runtime.sendMessage({
        action: "tabUpdated",
        tabUrl: tab.url,
      });
    }
  });
});
```

### 2. popup.js

Este archivo maneja la lógica de la ventana emergente que se muestra al hacer clic en el icono de la extensión.

```javascript
// popup.js
document.addEventListener("DOMContentLoaded", () => {
  const newsList = document.getElementById("news-list");
  const avatarStatus = document.getElementById("avatar-status");
  const loadNewsButton = document.getElementById("load-news");

  // Cargar noticias al abrir el popup
  loadNews();

  // Event listener para el botón de cargar noticias
  loadNewsButton.addEventListener("click", loadNews);

  // Escuchar mensajes del background script
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "newsLoaded") {
      displayNews(request.news);
    } else if (request.action === "tabUpdated") {
      updateTabStatus(request.tabUrl);
    }
  });

  async function loadNews() {
    try {
      // Mostrar estado de carga
      newsList.innerHTML = "<li>Cargando noticias...</li>";

      // Enviar mensaje al background script para obtener noticias
      chrome.runtime.sendMessage({ action: "getNews" }, (response) => {
        if (response && response.news) {
          displayNews(response.news);
        } else {
          newsList.innerHTML = "<li>No se pudieron cargar las noticias.</li>";
        }
      });
    } catch (error) {
      newsList.innerHTML = `<li>Error: ${error.message}</li>`;
    }
  }

  function displayNews(newsItems) {
    if (!newsItems || newsItems.length === 0) {
      newsList.innerHTML = "<li>No hay noticias disponibles.</li>";
      return;
    }

    let html = "";
    newsItems.forEach((item) => {
      html += `
        <li class="news-item">
          <h3>${item.title}</h3>
          <p class="source">Fuente: ${item.source}</p>
          <p class="summary">${item.summary}</p>
          <p class="relevance">Relevancia: ${item.relevance}/10</p>
        </li>
      `;
    });

    newsList.innerHTML = html;
  }

  function updateTabStatus(tabUrl) {
    avatarStatus.textContent = `🔍 Analizando contenido en: ${new URL(tabUrl).hostname}`;
    setTimeout(() => {
      avatarStatus.textContent = "🤖 Listo para ayudarte";
    }, 3000);
  }
});
```

### 3. content.js

Este archivo se inyecta en las páginas web y permite interactuar con el DOM de la página actual.

```javascript
// content.js
console.log("🌐 AURA/AME Chrome Extension - Content script loaded");

// Escuchar mensajes desde el background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "highlightNews") {
    highlightNewsElements();
    return true;
  }
});

function highlightNewsElements() {
  // Ejemplo: resaltar elementos que parezcan ser noticias
  const selectors = [
    "article",
    "div.news",
    "div.article",
    "h2 + p",
    "h3 + p",
    "h4 + p",
  ];

  selectors.forEach((selector) => {
    const elements = document.querySelectorAll(selector);
    elements.forEach((el) => {
      if (
        el.textContent.includes("noticia") ||
        el.textContent.includes("News") ||
        el.textContent.includes("actualidad")
      ) {
        el.style.border = "2px solid #00ff88";
        el.style.backgroundColor = "rgba(0, 255, 136, 0.1)";
        el.style.padding = "8px";
        el.style.borderRadius = "4px";
      }
    });
  });
}

// Detectar cuando el usuario hace clic en un elemento destacado
document.addEventListener("click", (e) => {
  if (e.target.style.border === "2px solid #00ff88") {
    // Enviar información del elemento al background script
    chrome.runtime.sendMessage({
      action: "userClickedNews",
      elementText: e.target.textContent,
      elementUrl: window.location.href,
    });
  }
});
```

---

## 🎨 Estilos para popup.css

```css
/* popup.css */
body {
  width: 300px;
  height: 400px;
  padding: 10px;
  font-family: "Courier New", monospace;
  background-color: #121212;
  color: #00ff88;
}

h1 {
  color: #00ff88;
  font-size: 1.2em;
  margin-top: 0;
  text-align: center;
}

#news-list {
  list-style: none;
  padding: 0;
  margin: 10px 0;
  max-height: 300px;
  overflow-y: auto;
}

.news-item {
  background-color: #1e1e1e;
  margin-bottom: 10px;
  padding: 8px;
  border-radius: 4px;
}

.news-item h3 {
  margin: 5px 0;
  color: #00ff88;
}

.source {
  font-size: 0.8em;
  color: #888;
  margin: 5px 0;
}

.summary {
  font-size: 0.9em;
  margin: 5px 0;
  line-height: 1.4;
}

.relevance {
  font-size: 0.8em;
  color: #00ff88;
  font-weight: bold;
}

#load-news {
  display: block;
  width: 100%;
  padding: 8px;
  background-color: #00ff88;
  color: #121212;
  border: none;
  border-radius: 4px;
  font-family: "Courier New", monospace;
  cursor: pointer;
  margin-top: 10px;
}

#load-news:hover {
  background-color: #00cc6a;
}

#avatar-status {
  text-align: center;
  font-size: 0.9em;
  color: #888;
  margin-top: 10px;
}

#avatar-status.active {
  color: #00ff88;
}
```

---

## 📥 Integración con el Backend de AURA/AME

Para conectar la extensión con el backend de AURA/AME, necesitas implementar las siguientes funciones en `background.js`:

### 1. Función para Obtener Noticias

```javascript
async function fetchNewsFromAuraAME() {
  try {
    const response = await fetch("https://tu-api-de-aura-ame.com/api/news", {
      method: "GET",
      headers: {
        Authorization: `Bearer ${await getAuthToken()}`,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Error al obtener noticias: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error("Error al conectar con el backend:", error);
    // Retornar noticias simuladas si falla la conexión
    return [
      {
        title: "Noticia simulada: Tecnología",
        source: "AURA/AME",
        summary: "Contenido simulado para desarrollo local.",
        relevance: 7,
      },
    ];
  }
}
```

### 2. Función para Obtener Token de Autenticación

```javascript
async function getAuthToken() {
  // Obtener token del almacenamiento local o del backend
  let token = localStorage.getItem("auraAmeAuthToken");

  if (!token) {
    // Solicitar token al backend si no existe
    const authResponse = await fetch(
      "https://tu-api-de-aura-ame.com/api/auth/token",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          userId: "user_123", // Obtener del usuario
          extensionId: chrome.runtime.id,
        }),
      },
    );

    if (authResponse.ok) {
      const data = await authResponse.json();
      token = data.token;
      localStorage.setItem("auraAmeAuthToken", token);
    } else {
      console.error("Error al obtener token de autenticación");
      return null;
    }
  }

  return token;
}
```

---

## 🧪 Pruebas y Validación

### 1. Pruebas Locales

1. **Carga la extensión en Chrome** como se describe en la sección de configuración inicial.
2. **Abre el popup** haciendo clic en el icono de la extensión.
3. **Verifica que:**
   - El popup se carga correctamente.
   - Los estilos se aplican correctamente.
   - El botón "Cargar Noticias" funciona.
   - Las noticias simuladas se muestran correctamente.

### 2. Pruebas de Funcionalidad

1. **Interacción con páginas web:**
   - Navega a diferentes páginas (ej: noticias, blogs, redes sociales).
   - Verifica que la extensión no cause errores.

2. **Pruebas de conexión con el backend:**
   - Si tienes acceso al backend, verifica que las solicitudes se envíen correctamente.
   - Prueba con y sin conexión a internet para validar el comportamiento de fallback.

3. **Pruebas de almacenamiento:**
   - Verifica que los datos se guarden correctamente en `chrome.storage.local`.
   - Prueba la recuperación de datos después de cerrar y reabrir la extensión.

---

## 📸 Capturas de Pantalla

Para documentar la extensión, toma capturas de pantalla de:

1. **El icono de la extensión en la barra de herramientas de Chrome.**
2. **La ventana emergente (popup) abierta.**
3. **La extensión interactuando con una página web (ej: resaltando noticias).**
4. **El menú de configuración de la extensión (si lo implementas).**

Guarda las capturas en la carpeta `docs/screenshots/` para incluir en la documentación.

---

## 📋 Documentación Adicional

### 1. Personalización de la Extensión

Puedes personalizar la extensión modificando:

- **Iconos:** Reemplaza los archivos en la carpeta `icons/` con tus propios diseños.
- **Colores:** Modifica los colores en `popup.css` para que coincidan con la identidad visual de AURA/AME.
- **Funcionalidades:** Añade más botones o secciones al popup según tus necesidades.

### 2. Publicación en Chrome Web Store

Cuando estés listo para publicar la extensión:

1. **Empaqueta la extensión:**

   ```bash
   cd chrome-extension-aura
   zip -r ../aura-ame-extension.zip .
   ```

2. **Sube a Chrome Web Store:**
   - Ve a [Chrome Developer Dashboard](https://chrome.google.com/webstore/devconsole).
   - Paga la tarifa de desarrollador (una sola vez).
   - Sube tu archivo `.zip` y completa la información de la extensión.

3. **Requisitos para publicación:**
   - Descripción clara y completa.
   - Iconos de diferentes tamaños.
   - Capturas de pantalla.
   - Política de privacidad.
   - Términos de servicio.

---

## 🔄 Solución de Problemas

### Problema: La extensión no se carga

**Posibles causas y soluciones:**

1. **Error en manifest.json:**
   - Verifica que no haya errores de sintaxis.
   - Asegúrate de que todos los archivos referenciados existan.

2. **Permisos insuficientes:**
   - Verifica que los permisos en `manifest.json` sean correctos.
   - Si necesitas permisos adicionales, ajusta la configuración.

3. **Errores en los scripts:**
   - Abre la consola de Chrome (`chrome://extensions/` > Inspeccionar vista de fondo).
   - Revisa los logs de error.

4. **Versión de Chrome:**
   - Asegúrate de estar usando una versión reciente de Chrome.
   - Algunas funciones pueden requerir Manifest V3.

### Problema: Los scripts no se inyectan en las páginas

**Posibles causas y soluciones:**

1. **Permiso `activeTab` o `scripting` faltante:**
   - Añade `"activeTab"` o `"scripting"` a los permisos en `manifest.json`.

2. **Error en el código de content.js:**
   - Verifica que no haya errores de sintaxis.
   - Asegúrate de que los selectores de DOM sean correctos.

3. **Contexto de ejecución:**
   - Algunos métodos de DOM pueden no estar disponibles en el contexto de content script.
   - Usa `chrome.scripting.executeScript` para inyectar scripts de manera segura.

### Problema: La extensión se cierra inesperadamente

**Posibles causas y soluciones:**

1. **Error en el background script:**
   - Revisa los logs en `chrome://extensions/` > Inspeccionar vista de fondo.
   - Asegúrate de manejar errores correctamente.

2. **Recursos sin liberar:**
   - Cierra correctamente conexiones, listeners y otros recursos.
   - Usa `try/catch` para manejar errores asíncronos.

3. **Conflictos con otras extensiones:**
   - Desactiva otras extensiones para verificar si hay conflictos.

---

## 🎯 Próximos Pasos

1. **Implementar funcionalidades adicionales:**
   - Sistema de notificaciones push.
   - Configuración de preferencias del usuario.
   - Integración con el sistema de recompensas de Godot.

2. **Optimizar el rendimiento:**
   - Minimizar el uso de recursos en segundo plano.
   - Implementar caché para noticias y datos del usuario.

3. **Añadir más pruebas:**
   - Pruebas unitarias para funciones críticas.
   - Pruebas de integración con el backend.
   - Pruebas de usuario con diferentes escenarios.

4. **Documentar la API de la extensión:**
   - Crear documentación técnica para desarrolladores que quieran extender la extensión.
   - Detallar los mensajes que se pueden enviar/reibir entre scripts.

---

## 📌 Ejemplo de Flujo de Trabajo

1. **Usuario abre una página de noticias en Chrome.**
2. **La extensión detecta que es una página relevante y muestra una notificación.**
3. **Usuario hace clic en el icono de la extensión.**
4. **Se abre el popup y se cargan las noticias más relevantes.**
5. **Usuario selecciona una noticia para obtener más detalles.**
6. **La extensión envía la información al backend de AURA/AME para análisis adicional.**
7. **El backend devuelve recomendaciones personalizadas que se muestran en el popup.**

---

## 📚 Recursos Útiles

- [Documentación Oficial de Extensiones de Chrome](https://developer.chrome.com/docs/extensions/)
- [Manifest V3](https://developer.chrome.com/docs/extensions/mv3/intro/)
- [chrome.storage API](https://developer.chrome.com/docs/extensions/reference/storage/)
- [chrome.runtime API](https://developer.chrome.com/docs/extensions/reference/runtime/)
- [chrome.tabs API](https://developer.chrome.com/docs/extensions/reference/tabs/)

---
