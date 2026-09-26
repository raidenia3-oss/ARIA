---
title: "Shadow-Core Spec Kit"
description: "Especificación técnica para el módulo Shadow-Core de AURA"
author: "AURA System"
date: "2026-05-27"
tags: ["shadow-core", "osint", "security", "spec"]
---

# 📜 Shadow-Core Spec Kit

## 🎯 Objetivo
Definir la arquitectura, funcionalidades y protocolos del **Shadow-Core**, un microservicio aislado para operaciones avanzadas de OSINT y seguridad.

---

## 🔧 Arquitectura

### 🏗️ Componentes
| Componente | Descripción | Estado |
|------------|-------------|--------|
| **Shadow-Core** | Microservicio en FastAPI (Puerto 5001) | ✅ Operativo |
| **net_recon_ghost.py** | Escaneo de red furtivo (SYN Stealth + ARP) | ✅ Simulado |
| **data_exfiltration_layer.py** | Exfiltración encriptada (AES-256 + DNS/ICMP) | ✅ Operativo |
| **Protocolo de Pánico** | Respuesta a amenazas (Dashboard + 3D) | ✅ Integrado |

---

## 🔄 Protocolos

### 🔗 Endpoints
| Endpoint | Método | Descripción | Estado |
|----------|--------|-------------|--------|
| `/health` | GET | Healthcheck + estado de módulos | ✅ Operativo |
| `/api/net_recon` | POST | Escaneo de red furtivo | ❌ Pendiente |
| `/api/data_exfil` | POST | Preparación de exfiltración | ❌ Pendiente |
| `/api/execute_advanced` | POST | Ejecución de comandos OSINT | ✅ Operativo |

---

## 🛡️ Seguridad

### 🔐 Medidas Implementadas
- **Fingerprint Rotation**: Cambio de fingerprint en cada petición
- **Threat Detection**: Escaneo de amenazas antes de ejecutar comandos
- **AES-256**: Cifrado para exfiltración de datos
- **Protocolo de Pánico**: Respuesta automática a amenazas

### ⚠️ Riesgos Identificados
| Riesgo | Mitigación |
|--------|------------|
| **Fingerprinting** | Rotación de fingerprint en cada petición |
| **Exposición de puertos** | Shadow-Core solo accesible en localhost |
| **Dependencias externas** | Módulos simulados si no hay conexión |
| **Errores en comandos** | Timeout de 30 segundos y manejo de excepciones |

---

## 📝 Metodología

### 🔄 Flujo de Trabajo
1. **Consulta de especificación**: Leer este archivo antes de modificar código
2. **Consulta de conocimientos**: Usar `knowledge_fetcher.py` para buscar en Obsidian
3. **Desarrollo modular**: Crear plugins en `/plugins/` y especificar en `/spec/`
4. **Pruebas**: Ejecutar `_test_endpoints.py` para validar integración

---

## 📁 Estructura de Directorios

```
AURA/
├── spec/                  # Especificaciones técnicas (Spec Kit)
│   ├── 001-shadow-core-spec.md  # Esta especificación
│   └── ...                 # Otras especificaciones
├── plugins/               # Módulos independientes
│   ├── map_module/        # Módulo de visualización 3D
│   ├── osint_tracker/     # Seguimiento de objetivos OSINT
│   └── ...
├── Shadow-Core/          # Módulos del Shadow-Core
│   ├── net_recon_ghost.py
│   ├── data_exfiltration_layer.py
│   └── ...
├── knowledge_fetcher.py  # Integración con Obsidian
└── ...
```

---

## 🔧 Configuración Requerida

### 🌐 Variables de Entorno
| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| `OBSIDIAN_PATH` | Ruta a la bóveda de Obsidian | `C:/Users/User/ObsidianVault` |
| `OBSIDIAN_GRAPHQL` | Endpoint GraphQL de Obsidian | `http://localhost:8080/graphql` |
| `AURA_EXFIL_KEY` | Clave AES-256 para exfiltración | `my_super_secret_key_32_bytes_long!!` |

---

## 🚀 Próximos Pasos

1. **Depurar endpoints**: `/api/net_recon` y `/api/data_exfil`
2. **Integración con Obsidian**: Configurar conexión real con la bóveda
3. **UI Táctica**: Migrar dashboard a Three.js + Cannon.es
4. **IA Local**: Configurar alternancia entre Gemini y Ollama

---

## 📝 Notas Adicionales

- **Simulación**: Los módulos que requieren dependencias externas (ej: scapy) están simulados
- **Seguridad**: Todos los endpoints verifican amenazas antes de procesar peticiones
- **Modularidad**: Los plugins deben ser independientes y auto-contenidos

---
**Última actualización**: 27/05/2026
**Estado**: En desarrollo (Fase 3: Arquitectura Híbrida)