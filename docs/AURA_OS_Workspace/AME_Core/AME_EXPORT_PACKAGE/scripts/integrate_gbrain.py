#!/usr/bin/env python3
"""
Script de integración entre Obsidian y GBrain
Este script sincroniza la bóveda de conocimiento con el motor GBrain
y asegura la consistencia entre la interfaz visual (Obsidian) y el backend semántico (GBrain).
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import sqlite3
import hashlib
import shutil
import subprocess
import sys
from gbrain_orchestrator import GBrainOrchestrator

class GBrainIntegrator:
    """
    Clase para integrar la bóveda de Obsidian con el motor GBrain.
    """

    def __init__(self, vault_path: str, config_path: str = "TERMUX_AGENT/config/gbrain_config.json"):
        """
        Inicializa el integrador GBrain.

        Args:
            vault_path: Ruta a la bóveda de conocimiento (AURA_INTELLIGENCE_VAULT)
            config_path: Ruta al archivo de configuración
        """
        self.vault_path = Path(vault_path)
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.orchestrator = GBrainOrchestrator(vault_path, config_path)
        self.logger = self._setup_logger()

        # Verificar que la bóveda exista
        if not self.vault_path.exists():
            raise FileNotFoundError(f"La bóveda de conocimiento no existe en: {self.vault_path}")

        # Verificar que la estructura de GBrain exista
        self._verify_gbrain_structure()

    def _load_config(self) -> Dict:
        """Carga la configuración de integración."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Archivo de configuración no encontrado: {self.config_path}")

        with open(self.config_path, 'r') as f:
            return json.load(f)

    def _setup_logger(self) -> logging.Logger:
        """Configura el logger para la integración."""
        logger = logging.getLogger('GBrainIntegrator')
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
        log_file = log_dir / f"integration_{datetime.now().strftime('%Y%m%d')}.log"

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        return logger

    def _verify_gbrain_structure(self):
        """Verifica que la estructura de GBrain exista y esté completa."""
        required_dirs = [
            self.vault_path / "04_Memory_Index",
            self.vault_path / "04_Memory_Index" / "logs",
            self.vault_path / "04_Memory_Index" / "metrics"
        ]

        for directory in required_dirs:
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Creado directorio: {directory}")

        # Verificar archivos de configuración
        required_files = [
            self.vault_path / "04_Memory_Index" / "index.json",
            self.vault_path / "04_Memory_Index" / "metadata.json"
        ]

        for file_path in required_files:
            if not file_path.exists():
                with open(file_path, 'w') as f:
                    json.dump({}, f)
                self.logger.info(f"Creado archivo: {file_path}")

    def _copy_vault_to_gbrain(self):
        """Copia los archivos de la bóveda original a la bóveda GBrain."""
        source_vault = Path("AME_EXPORT_PACKAGE/AURA_OBSIDIAN_VAULT")
        target_vault = self.vault_path

        # Verificar que la bóveda original exista
        if not source_vault.exists():
            raise FileNotFoundError(f"Bóveda original no encontrada en: {source_vault}")

        # Copiar estructura de directorios
        for root, dirs, files in os.walk(source_vault):
            relative_path = root.replace(str(source_vault), "")
            target_root = target_vault / relative_path.lstrip('/')

            # Crear directorios en la bóveda GBrain
            if not target_root.exists():
                target_root.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Creado directorio: {target_root}")

            # Copiar archivos
            for file in files:
                source_file = Path(root) / file
                target_file = target_root / file

                if not target_file.exists():
                    shutil.copy2(source_file, target_file)
                    self.logger.info(f"Copiado archivo: {target_file}")

    def _initialize_gbrain(self):
        """Inicializa el motor GBrain con los datos de la bóveda."""
        self.logger.info("Inicializando motor GBrain...")

        # Copiar bóveda original a la bóveda GBrain
        self._copy_vault_to_gbrain()

        # Procesar la bóveda para crear los índices y grafos
        self.orchestrator.process_vault()

        # Ejecutar ciclo de sueño para optimizar
        from gbrain_dream import GBrainDreamCycle
        dream_cycle = GBrainDreamCycle(self.vault_path, self.config_path)
        dream_cycle.run()

        self.logger.info("Motor GBrain inicializado con éxito")

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
        """Instala las dependencias requeridas para GBrain."""
        required_packages = self.config.get('dependencies', {}).get('required_packages', [])

        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *required_packages])
            self.logger.info(f"Dependencias instaladas: {', '.join(required_packages)}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error al instalar dependencias: {str(e)}")
            return False

    def _check_obsidian_compatibility(self):
        """Verifica la compatibilidad con la versión de Obsidian."""
        obsidian_version = self.config.get('compatibility', {}).get('obsidian_version', '>=1.0.0')
        min_disk_space = self.config.get('compatibility', {}).get('minimum_disk_space_mb', 500)

        # Verificar espacio en disco
        free_space = shutil.disk_usage(self.vault_path.parent).free / (1024 * 1024)  # MB

        if free_space < min_disk_space:
            self.logger.warning(f"Espacio en disco insuficiente. Se requiere al menos {min_disk_space}MB, pero hay {free_space:.2f}MB disponibles.")

        return True  # Simplificado: en producción verificaríamos la versión de Obsidian

    def integrate(self, force: bool = False):
        """
        Ejecuta la integración completa entre Obsidian y GBrain.

        Args:
            force: Si True, fuerza la reintegración completa (ignora caché)
        """
        self.logger.info("Iniciando integración entre Obsidian y GBrain")

        # Verificar dependencias
        if not self._verify_dependencies():
            self.logger.info("Instalando dependencias faltantes...")
            if not self._install_dependencies():
                raise RuntimeError("No se pudieron instalar las dependencias requeridas")

        # Verificar compatibilidad
        if not self._check_obsidian_compatibility():
            raise RuntimeError("Requisitos de compatibilidad no cumplidos")

        # Verificar si ya existe integración
        if not force and self._integration_exists():
            self.logger.info("Integración ya existe. Usando actualización incremental.")
            self._update_integration()
        else:
            self.logger.info("Realizando integración completa...")
            self._initialize_gbrain()

        self.logger.info("Integración completada con éxito")

    def _integration_exists(self) -> bool:
        """Verifica si ya existe una integración previa."""
        # Verificar si existen las bases de datos de GBrain
        vector_db_exists = self.orchestrator.vector_db_path.exists()
        graph_db_exists = self.orchestrator.graph_db_path.exists()
        index_exists = self.orchestrator.index_path.exists()

        return vector_db_exists and graph_db_exists and index_exists

    def _update_integration(self):
        """Actualiza la integración existente."""
        self.logger.info("Actualizando integración existente...")

        # Procesar solo archivos modificados
        self.orchestrator.process_vault()

        # Reparar enlaces rotos
        self.orchestrator.repair_broken_links()

        # Optimizar bases de datos
        self.orchestrator._optimize_databases()

        self.logger.info("Actualización de integración completada")

    def get_integration_status(self) -> Dict:
        """Obtiene el estado actual de la integración."""
        return {
            'status': 'integrated' if self._integration_exists() else 'not_integrated',
            'files_processed': len(self.orchestrator.file_index),
            'nodes_in_graph': self.orchestrator.graph.number_of_nodes(),
            'edges_in_graph': self.orchestrator.graph.number_of_edges(),
            'vault_size_mb': self._get_vault_size_mb(),
            'last_integration': self._get_last_integration_time(),
            'gbrain_version': self.config.get('version', '1.0.0'),
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

    def _get_last_integration_time(self) -> Optional[str]:
        """Obtiene la fecha de la última integración."""
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

    def search_knowledge(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Realiza una búsqueda semántica en la bóveda de conocimiento integrada.

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

    def update_config(self, new_config: Dict):
        """
        Actualiza la configuración de integración.

        Args:
            new_config: Nuevo diccionario de configuración
        """
        self.config.update(new_config)

        # Guardar configuración actualizada
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

        self.logger.info("Configuración actualizada con éxito")

if __name__ == "__main__":
    # Ejemplo de uso
    integrator = GBrainIntegrator(
        vault_path="AME_EXPORT_PACKAGE/AURA_INTELLIGENCE_VAULT",
        config_path="AME_EXPORT_PACKAGE/TERMUX_AGENT/config/gbrain_config.json"
    )

    print("Estado actual de la integración:")
    print(json.dumps(integrator.get_integration_status(), indent=2))

    # Ejecutar integración (comentar para producción)
    # print("\nEjecutando integración...")
    # integrator.integrate(force=True)

    # Ejemplo de búsqueda
    # results = integrator.search_knowledge("¿Cómo funciona el módulo Nmap Avanzado?", top_k=3)
    # print("\nResultados de búsqueda:")
    # for result in results:
    #     print(f"\nResultado (similaridad: {result['similarity']:.2f}):")
    #     print(f"Archivo: {result['title']} ({result['path']})")
    #     print(f"Contenido: {result['content'][:200]}...")

    # Ejemplo de obtención de archivos relacionados
    # if results:
    #     related = integrator.get_related_files(results[0]['file_id'])
    #     print("\nArchivos relacionados:")
    #     for rel in related:
    #         print(f"- {rel['title']} (peso: {rel['weight']:.2f})")