# AURA SYSTEM CONTEXT - Mapa de Herramientas Disponibles

## Fecha de Creación: 2026-07-01
## Propósito: Documentar herramientas de desarrollo disponibles en el sistema para integración con AURA

---

## 🔧 Herramientas de Desarrollo Instaladas

### 1. Java (Eclipse Adoptium)
- **Ruta:** `C:\Program Files\Eclipse Adoptium\jdk-21.0.11.0\bin\java.exe`
- **Versión:** 21.0.11.0
- **Uso:** Desarrollo Android, backend Java, herramientas basadas en JVM

### 2. Godot Engine
- **Ruta:** `C:\Users\User\OneDrive\Escritorio\Godot_v4.6-stable_win64.exe`
- **Versión:** 4.6 (stable)
- **Uso:** Desarrollo de interfaces 3D para AURA_Tactical_UI

### 3. Unity
- **Ruta:** `C:\Program Files\Unity\Hub\Editor\6000.3.10f1\Editor\Unity.exe`
- **Versión:** 6000.3.10f1
- **Uso:** Desarrollo de experiencias inmersivas 3D

### 4. Android Studio / SDK
- **Ruta:** `C:\Program Files\Android\Android Studio\bin\studio64.exe`
- **ADB:** `C:\Program Files\Netease\MuMuPlayer\nx_device\12.0\shell\adb.exe`
- **Uso:** Compilación de APKs para AME_Core

---

## 📋 Extensiones de VS Code Instaladas (Relevantes para AURA)

### Python & Data Science
- `ms-python.python` - Soporte completo para Python
- `ms-python.vscode-pylance` - Análisis de código avanzado
- `ms-python.black-formatter` - Formateador de código
- `ms-toolsai.jupyter` - Soporte para Jupyter Notebooks
- `continue.continue` - IA para autocompletado de código
- `saoudrizwan.claude-dev` - Integración con Claude AI

### C# & Unity
- `ms-dotnettools.csharp` - Soporte para C#
- `ms-dotnettools.csdevkit` - Kit de desarrollo C#
- `vscjava.vscode-java-pack` - Paquete completo para Java

### GDScript (Godot)
- **Recomendación:** Instalar `geequlim.gdscript` para soporte completo

### Frontend & Web
- `ritwickdey.liveserver` - Servidor local para desarrollo web
- `esbenp.prettier-vscode` - Formateador de código
- `dbaeumer.vscode-eslint` - Linter para JavaScript/TypeScript
- `redhat.java` - Soporte para Java
- `golang.go` - Soporte para Go

### DevOps & Containers
- `ms-azuretools.vscode-docker` - Soporte para Docker
- `ms-vscode-remote.remote-containers` - Desarrollo en contenedores
- `rangav.vscode-thunder-client` - Cliente HTTP para testing de APIs

### Utilidades
- `eamodio.gitlens` - Superpoderes para Git
- `gruntfuggly.todo-tree` - Gestión de TODOs en el código
- `streetsidesoftware.code-spell-checker` - Corrector ortográfico
- `usernamehw.errorlens` - Mejor visualización de errores

---

## 🎯 Recomendaciones para Integración AURA

### 1. Compilación Android
- Buscar ruta manual de Android Studio para compilación de APKs
- Configurar variables de entorno para ADB y Android SDK

### 2. Desarrollo 3D
- Instalar Godot Engine para interfaces tácticas 3D
- Considerar Unity para experiencias inmersivas avanzadas

### 3. Extensiones Recomendadas (por instalar)
```bash
# GDScript para Godot
code --install-extension geequlim.gdscript

# Mejor soporte para TypeScript/React
code --install-extension dsznajder.es7-react-js-snippets

# Soporte para GDScript
code --install-extension geequlim.gdscript

# Temas y productividad
code --install-extension PKief.material-icon-theme
```

---

## 📝 Notas de Uso

1. **Antes de proponer soluciones:** Leer este archivo para recordar herramientas disponibles
2. **Compilación Android:** Usar Android Studio si está instalado para generar APKs
3. **Interfaces 3D:** Godot/Unity pueden usarse para crear interfaces tácticas inmersivas
4. **Backend:** Java 21 disponible para servicios Android y herramientas JVM

---

## 🔄 Actualizaciones Requeridas
- [ ] Verificar instalaciones manuales de Godot/Unity/Android Studio
- [ ] Documentar rutas completas cuando se encuentren
- [ ] Instalar extensiones recomendadas para VS Code