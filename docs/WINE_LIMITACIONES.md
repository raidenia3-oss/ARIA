# Limitaciones de Wine en el entorno Kali de ARIA

## Resumen

El entorno Kali dedicado para ARIA incluye `wine` (preconfigurado) para ejecutar aplicaciones Windows (`.exe`) bajo Linux. **No es un reemplazo confiable para software complejo.**

## Hallazgos clave (basados en análisis de referencia)

| Categoría | Hallazgo | Impacto en ARIA |
|---|---|---|
| Apps simples | WinRAR, capturadores de pantalla: funcionan bien | Utilitario básico aceptable |
| Apps complejas | Microsoft Office: presenta fallos | No usar para productividad ofimática crítica |
| Gaming | No soportado de forma fiable | Descartar para uso gaming |
| Rendimiento | Overhead de traducción de API Win32 → POSIX | Latencia adicional, consumo de CPU/RAM |

## Recomendación para ARIA

- **No confiar en Wine** para ejecutar herramientas de seguridad Windows (.exe) dentro de la VM Kali.
- Usar las herramientas nativas de Kali (`nmap`, `metasploit-framework`, `tcpdump`, etc.) en su lugar.
- `wine` se mantiene solo como utilitario opcional para apps ligeras, sin garantías de estabilidad.

## Referencia

Este documento se deriva del análisis de Winux 11 LTSC (KDE Plasma con skin Windows 11), donde Wine demostró soporte parcial para aplicaciones Windows pero fallos en software complejo como Microsoft Office.
