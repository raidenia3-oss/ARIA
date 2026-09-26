# Quick Start — ARIA OS v4.0

## Instalación (30 segundos)

```powershell
cd C:\Users\User\Downloads\AURA\ARIA_v4
pip install -r requirements.txt
```

## Activación

Solo di: **Prendete**

```powershell
python AURA_APP/aria_startup.py
```

O usa el auto-fix:

```powershell
python scripts/auto_fix_bundle.py
```

## Comandos principales

| Comando | Acción |
|---------|--------|
| Prendete | Activar ARIA |
| Expande | Expandir capacidades |
| USB | Detectar USB |
| Maximiza | Maximizar todo |
| Aprende | Aprender del contexto |
| ¿Qué hora es? | Consulta |
| Salir | Apagar |

## APIs

```powershell
# Chat
curl -X POST http://localhost:8000/api/aria/chat -d '{"message":"Prendete"}'

# USB
curl http://localhost:8000/api/aria/usb/status

# PStack
curl -X POST http://localhost:8000/api/aria/pstack/potato-mode -d "Necesito expandir"

# Health
curl http://localhost:8000/api/system/health
```

## Verificar sistema

```powershell
python AURA_APP/tests/verify_system.py
```

## Build ejecutable

```powershell
python scripts/build.py
```
