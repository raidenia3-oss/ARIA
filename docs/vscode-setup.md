# AURA — VS Code Development Setup

Este documento describe cómo configurar AURA como entorno de desarrollo profesional en VS Code.

## Requisitos previos

- VS Code 1.85+
- Docker Desktop + Docker Compose
- Python 3.11+
- Node.js 20+
- Ruby 3.2+ (para Discord bot y DSL compiler)
- Git 2.40+

## Inicio rápido

### 1. Abrir el workspace

```bash
code C:\Users\User\Downloads\AURA
```

O desde terminal:
```bash
cd C:\Users\User\Downloads\AURA
code .
```

### 2. Instalar extensiones recomendadas

VS Code detectará automáticamente `.vscode/extensions.json` y sugerirá instalar las extensiones.

Instalar manualmente si es necesario:
```bash
code --install-extension ms-python.python
code --install-extension rebornix.ruby
code --install-extension dbaeumer.vscode-eslint
code --install-extension esbenp.prettier-vscode
code --install-extension ms-azuretools.vscode-docker
code --install-extension github.copilot
code --install-extension eamodio.gitlens
code --install-extension usernamehw.errorlens
```

### 3. Configurar entorno

Copiar archivos de entorno:
```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
cp services/discord-bot/.env.example services/discord-bot/.env
```

Configurar variables requeridas en cada `.env`.

### 4. Iniciar servicios

Opción A: Docker Compose (recomendado para producción)
```bash
docker-compose up --build
```

Opción B: Desarrollo individual (recomendado para debugging)
```bash
# Terminal 1: Backend
python -m uvicorn ame_backend.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev

# Terminal 3: Discord Bot
cd services/discord-bot && ruby bot.rb

# Terminal 4: HF Space
cd hf-space && python app.py
```

## Configuración de VS Code

### Debugging

El archivo `.vscode/launch.json` incluye configuraciones para:

- **Debug Backend (FastAPI)** — Debug el backend con reload automático
- **Debug Frontend (Next.js)** — Debug el frontend con Chrome/Edge
- **Debug HF Space** — Debug el servicio de inferencia
- **Debug Gesture Control** — Debug el control por gestos
- **Debug Voice Commands** — Debug los comandos de voz
- **Debug Discord Bot** — Debug el bot de Discord
- **Debug DSL Compiler** — Debug el compilador DSL
- **Attach to Backend** — Adjuntar debugger a proceso remoto
- **Attach to Frontend (Node)** — Adjuntar debugger a Node.js

Compounds:
- **Run All Services** — Inicia backend + frontend + hf-space
- **Run Backend + Frontend** — Inicia solo los servicios core

### Tasks

El archivo `.vscode/tasks.json` incluye tareas para:

- Backend: Run Dev Server, Run Tests, Lint & Format Check
- Frontend: Run Dev Server, Build, Type Check, Lint
- Discord Bot: Run, Run Specs
- DSL Compiler: Run Specs
- HF Space: Run Dev
- Docker: Compose Up/Down/Logs
- Load Tests: Run Locust
- AURA: Health Check, Setup Environment

Ejecutar tareas:
- Windows/Linux: `Ctrl+Shift+B` → seleccionar tarea
- Mac: `Cmd+Shift+B` → seleccionar tarea

### Testing

Configuración automática para:
- **Python**: pytest con descubrimiento automático
- **Ruby**: rspec para Discord bot y DSL compiler
- **Load**: Locust para pruebas de carga

Ejecutar tests desde VS Code:
1. Abrir el panel de Testing (`Ctrl+Shift+`` `)
2. Seleccionar el framework
3. Ejecutar tests individuales o suites completas

## Dev Container

Para desarrollo en contenedor aislado:

1. Instalar extensión "Dev Containers"
2. `F1` → "Dev Containers: Reopen in Container"
3. Esperar a que se construya el entorno
4. El contenedor incluye: Python, Ruby, Node.js, Docker, VS Code Server

Puertos forward automáticos:
- 8000 → Backend
- 3000 → Frontend
- 7860 → HF Space
- 5432 → PostgreSQL
- 6379 → Redis

## Agentes y Automatización

### Kilo Agent Manager

El proyecto incluye configuración de Kilo Agent Manager en `.kilo/agent-manager.json` para:

- Worktrees aislados por feature
- Sesiones de agente persistentes
- Asignación de tareas automática

Usar desde Kilo:
```bash
# Ver sesiones activas
agent_manager list

# Iniciar nueva sesión de trabajo
agent_manager start --mode worktree --tasks [...]

# Mover sesión a sección
agent_manager move --sessionID ses_xxx --sectionID section_yyy
```

### GitHub Copilot

Configurado para:
- Autocompletado multi-lenguaje (Python, Ruby, TypeScript)
- Chat integrado para debugging
- Sugerencias de código contextuales

### GitLens

- Blame annotations en tiempo real
- Navegación de historial
- Comparación de ramas

### Error Lens

- Errores y warnings inline
- Diagnósticos en tiempo real

## Estructura del proyecto

```
AURA/
├── .vscode/                    # Configuración de VS Code
│   ├── extensions.json         # Extensiones recomendadas
│   ├── launch.json             # Configuraciones de debugging
│   ├── tasks.json              # Tareas automatizadas
│   └── settings.json           # Configuraciones del editor
├── .devcontainer/              # Dev Container config
│   ├── devcontainer.json       # Configuración del contenedor
│   └── post-create.sh          # Script post-creación
├── backend/                    # FastAPI Backend
├── frontend/                   # Next.js Frontend
├── services/
│   ├── discord-bot/            # Ruby Discord Bot
│   ├── gesture-control/        # Python Gesture Control
│   ├── voice-commands/         # Python Voice Commands
│   └── dsl-compiler/           # Ruby DSL Compiler
├── hf-space/                   # Gradio HF Space
├── docker-compose.yml          # Orquestación de servicios
├── requirements.txt            # Dependencias Python
└── README.md                   # Documentación principal
```

## Comandos útiles

### Desarrollo

```bash
# Backend con reload
python -m uvicorn ame_backend.main:app --reload

# Frontend con turbopack
cd frontend && npm run dev

# Tests Python
pytest services/gesture-control/tests services/voice-commands/tests tests/integration tests/unit -v

# Tests Ruby
rspec services/discord-bot/spec services/dsl-compiler/spec --format documentation

# Lint Python
ruff check backend services tests

# Lint Frontend
cd frontend && npx eslint app components lib --ext .ts,.tsx

# Load tests
locust -f tests/load/locustfile.py --host http://localhost:8000
```

### Docker

```bash
# Levantar todos los servicios
docker-compose up --build

# Ver logs
docker-compose logs -f

# Detener servicios
docker-compose down

# Reconstruir un servicio específico
docker-compose up --build backend
```

### Git

```bash
# Crear feature branch
git checkout -b feature/nombre-feature

# Commit con conventional commits
git commit -m "feat(backend): agregar nuevo endpoint"

# Push y crear PR
git push origin feature/nombre-feature
```

## Troubleshooting

### Puerto ocupado

Si el puerto 8000/3000/7860 está ocupado:
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <pid> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

### Problemas con extensiones

Recargar ventana de VS Code:
```
Ctrl+Shift+P → "Developer: Reload Window"
```

### Problemas con Docker

Reiniciar Docker Desktop y verificar que esté corriendo:
```bash
docker info
docker-compose ps
```

## Próximos pasos

1. Configurar variables de entorno en `.env`
2. Ejecutar `docker-compose up --build` o servicios individuales
3. Abrir http://localhost:3000 para ver el frontend
4. Verificar health check en http://localhost:8000/health
5. Explorar las extensiones instaladas y sus funcionalidades
