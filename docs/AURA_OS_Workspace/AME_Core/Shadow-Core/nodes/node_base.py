"""
Base para los nodos tácticos del ecosistema AURA/AME.
Define la clase abstracta TacticalNode que todos los nodos deben heredar.
"""

import abc
import importlib
import inspect
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TacticalNode")

class TacticalNode(abc.ABC):
    """
    Clase base abstracta para todos los nodos tácticos.
    Todos los nodos deben heredar de esta clase y implementar los métodos abstractos.
    """

    def __init__(self):
        self.node_id = self.__class__.__name__
        self.version = "1.0.0"
        self.status = "inactive"
        self._initialized = False
        self._terminated = False
        self._execution_log = []

    @abc.abstractmethod
    def initialize(self, config: Optional[Dict] = None) -> bool:
        """
        Inicializa el nodo con configuración opcional.
        Debe ser implementado por cada nodo táctico.
        """
        pass

    @abc.abstractmethod
    def execute(self, input_data: Dict) -> Dict:
        """
        Ejecuta el nodo con los datos de entrada proporcionados.
        Debe ser implementado por cada nodo táctico.
        """
        pass

    def terminate(self) -> bool:
        """
        Limpia recursos y termina la ejecución del nodo.
        """
        self._terminated = True
        self.status = "terminated"
        logger.info(f"🛑 Nodo {self.node_id} terminado correctamente")
        return True

    def get_info(self) -> Dict:
        """
        Devuelve información del nodo.
        """
        return {
            'node_id': self.node_id,
            'version': self.version,
            'status': self.status,
            'description': self.__class__.__doc__ or "Nodo táctico sin descripción",
            'initialized': self._initialized,
            'terminated': self._terminated,
            'execution_log': self._execution_log,
            'timestamp': datetime.now().isoformat()
        }

    def log_execution(self, message: str, level: str = "info") -> None:
        """
        Registra eventos de ejecución en el log del nodo.
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'level': level,
            'node_id': self.node_id
        }
        self._execution_log.append(log_entry)

        # Registrar también en el logger principal
        if level == "info":
            logger.info(f"[{self.node_id}] {message}")
        elif level == "warning":
            logger.warning(f"[{self.node_id}] {message}")
        elif level == "error":
            logger.error(f"[{self.node_id}] {message}")
        else:
            logger.debug(f"[{self.node_id}] {message}")

    def validate_input(self, input_data: Dict) -> bool:
        """
        Valida la entrada del nodo según su estructura esperada.
        Método base que puede ser sobrescrito por nodos específicos.
        """
        if not isinstance(input_data, dict):
            self.log_execution("Entrada no es un diccionario", "error")
            return False

        required_fields = self.get_required_input_fields()
        for field in required_fields:
            if field not in input_data:
                self.log_execution(f"Campo requerido faltante: {field}", "error")
                return False

        return True

    def get_required_input_fields(self) -> list:
        """
        Devuelve los campos requeridos para la entrada del nodo.
        Debe ser implementado por cada nodo táctico.
        """
        return []

    def get_output_structure(self) -> Dict:
        """
        Devuelve la estructura esperada de la salida del nodo.
        Debe ser implementado por cada nodo táctico.
        """
        return {}

class NodeRegistry:
    """
    Registro dinámico de nodos tácticos.
    Escanea automáticamente la carpeta Nodes/ al inicializarse.
    """

    def __init__(self, nodes_path: str = "Shadow-Core/Nodes"):
        self.nodes_path = nodes_path
        self._nodes = {}
        self._loaded = False
        self._scan_nodes()

    def _scan_nodes(self) -> None:
        """
        Escanea la carpeta de nodos y registra todos los módulos válidos.
        """
        if not os.path.exists(self.nodes_path):
            logger.warning(f"📂 Carpeta de nodos no encontrada: {self.nodes_path}")
            return

        logger.info(f"🔍 Escaneando carpeta de nodos: {self.nodes_path}")

        for filename in os.listdir(self.nodes_path):
            if filename.endswith(".py") and not filename.startswith("node_base"):
                module_name = filename[:-3]  # Quitar la extensión .py
                try:
                    module = importlib.import_module(f"Shadow-Core.Nodes.{module_name}")

                    # Buscar clases que hereden de TacticalNode
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and
                            issubclass(obj, TacticalNode) and
                            obj != TacticalNode):
                            node_class = obj()
                            self._nodes[module_name] = {
                                'class': obj,
                                'instance': node_class,
                                'module': module
                            }
                            logger.info(f"🎯 Nodo registrado: {module_name} ({obj.__name__})")

                except Exception as e:
                    logger.error(f"❌ Error al cargar módulo {module_name}: {e}")

        self._loaded = True
        logger.info(f"✅ Cargados {len(self._nodes)} nodos tácticos")

    def get_node(self, node_id: str) -> Optional[TacticalNode]:
        """
        Obtiene una instancia de un nodo por su ID.
        """
        if not self._loaded:
            self._scan_nodes()

        if node_id not in self._nodes:
            logger.error(f"❌ Nodo no encontrado: {node_id}")
            return None

        # Crear una nueva instancia del nodo
        node_class = self._nodes[node_id]['class']
        node_instance = node_class()

        # Inicializar el nodo
        if not node_instance.initialize():
            logger.error(f"❌ Error al inicializar nodo {node_id}")
            return None

        return node_instance

    def list_nodes(self) -> Dict:
        """
        Lista todos los nodos disponibles.
        """
        if not self._loaded:
            self._scan_nodes()

        return {
            'nodes': list(self._nodes.keys()),
            'total': len(self._nodes),
            'timestamp': datetime.now().isoformat()
        }

    def execute_node(self, node_id: str, input_data: Dict) -> Dict:
        """
        Ejecuta un nodo específico con los datos de entrada proporcionados.
        """
        node = self.get_node(node_id)
        if not node:
            return {
                'status': 'node_not_found',
                'error': f'Nodo {node_id} no encontrado',
                'timestamp': datetime.now().isoformat()
            }

        try:
            result = node.execute(input_data)
            return {
                'status': 'success',
                'node_id': node_id,
                'result': result,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Error al ejecutar nodo {node_id}: {e}")
            return {
                'status': 'execution_error',
                'node_id': node_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
        finally:
            node.terminate()

# Instancia global del registro de nodos
node_registry = NodeRegistry()