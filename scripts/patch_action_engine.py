import re
p = 'backend/services/action_engine.py'
with open(p, 'r', encoding='utf-8') as f:
    text = f.read()
marker = '''        self.register_tool(ToolDefinition(
            name="open_url",
            description="Abre una URL en el navegador predeterminado del sistema.",
            parameters={
                "properties": {
                    "url": {"type": "string", "description": "URL a abrir."},
                },
                "required": ["url"],
            },
            risk_level=ActionRiskLevel.LOW,
            requires_confirmation=False,
            category="web",
        ))'''
if marker not in text:
    raise SystemExit('marker not found')
insert = '''        self.register_tool(ToolDefinition(
            name="browser.open",
            description="Abre una URL en el navegador del sistema (alias de open_url).",
            parameters={
                "properties": {
                    "url": {"type": "string", "description": "URL a abrir."},
                },
                "required": ["url"],
            },
            risk_level=ActionRiskLevel.LOW,
            requires_confirmation=False,
            category="browser",
        ))
        self.register_tool(ToolDefinition(
            name="browser.search",
            description="Busca en Internet y devuelve resultados web.",
            parameters={
                "properties": {
                    "query": {"type": "string", "description": "Consulta de búsqueda."},
                },
                "required": ["query"],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="browser",
        ))
        self.register_tool(ToolDefinition(
            name="browser.read",
            description="Lee el contenido textual de una página web.",
            parameters={
                "properties": {
                    "url": {"type": "string", "description": "URL a leer."},
                },
                "required": ["url"],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="browser",
        }))
        self.register_tool(ToolDefinition(
            name="browser.screenshot",
            description="Captura la pantalla actual (requiere pyautogui).",
            parameters={
                "properties": {},
                "required": [],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="browser",
        }))
        self.register_tool(ToolDefinition(
            name="browser.wait",
            description="Espera N segundos durante una automatización.",
            parameters={
                "properties": {
                    "seconds": {"type": "number", "description": "Segundos a esperar.", "default": 1},
                },
                "required": [],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="browser",
        }))
        self.register_tool(ToolDefinition(
            name="files.list",
            description="Alias de list_directory.",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "Ruta del directorio.", "default": "."},
                },
                "required": ["path"],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="filesystem",
        ))
        self.register_tool(ToolDefinition(
            name="files.read",
            description="Alias de read_file.",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "Ruta del archivo."},
                    "limit": {"type": "integer", "description": "Límite de caracteres.", "default": 4000},
                },
                "required": ["path"],
            },
            risk_level=ActionRiskLevel.LOW,
            requires_confirmation=False,
            category="filesystem",
        }))
        self.register_tool(ToolDefinition(
            name="files.write",
            description="Alias de write_file.",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "Ruta del archivo."},
                    "content": {"type": "string", "description": "Contenido a escribir."},
                    "mode": {"type": "string", "description": "Modo de escritura.", "default": "w"},
                },
                "required": ["path", "content"],
            },
            risk_level=ActionRiskLevel.HIGH,
            requires_confirmation=True,
            category="filesystem",
        }))
        self.register_tool(ToolDefinition(
            name="files.move",
            description="Mueve un archivo o directorio a otra ruta.",
            parameters={
                "properties": {
                    "src": {"type": "string", "description": "Ruta origen."},
                    "dst": {"type": "string", "description": "Ruta destino."},
                },
                "required": ["src", "dst"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="filesystem",
        }))
        self.register_tool(ToolDefinition(
            name="files.organize",
            description="Organiza archivos por extensión en subcarpetas.",
            parameters={
                "properties": {
                    "path": {"type": "string", "description": "Directorio a organizar.", "default": "."},
                },
                "required": ["path"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="filesystem",
        }))
        self.register_tool(ToolDefinition(
            name="system.status",
            description="Devuelve estado básico de la PC (CPU, RAM, disco).",
            parameters={
                "properties": {},
                "required": [],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="system",
        }))
        self.register_tool(ToolDefinition(
            name="system.apps",
            description="Lista procesos activos del sistema.",
            parameters={
                "properties": {
                    "limit": {"type": "integer", "description": "Límite de resultados.", "default": 20},
                },
                "required": [],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="system",
        }))
        self.register_tool(ToolDefinition(
            name="system.open",
            description="Alias de launch_app.",
            parameters={
                "properties": {
                    "app": {"type": "string", "description": "Nombre o ruta del ejecutable."},
                    "args": {"type": "array", "items": {"type": "string"}, "description": "Argumentos opcionales."},
                },
                "required": ["app"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="system",
        }))
        self.register_tool(ToolDefinition(
            name="system.screenshot",
            description="Captura la pantalla actual (requiere pyautogui).",
            parameters={
                "properties": {},
                "required": [],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="system",
        }))
        self.register_tool(ToolDefinition(
            name="automation.create",
            description="Crea una automatización aprendida a partir de pasos.",
            parameters={
                "properties": {
                    "name": {"type": "string", "description": "Nombre de la automatización."},
                    "goal": {"type": "string", "description": "Objetivo de la automatización."},
                    "steps": {"type": "array", "description": "Lista de pasos."},
                },
                "required": ["name", "goal", "steps"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="automation",
        }))
        self.register_tool(ToolDefinition(
            name="automation.run",
            description="Ejecuta una automatización aprendida por ID.",
            parameters={
                "properties": {
                    "procedure_id": {"type": "string", "description": "ID de la automatización."},
                },
                "required": ["procedure_id"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="automation",
        }))
        self.register_tool(ToolDefinition(
            name="automation.cancel",
            description="Cancela una automatización en ejecución por ID de tarea.",
            parameters={
                "properties": {
                    "task_id": {"type": "string", "description": "ID de la tarea."},
                },
                "required": ["task_id"],
            },
            risk_level=ActionRiskLevel.MEDIUM,
            requires_confirmation=True,
            category="automation",
        }))
        self.register_tool(ToolDefinition(
            name="memory.remember",
            description="Guarda un recuerdo en la memoria de AURA.",
            parameters={
                "properties": {
                    "text": {"type": "string", "description": "Texto a recordar."},
                    "type": {"type": "string", "description": "Tipo de memoria.", "default": "episodic"},
                    "source": {"type": "string", "description": "Fuente.", "default": "user"},
                },
                "required": ["text"],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="memory",
        }))
        self.register_tool(ToolDefinition(
            name="memory.search",
            description="Busca en la memoria de AURA.",
            parameters={
                "properties": {
                    "query": {"type": "string", "description": "Consulta de búsqueda."},
                    "limit": {"type": "integer", "description": "Límite de resultados.", "default": 5},
                },
                "required": ["query"],
            },
            risk_level=ActionRiskLevel.SAFE,
            requires_confirmation=False,
            category="memory",
        }))
'''
text = text.replace(marker, marker + insert)
with open(p, 'w', encoding='utf-8') as f:
    f.write(text)
print('inserted')
