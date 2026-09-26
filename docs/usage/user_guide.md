# Guía de Usuario AURA

## Inicio rápido

1. Ejecuta `scripts/start_aura_full.bat` (Windows) o `scripts/start_aura_production.bat`
2. Abre http://localhost:3000
3. Escribe un mensaje y presiona Enter

## Chat

- Escribe preguntas o comandos
- Usa los botones 👍/👎 para dar feedback
- El sistema aprende de tus preferencias

## Comandos útiles

- `/chat <mensaje>` en Discord
- `/status` para ver estado del sistema
- `/feedback up|down` para calificar respuestas

## Mantenimiento

- `python scripts/maintenance.py --dry-run` para verificar estado
- `python training/scripts/backup_model.py` para backup local
- `python training/scripts/cloud_backup.py` para backup en la nube

## Soporte

- Documentación: `docs/deployment/`
- Logs: `logs/`
- Reportes: `training/output/`