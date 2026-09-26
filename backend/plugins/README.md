# AURA OS — Plugin System Guide

## Quick Start

1. Copiar `backend/plugins/template/` a `backend/plugins/my-plugin/`
2. Editar `plugin.yaml` con nombre, comandos y dependencias
3. Implementar `PluginAgent` en `agent.py`
4. Registrar comandos en el constructor
5. Cargar con `aura plugins load my-plugin`

## Structure

```
backend/plugins/my-plugin/
  plugin.yaml          # Metadata y configuracion
  agent.py             # Implementacion PluginAgent
```

## Plugin YAML Schema

- `name`: Nombre unico del plugin
- `version`: Version semantica
- `author`: Autor
- `description`: Descripcion breve
- `commands`: Lista de comandos con nombre, params y async
- `dependencies`: Lista de dependencias pip
- `capabilities`: Tags funcionales
- `settings`: Configuracion por defecto

## Agent Implementation

```python
from backend.plugins.plugin_template import PluginAgent

class PluginAgent(PluginAgent):
    def __init__(self):
        super().__init__()
        self.name = "mi-plugin"
        self.commands = {"mi-cmd": self.mi_cmd}

    async def mi_cmd(self, args):
        return {"result": "ok"}
```

## CLI Commands

- `aura plugins load {name}`
- `aura plugins unload {name}`
- `aura plugins list`
- `aura plugins reload`
- `aura agents list`
- `aura stats`
- `aura health`
