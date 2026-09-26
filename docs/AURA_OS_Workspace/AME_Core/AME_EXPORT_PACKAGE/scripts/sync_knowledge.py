#!/usr/bin/env python3
"""
Script de sincronización de conocimiento entre Obsidian y GBrain
Este script sincroniza cambios en la bóveda de conocimiento con el motor GBrain,
asegurando que los índices semánticos y el grafo relacional estén actualizados.
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import hashlib
import shutil
import subprocess
import sys
import watchdog.events
import watchdog.observers
from watchdog.observers import Observer
from gbrain_orchestrator import GBrainOrchestrator

class KnowledgeSyncObserver(watchdog.events.PatternMatchingEventHandler):
    """
    Observador para detectar cambios en la bóveda de conocimiento.
    """

    def __init__(self, integrator, patterns=None, ignore_patterns=None, ignore_directories=False):
        super().__init__(patterns=patterns, ignore_patterns=ignore_patterns, ignore_directories=ignore_directories)
        self.integrator = integrator
        self.logger = logging.getLogger('KnowledgeSyncObserver')

    def on_modified(self, event):
        """Maneja eventos de modificación de archivos."""
        if not event.is_directory:
            self.logger.info(f"Detectado cambio en archivo: {event.src_path}")
            self._handle_file_change(event.src_path)

    def on_created(self, event):
        """Maneja eventos de creación de archivos."""
        if not event.is_directory:
            self.logger.info(f"Detectado archivo nuevo: {event.src_path}")
            self._handle_file_change(event.src_path)

    def on_deleted(self, event):
        """Maneja eventos de eliminación de archivos."""
        if not event.is_directory:
            self.logger.info(f"Detectado archivo eliminado: {event.src_path}")
            self._handle_file_change(event.src_path)

    def _handle_file_change(self, file_path: str):
        """Maneja un cambio en un archivo específico."""
        try:
            # Verificar si es un archivo Markdown
            if file_path.endswith('.md'):
                self.logger.info(f"Sincronizando cambios en: {file_path}")

                # Obtener el integrador de GBrain
                orchestrator = self.integrator.orchestrator

                # Procesar solo el archivo modificado
                chunks = orchestrator._process_file(Path(file_path))

                # Actualizar el grafo de conocimiento
                orchestrator.process_vault()

                # Ejecutar optimización ligera
                orchestrator._optimize_databases()

                self.logger.info(f"Sincronización completada para: {file_path}")

        except Exception as e:
            self.logger.error(f"Error al sincronizar cambios en {file_path}: {str(e)}")

class KnowledgeSynchronizer:
    """
    Clase para sincronizar la bóveda de conocimiento con el motor GBrain.
    """

    def __init__(self, vault_path: str, config_path: str = "TERMUX_AGENT/config/gbrain_config.json"):
        """
        Inicializa el sincronizador de conocimiento.

        Args:
            vault_path: Ruta a la bóveda de conocimiento (AURA_INTELLIGENCE_VAULT)
            config_path: Ruta al archivo de configuración
        """
        self.vault_path = Path(vault_path)
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.orchestrator = GBrainOrchestrator(vault_path, config_path)
        self.logger = self._setup_logger()
        self.observer = None

        # Verificar que la bóveda exista
        if not self.vault_path.exists():
            raise FileNotFoundError(f"La bóveda de conocimiento no existe en: {self.vault_path}")

    def _load_config(self) -> Dict:
        """Carga la configuración de sincronización."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Archivo de configuración no encontrado: {self.config_path}")

        with open(self.config_path, 'r') as f:
            return json.load(f)

    def _setup_logger(self) -> logging.Logger:
        """Configura el logger para la sincronización."""
        logger = logging.getLogger('KnowledgeSynchronizer')
        logger.setLevel(self.config.get('logging', {}).get('level', 'INFO'))

        # Formateador
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Manejo de logs a consola
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Manejo de logs a archivo
        log_dir = self.vault_path / "04_Memory_Index" / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"sync_{datetime.now().strftime('%Y%m%d')}.log"

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        return logger

    def _verify_dependencies(self):
        """Verifica que todas las dependencias requeridas estén instaladas."""
        required_packages = self.config.get('dependencies', {}).get('required_packages', [])

        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)

        if missing_packages:
            self.logger.error(f"Dependencias faltantes: {', '.join(missing_packages)}")
            return False

        return True

    def _install_dependencies(self):
        """Instala las dependencias requeridas para la sincronización."""
        required_packages = self.config.get('dependencies', {}).get('required_packages', [])

        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *required_packages])
            self.logger.info(f"Dependencias instaladas: {', '.join(required_packages)}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error al instalar dependencias: {str(e)}")
            return False

    def _check_integration_status(self) -> bool:
        """Verifica que la integración con GBrain exista."""
        return self.orchestrator._integration_exists()

    def _initialize_integration(self):
        """Inicializa la integración con GBrain si no existe."""
        from integrate_gbrain import GBrainIntegrator
        integrator = GBrainIntegrator(self.vault_path, self.config_path)
        integrator.integrate(force=True)

    def _get_sync_config(self) -> Dict:
        """Obtiene la configuración específica de sincronización."""
        return self.config.get('sync', {
            'enabled': True,
            'auto_sync': True,
            'watch_interval': 5.0,  # segundos
            'max_changes_buffer': 100,
            'sync_on_start': True,
            'sync_threshold': 0.1,  # Umbral de cambios para sincronización
            'patterns': ["*.md"],
            'ignore_patterns': ["*.tmp", "*.log", "temp_*"],
            'ignore_directories': False
        })

    def _get_changed_files(self, since_time: Optional[datetime] = None) -> List[Path]:
        """
        Obtiene los archivos modificados desde una fecha específica.

        Args:
            since_time: Fecha desde la cual buscar cambios (None para todos los archivos)

        Returns:
            Lista de archivos modificados
        """
        changed_files = []

        for root, _, files in os.walk(self.vault_path):
            for file in files:
                if file.endswith('.md'):
                    file_path = Path(root) / file

                    # Verificar si el archivo ha sido modificado desde la fecha especificada
                    if since_time:
                        mod_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if mod_time > since_time:
                            changed_files.append(file_path)
                    else:
                        changed_files.append(file_path)

        return changed_files

    def _calculate_change_metrics(self) -> Dict:
        """Calcula métricas de cambios en la bóveda."""
        metrics = {
            'total_files': 0,
            'modified_files': 0,
            'new_files': 0,
            'deleted_files': 0,
            'last_sync': None,
            'changes_since_last_sync': 0
        }

        # Obtener la última fecha de sincronización
        if self.orchestrator.index_path.exists():
            last_sync_time = datetime.fromtimestamp(self.orchestrator.index_path.stat().st_mtime)
            metrics['last_sync'] = last_sync_time.isoformat()

            # Calcular cambios desde la última sincronización
            metrics['changes_since_last_sync'] = len(self._get_changed_files(last_sync_time))

        # Contar archivos totales
        metrics['total_files'] = len(self._get_changed_files())

        return metrics

    def _sync_files(self, file_paths: List[Path]):
        """Sincroniza archivos específicos con GBrain."""
        self.logger.info(f"Sincronizando {len(file_paths)} archivos con GBrain...")

        for file_path in file_paths:
            try:
                self.logger.info(f"Procesando archivo: {file_path}")
                chunks = self.orchestrator._process_file(file_path)

                # Actualizar el grafo de conocimiento
                self.orchestrator.process_vault()

                # Optimizar bases de datos
                self.orchestrator._optimize_databases()

                self.logger.info(f"Sincronización completada para: {file_path}")

            except Exception as e:
                self.logger.error(f"Error al sincronizar {file_path}: {str(e)}")

    def _full_sync(self):
        """Realiza una sincronización completa de la bóveda."""
        self.logger.info("Iniciando sincronización completa...")

        # Obtener todos los archivos Markdown
        all_files = self._get_changed_files()

        # Sincronizar todos los archivos
        self._sync_files(all_files)

        self.logger.info("Sincronización completa finalizada")

    def _incremental_sync(self, since_time: Optional[datetime] = None):
        """Realiza una sincronización incremental desde una fecha específica."""
        self.logger.info("Iniciando sincronización incremental...")

        # Obtener archivos modificados desde la fecha especificada
        changed_files = self._get_changed_files(since_time)

        if not changed_files:
            self.logger.info("No se detectaron cambios desde la última sincronización")
            return

        # Sincronizar solo los archivos modificados
        self._sync_files(changed_files)

        self.logger.info(f"Sincronización incremental finalizada (procesados {len(changed_files)} archivos)")

    def _start_watchdog(self):
        """Inicia el observador de cambios en la bóveda."""
        sync_config = self._get_sync_config()

        if not sync_config.get('auto_sync', True):
            self.logger.info("La sincronización automática está deshabilitada")
            return

        # Crear observador
        event_handler = KnowledgeSyncObserver(self, patterns=sync_config.get('patterns', ["*.md"]),
                                             ignore_patterns=sync_config.get('ignore_patterns', []),
                                             ignore_directories=sync_config.get('ignore_directories', False))

        # Crear observador de watchdog
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.vault_path), recursive=True)
        self.observer.start()

        self.logger.info(f"Observador de cambios iniciado. Escaneando cada {sync_config.get('watch_interval', 5.0)} segundos...")

    def _stop_watchdog(self):
        """Detiene el observador de cambios."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.logger.info("Observador de cambios detenido")

    def sync(self, force_full: bool = False):
        """
        Ejecuta la sincronización de conocimiento.

        Args:
            force_full: Si True, fuerza una sincronización completa (ignora cambios incrementales)
        """
        self.logger.info("Iniciando sincronización de conocimiento")

        # Verificar dependencias
        if not self._verify_dependencies():
            self.logger.info("Instalando dependencias faltantes...")
            if not self._install_dependencies():
                raise RuntimeError("No se pudieron instalar las dependencias requeridas")

        # Verificar integración con GBrain
        if not self._check_integration_status():
            self.logger.info("Integración con GBrain no encontrada. Inicializando...")
            self._initialize_integration()

        # Obtener métricas de cambios
        metrics = self._calculate_change_metrics()
        self.logger.info(f"Métricas de cambios: {json.dumps(metrics, indent=2)}")

        # Decidir qué tipo de sincronización realizar
        if force_full or metrics.get('changes_since_last_sync', 0) > 10:
            self.logger.info("Realizando sincronización completa (demasiados cambios)")
            self._full_sync()
        else:
            self.logger.info("Realizando sincronización incremental")
            self._incremental_sync(metrics.get('last_sync') and datetime.fromisoformat(metrics['last_sync']))

        self.logger.info("Sincronización completada con éxito")

    def run_continuous(self, interval: float = 5.0):
        """
        Ejecuta la sincronización en modo continuo con verificación periódica.

        Args:
            interval: Intervalo en segundos para verificar cambios
        """
        self.logger.info(f"Iniciando sincronización continua (intervalo: {interval} segundos)")

        # Iniciar observador de cambios
        self._start_watchdog()

        # Bucle principal
        try:
            while True:
                try:
                    # Verificar si hay cambios significativos
                    metrics = self._calculate_change_metrics()
                    changes = metrics.get('changes_since_last_sync', 0)

                    if changes > 0:
                        self.logger.info(f"Detectados {changes} cambios. Iniciando sincronización...")
                        self.sync(force_full=changes > 10)

                    # Esperar hasta el próximo intervalo
                    time.sleep(interval)

                except KeyboardInterrupt:
                    self.logger.info("Deteniendo sincronización continua...")
                    break
                except Exception as e:
                    self.logger.error(f"Error en sincronización continua: {str(e)}", exc_info=True)
                    time.sleep(interval)

        finally:
            # Detener observador al finalizar
            self._stop_watchdog()

    def get_sync_status(self) -> Dict:
        """Obtiene el estado actual de la sincronización."""
        return {
            'status': 'active',
            'integration_status': 'integrated' if self._check_integration_status() else 'not_integrated',
            'files_processed': len(self.orchestrator.file_index),
            'nodes_in_graph': self.orchestrator.graph.number_of_nodes(),
            'edges_in_graph': self.orchestrator.graph.number_of_edges(),
            'vault_size_mb': self._get_vault_size_mb(),
            'last_sync': self._get_last_sync_time(),
            'sync_config': self._get_sync_config(),
            'metrics': self._calculate_change_metrics(),
            'dependencies': {
                'installed': self._verify_dependencies(),
                'missing': [] if self._verify_dependencies() else self._get_missing_dependencies()
            }
        }

    def _get_vault_size_mb(self) -> float:
        """Obtiene el tamaño aproximado de la bóveda en MB."""
        total_size = 0

        for root, _, files in os.walk(self.vault_path):
            for file in files:
                if file.endswith(('.md', '.db', '.json')):
                    file_path = Path(root) / file
                    total_size += file_path.stat().st_size

        return total_size / (1024 * 1024)  # Convertir a MB

    def _get_last_sync_time(self) -> Optional[str]:
        """Obtiene la fecha de la última sincronización."""
        if not self.orchestrator.index_path.exists():
            return None

        try:
            stat = self.orchestrator.index_path.stat()
            return datetime.fromtimestamp(stat.st_mtime).isoformat()
        except Exception:
            return None

    def _get_missing_dependencies(self) -> List[str]:
        """Obtiene la lista de dependencias faltantes."""
        required_packages = self.config.get('dependencies', {}).get('required_packages', [])
        missing_packages = []

        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)

        return missing_packages

    def update_config(self, new_config: Dict):
        """
        Actualiza la configuración de sincronización.

        Args:
            new_config: Nuevo diccionario de configuración
        """
        self.config.update(new_config)

        # Guardar configuración actualizada
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

        self.logger.info("Configuración actualizada con éxito")

    def search_knowledge(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Realiza una búsqueda semántica en la bóveda de conocimiento sincronizada.

        Args:
            query: Consulta de búsqueda
            top_k: Número de resultados a devolver

        Returns:
            Lista de resultados ordenados por relevancia
        """
        return self.orchestrator.search(query, top_k)

    def get_related_files(self, file_id: str, top_k: int = 3) -> List[Dict]:
        """
        Obtiene archivos relacionados con un archivo específico basado en el grafo.

        Args:
            file_id: ID del archivo de referencia
            top_k: Número de archivos relacionados a devolver

        Returns:
            Lista de archivos relacionados ordenados por relevancia
        """
        return self.orchestrator.get_related_files(file_id, top_k)

    def get_knowledge_graph(self) -> Dict:
        """
        Obtiene el grafo de conocimiento completo en formato JSON.

        Returns:
            Representación del grafo de conocimiento
        """
        return self.orchestrator.get_knowledge_graph()

    def run_dream_cycle(self):
        """
        Ejecuta un ciclo de sueño de GBrain para mantener la base de conocimiento.
        """
        from gbrain_dream import GBrainDreamCycle
        dream_cycle = GBrainDreamCycle(self.vault_path, self.config_path)
        return dream_cycle.run()

if __name__ == "__main__":
    # Ejemplo de uso
    synchronizer = KnowledgeSynchronizer(
        vault_path="AME_EXPORT_PACKAGE/AURA_INTELLIGENCE_VAULT",
        config_path="AME_EXPORT_PACKAGE/TERMUX_AGENT/config/gbrain_config.json"
    )

    print("Estado actual de la sincronización:")
    print(json.dumps(synchronizer.get_sync_status(), indent=2))

    # Ejecutar sincronización (comentar para producción)
    # print("\nEjecutando sincronización...")
    # synchronizer.sync(force_full=True)

    # Ejemplo de búsqueda
    # results = synchronizer.search_knowledge("¿Cómo funciona el módulo Nmap Avanzado?", top_k=3)
    # print("\nResultados de búsqueda:")
    # for result in results:
    #     print(f"\nResultado (similaridad: {result['similarity']:.2f}):")
    #     print(f"Archivo: {result['title']} ({result['path']})")
    #     print(f"Contenido: {result['content'][:200]}...")

    # Ejemplo de obtención de archivos relacionados
    # if results:
    #     related = synchronizer.get_related_files(results[0]['file_id'])
    #     print("\nArchivos relacionados:")
    #     for rel in related:
    #         print(f"- {rel['title']} (peso: {rel['weight']:.2f})")

    # Para ejecución continua (descomentar para uso en producción):
    # print("\nIniciando sincronización continua (presione Ctrl+C para detener)...")
    # synchronizer.run_continuous(interval=5.0)