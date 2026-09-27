# ARIA Core — Referencia Multimedia
> Archivo de referencia para el núcleo de ARIA: fotos, videos, assets visuales.
> Este archivo es un índice; los archivos multimedia se colocan en las carpetas indicadas.

## Estructura

```
ARIA_CORE_REFERENCE/
├── README.md              # Este archivo
├── screenshots/           # Capturas de pantalla del HUD, orb, dashboards
│   ├── orb-default.png
│   ├── orb-animated.gif
│   ├── dashboard-v5.png
│   └── ...
├── videos/                # Videos de referencia (arquitectura, demos)
│   ├── architecture-overview.mp4
│   ├── orb-3d-demo.mp4
│   ├── swarm-demo.mp4
│   └── ...
├── icons/                 # Iconos y assets
│   ├── aria-icon.png
│   ├── tray-icon.png
│   └── ...
└── diagrams/             # Diagramas de arquitectura
    ├── architecture.mermaid
    ├── data-flow.mermaid
    └── ...
```

## Cómo usar

1. Coloca fotos en `screenshots/`
2. Coloca videos en `videos/`
3. Actualiza este README con las referencias

## Referencias Rápidas

| Asset | Ruta | Uso |
|-------|------|-----|
| Orb 3D default | `screenshots/orb-default.png` | Referencia visual del núcleo |
| Dashboard v5 | `screenshots/dashboard-v5.png` | Interfaz principal |
| Arquitectura | `diagrams/architecture.mermaid` | Diagrama de flujo |
| Demo swarm | `videos/swarm-demo.mp4` | Ejecución paralela de agentes |

## Notas
- Los videos deben ser < 60s para referencia rápida
- Las capturas deben ser al menos 1280x720
- Formatos recomendados: PNG (fotos), MP4 H.264 (videos), SVG/PNG (iconos)