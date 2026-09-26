#!/usr/bin/env python3
"""
GBrain Dream Cycle - Ciclo de sueño para mantenimiento de la base de conocimiento
Integración híbrida Obsidian + GBrain (PG Lite)
"""

import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
import hashlib
import networkx as nx
from gbrain_orchestrator import GBrainOrchestrator

class GBrainDreamCycle:
    """
    Ciclo de sueño para mantenimiento automático de la base de conocimiento GBrain.
    Ejecuta tareas periódicas de mantenimiento, reparación y optimización.
    """

    def __init__(self, vault_path: str, config_path: str = "config/gbrain_config.json"):
        """
        Inicializa el ciclo de sueño de GBrain.

        Args:
            vault_path: Ruta a la bóveda de conocimiento (AURA_INTELLIGENCE_VAULT)
            config_path: Ruta al archivo de configuración
        """
        self.vault_path = Path(vault_path)
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.orchestrator = GBrainOrchestrator(vault_path, config_path)
        self.logger = self._setup_logger()

        # Configuración de horarios
        self.last_run = None
        self.next_run = None
        self._calculate_next_run()

    def _load_config(self) -> Dict:
        """Carga la configuración de GBrain."""
        if not self.config_path.exists():
            return {
                'dream_cycle_interval': 3600,  # 1 hora por defecto
                'repair_threshold': 0.8,       # Umbral para reparación automática
                'optimization_interval': 86400, # 1 día para optimización
                'log_level': 'INFO',
                'max_runtime': 3600,          # Máximo tiempo de ejecución en segundos
                'check_interval': 60          # Intervalo para verificar estado en segundos
            }

        with open(self.config_path, 'r') as f:
            return json.load(f)

    def _setup_logger(self) -> logging.Logger:
        """Configura el logger para el ciclo de sueño."""
        logger = logging.getLogger('GBrainDreamCycle')
        logger.setLevel(self.config.get('log_level', 'INFO'))

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
        log_file = log_dir / f"gbrain_dream_{datetime.now().strftime('%Y%m%d')}.log"

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        return logger

    def _calculate_next_run(self):
        """Calcula el próximo horario de ejecución basado en la configuración."""
        interval = self.config.get('dream_cycle_interval', 3600)
        now = datetime.now()

        if self.last_run:
            # Si ya se ejecutó antes, calcular el próximo horario
            next_run = self.last_run + timedelta(seconds=interval)
            if now > next_run:
                # Si ya pasó el horario, ajustar al próximo ciclo
                next_run = now + timedelta(seconds=interval - (now - self.last_run).seconds)
        else:
            # Primera ejecución, programar para dentro de intervalo
            next_run = now + timedelta(seconds=interval)

        self.next_run = next_run
        self.logger.info(f"Próximo ciclo de sueño programado para: {self.next_run.strftime('%Y-%m-%d %H:%M:%S')}")

    def _should_run(self) -> bool:
        """Verifica si es hora de ejecutar el ciclo de sueño."""
        now = datetime.now()
        return now >= self.next_run

    def _check_runtime(self, start_time: float) -> bool:
        """Verifica si se ha excedido el tiempo máximo de ejecución."""
        max_runtime = self.config.get('max_runtime', 3600)
        current_time = time.time()
        elapsed = current_time - start_time

        if elapsed > max_runtime:
            self.logger.warning(f"Tiempo máximo de ejecución ({max_runtime} segundos) excedido. Deteniendo ciclo de sueño.")
            return False

        return True

    def _log_metrics(self, start_time: float, success: bool):
        """Registra métricas del ciclo de sueño."""
        end_time = time.time()
        elapsed = end_time - start_time

        metrics = {
            'timestamp': datetime.now().isoformat(),
            'success': success,
            'duration_seconds': elapsed,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'files_processed': len(self.orchestrator.file_index),
            'nodes_in_graph': self.orchestrator.graph.number_of_nodes(),
            'edges_in_graph': self.orchestrator.graph.number_of_edges()
        }

        # Guardar métricas en archivo
        metrics_dir = self.vault_path / "04_Memory_Index" / "metrics"
        metrics_dir.mkdir(exist_ok=True)
        metrics_file = metrics_dir / "dream_cycle_metrics.json"

        with open(metrics_file, 'a') as f:
            f.write(json.dumps(metrics) + '\n')

        self.logger.info(f"Métricas del ciclo de sueño: {metrics}")

    def _run_repair_check(self):
        """Verifica si se necesitan reparaciones en los enlaces."""
        self.logger.info("Iniciando verificación de reparación de enlaces...")

        # Escanear bóveda actual
        current_files = {self.orchestrator._generate_file_id(str(f)): f for f in self.orchestrator._scan_vault()}

        # Obtener archivos registrados en el índice
        registered_files = {f['file_id']: f for f in self.orchestrator.file_index.values()}

        # Detectar archivos eliminados
        deleted_files = set(registered_files.keys()) - set(current_files.keys())

        # Detectar archivos nuevos
        new_files = set(current_files.keys()) - set(registered_files.keys())

        repair_needed = False

        if deleted_files:
            self.logger.warning(f"Detectados {len(deleted_files)} archivos eliminados que podrían requerir reparación")
            repair_needed = True

        if new_files:
            self.logger.info(f"Detectados {len(new_files)} archivos nuevos que podrían requerir procesamiento")
            repair_needed = True

        # Verificar integridad del grafo
        try:
            # Intentar reconstruir el grafo para detectar inconsistencias
            self.orchestrator._build_graph()

            # Verificar si hay nodos sin aristas
            isolated_nodes = [n for n, d in self.orchestrator.graph.nodes(data=True) if self.orchestrator.graph.degree(n) == 0]

            if isolated_nodes:
                self.logger.warning(f"Detectados {len(isolated_nodes)} nodos aislados en el grafo")
                repair_needed = True

        except Exception as e:
            self.logger.error(f"Error al verificar integridad del grafo: {str(e)}")
            repair_needed = True

        return repair_needed

    def _run_optimization_check(self) -> bool:
        """Verifica si se necesitan optimizaciones en las bases de datos."""
        self.logger.info("Iniciando verificación de optimización de bases de datos...")

        # Verificar tamaño de las bases de datos
        vector_db_size = os.path.getsize(self.orchestrator.vector_db_path) / (1024 * 1024)  # MB
        graph_db_size = os.path.getsize(self.orchestrator.graph_db_path) / (1024 * 1024)  # MB

        self.logger.debug(f"Tamaño de vector_db: {vector_db_size:.2f} MB")
        self.logger.debug(f"Tamaño de graph_db: {graph_db_size:.2f} MB")

        # Verificar si las bases de datos necesitan optimización
        # (Simplificado: en una implementación real usaríamos métricas más específicas)
        optimization_needed = vector_db_size > 100 or graph_db_size > 100  # Umbral de 100MB

        if optimization_needed:
            self.logger.info("Bases de datos requieren optimización (tamaño excesivo)")
            return True

        return False

    def _run_dream_cycle(self):
        """Ejecuta un ciclo completo de sueño de GBrain."""
        start_time = time.time()
        success = True

        try:
            self.logger.info("Iniciando ciclo de sueño de GBrain")

            # 1. Procesar bóveda para detectar cambios
            self.logger.info("Procesando bóveda de conocimiento...")
            self.orchestrator.process_vault()

            # 2. Reparar enlaces rotos si es necesario
            if self._run_repair_check():
                self.logger.info("Ejecutando reparación de enlaces rotos...")
                self.orchestrator.repair_broken_links()

            # 3. Verificar y ejecutar optimizaciones si es necesario
            if self._run_optimization_check():
                self.logger.info("Ejecutando optimización de bases de datos...")
                self.orchestrator._optimize_databases()

            # 4. Verificar integridad del grafo
            self.logger.info("Verificando integridad del grafo de conocimiento...")
            try:
                self.orchestrator._build_graph()
                self.logger.info(f"Grafo verificado: {self.orchestrator.graph.number_of_nodes()} nodos, {self.orchestrator.graph.number_of_edges()} aristas")
            except Exception as e:
                self.logger.error(f"Error al verificar integridad del grafo: {str(e)}")
                success = False

            # Actualizar última ejecución
            self.last_run = datetime.now()
            self._calculate_next_run()

            self.logger.info("Ciclo de sueño de GBrain completado con éxito")

        except Exception as e:
            self.logger.error(f"Error durante el ciclo de sueño: {str(e)}", exc_info=True)
            success = False

        # Registrar métricas
        self._log_metrics(start_time, success)

        return success

    def run(self):
        """Ejecuta el ciclo de sueño de GBrain."""
        start_time = time.time()

        if not self._should_run():
            self.logger.info("No es hora de ejecutar el ciclo de sueño. Esperando hasta el próximo horario...")
            return False

        # Verificar si el tiempo de ejecución sería excesivo
        if not self._check_runtime(start_time):
            return False

        # Ejecutar el ciclo de sueño
        success = self._run_dream_cycle()

        # Verificar si se excedió el tiempo máximo
        if not self._check_runtime(start_time):
            return False

        return success

    def run_continuous(self, interval: int = 60):
        """
        Ejecuta el ciclo de sueño en modo continuo con verificación periódica.

        Args:
            interval: Intervalo en segundos para verificar estado
        """
        self.logger.info(f"Iniciando modo continuo de ciclo de sueño (intervalo: {interval} segundos)")

        while True:
            try:
                # Verificar si es hora de ejecutar
                if self._should_run():
                    self.run()

                # Esperar hasta el próximo intervalo de verificación
                time.sleep(interval)

            except KeyboardInterrupt:
                self.logger.info("Deteniendo ciclo de sueño continuo...")
                break
            except Exception as e:
                self.logger.error(f"Error en ciclo de sueño continuo: {str(e)}", exc_info=True)
                time.sleep(interval)

    def get_status(self) -> Dict:
        """Obtiene el estado actual del ciclo de sueño."""
        return {
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'should_run': self._should_run(),
            'files_processed': len(self.orchestrator.file_index),
            'nodes_in_graph': self.orchestrator.graph.number_of_nodes(),
            'edges_in_graph': self.orchestrator.graph.number_of_edges(),
            'vault_size_mb': self._get_vault_size_mb(),
            'config': {
                'dream_cycle_interval': self.config.get('dream_cycle_interval', 3600),
                'repair_threshold': self.config.get('repair_threshold', 0.8),
                'optimization_interval': self.config.get('optimization_interval', 86400),
                'max_runtime': self.config.get('max_runtime', 3600)
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

    def update_config(self, new_config: Dict):
        """Actualiza la configuración del ciclo de sueño."""
        self.config.update(new_config)

        # Guardar configuración actualizada
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

        # Recalcular próximo horario de ejecución
        self._calculate_next_run()

        self.logger.info("Configuración actualizada con éxito")

if __name__ == "__main__":
    # Ejemplo de uso
    dream_cycle = GBrainDreamCycle(
        vault_path="AME_EXPORT_PACKAGE/AURA_INTELLIGENCE_VAULT",
        config_path="AME_EXPORT_PACKAGE/TERMUX_AGENT/config/gbrain_config.json"
    )

    # Ejecutar ciclo de sueño manualmente (para pruebas)
    print("Ejecutando ciclo de sueño manualmente...")
    success = dream_cycle.run()

    if success:
        print("Ciclo de sueño completado con éxito")
    else:
        print("Ciclo de sueño falló")

    # Mostrar estado
    print("\nEstado del ciclo de sueño:")
    print(json.dumps(dream_cycle.get_status(), indent=2))

    # Para ejecución continua (descomentar para uso en producción):
    # print("\nIniciando modo continuo (presione Ctrl+C para detener)...")
    # dream_cycle.run_continuous(interval=60)