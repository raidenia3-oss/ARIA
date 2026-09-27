# ARIA Core — Referencia Multimedia
> Archivo de referencia para el núcleo de ARIA: fotos, videos, assets visuales.
> Actualizado: 2026-09-26 | v6.0

## Estructura

```
ARIA_CORE_REFERENCE/
├── README.md              # Este archivo
├── screenshots/           # Capturas de pantalla del HUD, orb, dashboards
├── videos/                # Videos de referencia (arquitectura, demos)
├── icons/                 # Iconos y assets
└── diagrams/             # Diagramas de arquitectura
```

## Capturas Disponibles

| Asset | Ruta | Descripción |
|-------|------|-------------|
| Dashboard v5 | `screenshots/dashboard-v5.png` | HUD glassmorphic original |
| Widget | `screenshots/widget.png` | Widget flotante ARIA |
| Axum POC | `screenshots/axum-poc.png` | Backend Rust health endpoint |
| Neural Brain | `screenshots/neural-brain-dashboard.png` | Phase N: agent visualization |
| v6.0 Dashboard | `screenshots/v6.0-dashboard.png` | Dashboard completo v6.0 |

## Diagramas

| Asset | Ruta | Uso |
|-------|------|-----|
| Arquitectura v5.0 | `diagrams/architecture.mermaid` | Flujo de datos completo |
| Arquitectura v6.0 | `diagrams/v6.0-architecture.mermaid` | Rediseño con Axum + Neural Brain |

## Videos (por agregar)
```
videos/
├── architecture-overview.mp4    # Demo de arquitectura
├── orb-3d-demo.mp4              # Demo del orbe 3D
├── swarm-demo.mp4               # Ejecución paralela de agentes
├── neural-brain-demo.mp4        # Visualización de agentes
└── jarvis-voice-demo.mp4        # Control por voz
```

## Cómo contributions
1. Coloca fotos en `screenshots/`
2. Coloca videos en `videos/`
3. Actualiza este README con las referencias

## Especificaciones
- Capturas: PNG, al menos 1280x720
- Videos: MP4 H.264, <60s
- Iconos: SVG o PNG