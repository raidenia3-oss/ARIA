"""Tool Registry — Registro de herramientas 20+"""

from typing import Dict, List


class ToolRegistry:
    """Registro de herramientas disponibles"""

    def __init__(self):
        self.tools = {
            'search': {'description': 'Búsqueda web', 'available': True},
            'calculator': {'description': 'Calculadora', 'available': True},
            'timer': {'description': 'Temporizador', 'available': True},
            'file_read': {'description': 'Leer archivos', 'available': True},
            'file_write': {'description': 'Escribir archivos', 'available': True},
            'file_list': {'description': 'Listar archivos', 'available': True},
            'weather': {'description': 'Clima', 'available': True},
            'news': {'description': 'Noticias', 'available': True},
            'translate': {'description': 'Traducción', 'available': True},
            'calendar': {'description': 'Calendario', 'available': True},
            'email': {'description': 'Email', 'available': True},
            'notes': {'description': 'Notas', 'available': True},
            'music': {'description': 'Música', 'available': True},
            'system_info': {'description': 'Info del sistema', 'available': True},
            'process_manager': {'description': 'Gestor de procesos', 'available': True},
            'network': {'description': 'Red', 'available': True},
            'usb': {'description': 'USB', 'available': True},
            'memory': {'description': 'Memoria', 'available': True},
            'voice': {'description': 'Voz', 'available': True},
            'vision': {'description': 'Visión', 'available': True},
        }

    def list_tools(self) -> List[str]:
        return list(self.tools.keys())

    def get_tool(self, name: str) -> Dict:
        return self.tools.get(name, {})

    def is_available(self, name: str) -> bool:
        return self.tools.get(name, {}).get('available', False)
