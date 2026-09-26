# Monetization Context — AURA Landing Page

## Producto
Recursos de Inteligencia Artificial gratuitos: herramientas, guías y enlaces a modelos open-source. Todo el contenido es de acceso libre y está orientado a entusiastas de la IA.

## Tecnología
- **HTML5 semántico** con estructura accesible.
- **Tailwind CSS** vía CDN para estilos utilitarios rápidos.
- **JavaScript vanilla** para interactividad y carga de anuncios.
- **Glassmorphism 3D** como identidad visual (fondos con blur, bordes translúcidos, sombras suaves).
- Diseño responsive 100% (mobile-first).

## Delivery
- Despliegue estático en **Vercel**.
- Sin dependencias de build; solo HTML/CSS/JS plano.
- Dominio personalizado opcional.

## Monetización (Adsterra)
- **Social Bar** flotante visible en toda la navegación.
- **Popunder** disparado en el primer clic sobre cualquier enlace de recurso gratuito.
- Códigos de Adsterra inyectados como scripts externos y configuraciones inline.

## Meta Verificable
0 errores de renderizado en la validación automática.

---

## Tráfico Orgánico Automatizado (Módulo 12)

### Fuentes de datos
- **RSS público de IA**: Hacker News, Google News AI section, Reddit r/artificial, r/MachineLearning.
- **APIs gratuitas**: Currents API, NewsAPI (plan developer), Hugging Face Papers.

### Volumen estimado
- Captura diaria: 3–7 tendencias relevantes de IA.
- Generación automática: micro-publicaciones con título atractivo, resumen, enlace UTM y categoría.
- Inyección en la landing page: contenido fresco cada 6–12 horas (SEO boost).

### Destino
- Archivos JSON en `ame-backend/src/traffic/output/`.
- Endpoint interno `GET /traffic/trends` (futuro) para servir contenido dinámico.
- Consumo directo desde `index.html` vía fetch a GitHub Pages o al backend.

### Herramientas
- **Python**: `feedparser` (RSS), `urllib` (HTTP), `json` (serialización).
- **Reescritura**: reglas de transformación heurísticas (sin dependencia LLM).
- **Tracking**: parámetros UTM estándar (`utm_source=aura_traffic&utm_medium=rss&utm_campaign=ia_trending`).

## Meta Verificable Módulo 12
El módulo `traffic_generator.py` debe generar contenido sin texto vacío, con enlaces UTM válidos y estructura JSON limpia.

