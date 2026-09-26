#!/usr/bin/env python3
"""
AURA Development Bridge - Puente de desarrollo para Godot y Unity
Permite lanzar comandos de compilación y ejecución desde la consola de VS Code

Parte del sistema AURA-OS
"""

import os
import sys
import subprocess
import platform
import psutil
import time
import json
import logging
from pathlib import Path
from typing import Dict, Optional, List, Tuple

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dev_bridge.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('AURADevBridge')

class DevBridge:
    """Puente de desarrollo para Godot y Unity"""

    def __init__(self):
        self.system_context = self._load_system_context()
        self.engine_paths = self._detect_engine_paths()
        self.projects = self._discover_projects()

    def _load_system_context(self) -> Dict:
        """Carga el contexto del sistema desde AURA_SYSTEM_CONTEXT.md"""
        context_path = Path(__file__).parent.parent / 'AURA_SYSTEM_CONTEXT.md'

        if not context_path.exists():
            logger.warning(f"Archivo de contexto no encontrado: {context_path}")
            return {}

        try:
            with open(context_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parsear información relevante
            context = {
                'godot_path': None,
                'unity_path': None,
                'godot_projects': [],
                'unity_projects': []
            }

            # Buscar rutas de Godot y Unity
            if 'Godot' in content:
                godot_match = self._extract_path_from_content(content, 'Godot')
                if godot_match:
                    context['godot_path'] = godot_match

            if 'Unity' in content:
                unity_match = self._extract_path_from_content(content, 'Unity')
                if unity_match:
                    context['unity_path'] = unity_match

            return context
        except Exception as e:
            logger.error(f"Error cargando contexto del sistema: {str(e)}")
            return {}

    def _extract_path_from_content(self, content: str, engine_name: str) -> Optional[str]:
        """Extrae la ruta de un motor de desarrollo del contenido"""
        import re
        pattern = rf"{engine_name}.*?:\s*([^\n]+)"
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _detect_engine_paths(self) -> Dict:
        """Detecta rutas de Godot y Unity en el sistema"""
        paths = {
            'godot': None,
            'unity': None,
            'unity_hub': None
        }

        # Detectar Godot
        if sys.platform == 'win32':
            possible_paths = [
                r'C:\Program Files\Godot\Godot.exe',
                r'C:\Program Files (x86)\Godot\Godot.exe',
                os.path.join(os.getenv('LOCALAPPDATA'), 'Godot', 'Godot.exe')
            ]
        else:
            possible_paths = [
                '/Applications/Godot.app/Contents/MacOS/Godot',
                '/usr/bin/godot'
            ]

        for path in possible_paths:
            if os.path.exists(path):
                paths['godot'] = path
                break

        # Detectar Unity
        if sys.platform == 'win32':
            possible_paths = [
                r'C:\Program Files\Unity\Hub\Editor\*.exe',
                r'C:\Program Files (x86)\Unity\Hub\Editor\*.exe',
                os.path.join(os.getenv('LOCALAPPDATA'), 'Unity', 'Hub', 'Editor', '*.exe')
            ]
        else:
            possible_paths = [
                '/Applications/Unity/Hub/Editor/*.app',
                '/usr/local/Unity/Hub/Editor/*.app'
            ]

        for path_pattern in possible_paths:
            if sys.platform == 'win32':
                for root, _, files in os.walk(path_pattern.replace('*.exe', '')):
                    for file in files:
                        if file.endswith('.exe'):
                            paths['unity'] = os.path.join(root, file)
                            break
                    if paths['unity']:
                        break
            else:
                # Para macOS, buscar aplicaciones
                if os.path.exists(path_pattern):
                    paths['unity'] = path_pattern
                    break

        # Detectar Unity Hub
        if sys.platform == 'win32':
            hub_path = os.path.join(os.getenv('LOCALAPPDATA'), 'Unity', 'Hub')
            if os.path.exists(hub_path):
                paths['unity_hub'] = hub_path

        return paths

    def _discover_projects(self) -> Dict:
        """Descubre proyectos de Godot y Unity en el sistema"""
        projects = {
            'godot': [],
            'unity': []
        }

        # Buscar proyectos de Godot
        if self.engine_paths['godot']:
            # Buscar directorios con project.godot
            for root, _, files in os.walk(Path.home()):
                if 'project.godot' in files:
                    project_path = Path(root)
                    projects['godot'].append({
                        'path': str(project_path),
                        'name': project_path.name
                    })

        # Buscar proyectos de Unity
        if self.engine_paths['unity_hub']:
            # Buscar directorios con Assets y .unity
            for root, dirs, files in os.walk(Path.home()):
                if 'Assets' in dirs and any(f.endswith('.unity') for f in files):
                    project_path = Path(root)
                    projects['unity'].append({
                        'path': str(project_path),
                        'name': project_path.name
                    })

        return projects

    def _get_godot_executable(self) -> Optional[str]:
        """Obtiene la ruta del ejecutable de Godot"""
        if self.engine_paths['godot']:
            return self.engine_paths['godot']

        # Intentar detectar Godot en PATH
        if sys.platform == 'win32':
            for path in os.getenv('PATH', '').split(os.pathsep):
                exe_path = os.path.join(path, 'Godot.exe')
                if os.path.exists(exe_path):
                    return exe_path
        else:
            for path in os.getenv('PATH', '').split(os.pathsep):
                if os.path.exists(os.path.join(path, 'godot')):
                    return os.path.join(path, 'godot')

        return None

    def _get_unity_executable(self) -> Optional[str]:
        """Obtiene la ruta del ejecutable de Unity"""
        if self.engine_paths['unity']:
            return self.engine_paths['unity']

        # Intentar detectar Unity en PATH
        if sys.platform == 'win32':
            for path in os.getenv('PATH', '').split(os.pathsep):
                exe_path = os.path.join(path, 'Unity.exe')
                if os.path.exists(exe_path):
                    return exe_path
        else:
            # Para macOS, buscar aplicaciones
            unity_apps = [
                '/Applications/Unity/Hub/Editor/Unity.app/Contents/MacOS/Unity',
                '/Applications/Unity Hub/Editor/Unity.app/Contents/MacOS/Unity'
            ]
            for app_path in unity_apps:
                if os.path.exists(app_path):
                    return app_path

        return None

    def launch_godot(self, project_path: Optional[str] = None, editor: bool = True) -> bool:
        """
        Lanza Godot con un proyecto específico
        :param project_path: Ruta al proyecto Godot (project.godot)
        :param editor: Si True, lanza el editor; si False, lanza el ejecutable
        :return: True si se lanzó correctamente, False en caso de error
        """
        godot_exe = self._get_godot_executable()
        if not godot_exe:
            logger.error("No se encontró Godot en el sistema")
            return False

        try:
            if project_path and os.path.exists(project_path):
                # Lanzar Godot con proyecto específico
                if sys.platform == 'win32':
                    command = [godot_exe, '--path', project_path]
                else:
                    command = [godot_exe, '--path', project_path]

                if editor:
                    command.append('--editor')
            else:
                # Lanzar Godot sin proyecto (editor vacío)
                command = [godot_exe]

            logger.info(f"🚀 Lanzando Godot: {'con proyecto' if project_path else 'editor vacío'}")
            logger.info(f"Comando: {' '.join(command)}")

            # Lanzar proceso
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=sys.platform != 'win32'
            )

            # Esperar un momento para verificar que se lanzó
            time.sleep(2)

            # Verificar que el proceso está activo
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] == 'godot.exe' or 'Godot' in proc.info['name']:
                        logger.info(f"✅ Godot lanzado correctamente (PID: {proc.info['pid']})")
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            logger.error("❌ No se pudo verificar que Godot se lanzó correctamente")
            return False

        except Exception as e:
            logger.error(f"Error lanzando Godot: {str(e)}")
            return False

    def launch_unity(self, project_path: Optional[str] = None) -> bool:
        """
        Lanza Unity con un proyecto específico
        :param project_path: Ruta al proyecto Unity (directorio con Assets)
        :return: True si se lanzó correctamente, False en caso de error
        """
        unity_exe = self._get_unity_executable()
        if not unity_exe:
            logger.error("No se encontró Unity en el sistema")
            return False

        try:
            if project_path and os.path.exists(project_path):
                # Lanzar Unity con proyecto específico
                if sys.platform == 'win32':
                    command = [unity_exe, '-projectPath', project_path]
                else:
                    command = [unity_exe, '-projectPath', project_path]

                logger.info(f"🚀 Lanzando Unity: {'con proyecto' if project_path else 'editor vacío'}")
                logger.info(f"Comando: {' '.join(command)}")

                # Lanzar proceso
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=sys.platform != 'win32'
                )

                # Esperar un momento para verificar que se lanzó
                time.sleep(3)

                # Verificar que el proceso está activo
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if proc.info['name'] == 'Unity.exe' or 'Unity' in proc.info['name']:
                            logger.info(f"✅ Unity lanzado correctamente (PID: {proc.info['pid']})")
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                logger.error("❌ No se pudo verificar que Unity se lanzó correctamente")
                return False

            else:
                logger.error("No se proporcionó una ruta de proyecto válida para Unity")
                return False

        except Exception as e:
            logger.error(f"Error lanzando Unity: {str(e)}")
            return False

    def compile_godot_project(self, project_path: str, export_path: str, platform: str = 'Windows') -> bool:
        """
        Compila un proyecto de Godot para una plataforma específica
        :param project_path: Ruta al proyecto Godot (directorio con project.godot)
        :param export_path: Ruta de destino para la compilación
        :param platform: Plataforma de destino (Windows, Linux, macOS)
        :return: True si la compilación fue exitosa, False en caso de error
        """
        godot_exe = self._get_godot_executable()
        if not godot_exe:
            logger.error("No se encontró Godot en el sistema")
            return False

        if not os.path.exists(project_path):
            logger.error(f"Proyecto de Godot no encontrado: {project_path}")
            return False

        try:
            # Verificar que existe project.godot
            project_file = os.path.join(project_path, 'project.godot')
            if not os.path.exists(project_file):
                logger.error(f"No se encontró project.godot en: {project_path}")
                return False

            # Configurar parámetros de compilación
            if sys.platform == 'win32':
                if platform.lower() == 'windows':
                    export_template = 'Windows Desktop'
                elif platform.lower() == 'linux':
                    export_template = 'Linux/X11'
                elif platform.lower() == 'macos':
                    export_template = 'macOS'
                else:
                    logger.error(f"Plataforma no soportada para Godot: {platform}")
                    return False

                command = [
                    godot_exe,
                    '--path', project_path,
                    '--export', export_template,
                    '--export-path', export_path
                ]
            else:
                # Para macOS/Linux, usar parámetros diferentes
                command = [
                    godot_exe,
                    '--path', project_path,
                    '--export', platform.lower(),
                    '--export-path', export_path
                ]

            logger.info(f"🔧 Compilando proyecto Godot para {platform}")
            logger.info(f"Comando: {' '.join(command)}")

            # Ejecutar compilación
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=sys.platform != 'win32'
            )

            if result.returncode == 0:
                logger.info("✅ Compilación exitosa")
                return True
            else:
                logger.error(f"❌ Error en compilación: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error compilando proyecto Godot: {str(e)}")
            return False

    def compile_unity_project(self, project_path: str, build_path: str, platform: str = 'StandaloneWindows64') -> bool:
        """
        Compila un proyecto de Unity para una plataforma específica
        :param project_path: Ruta al proyecto Unity (directorio con Assets)
        :param build_path: Ruta de destino para la compilación
        :param platform: Plataforma de destino (StandaloneWindows64, etc.)
        :return: True si la compilación fue exitosa, False en caso de error
        """
        unity_exe = self._get_unity_executable()
        if not unity_exe:
            logger.error("No se encontró Unity en el sistema")
            return False

        if not os.path.exists(project_path):
            logger.error(f"Proyecto de Unity no encontrado: {project_path}")
            return False

        try:
            # Verificar que existe Assets
            assets_path = os.path.join(project_path, 'Assets')
            if not os.path.exists(assets_path):
                logger.error(f"No se encontró Assets en: {project_path}")
                return False

            # Configurar parámetros de compilación
            if sys.platform == 'win32':
                command = [
                    unity_exe,
                    '-batchmode',
                    '-projectPath', project_path,
                    '-executeMethod', 'BuildPipeline.BuildPlayer',
                    '-buildTarget', platform,
                    '-buildPath', build_path
                ]
            else:
                # Para macOS, usar parámetros diferentes
                command = [
                    unity_exe,
                    '-batchmode',
                    '-projectPath', project_path,
                    '-executeMethod', 'BuildPipeline.BuildPlayer',
                    '-buildTarget', platform,
                    '-buildPath', build_path
                ]

            logger.info(f"🔧 Compilando proyecto Unity para {platform}")
            logger.info(f"Comando: {' '.join(command)}")

            # Ejecutar compilación
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=sys.platform != 'win32'
            )

            if result.returncode == 0:
                logger.info("✅ Compilación exitosa")
                return True
            else:
                logger.error(f"❌ Error en compilación: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error compilando proyecto Unity: {str(e)}")
            return False

    def get_system_status(self) -> Dict:
        """Obtiene el estado del sistema de desarrollo"""
        return {
            'engines': {
                'godot': {
                    'installed': bool(self._get_godot_executable()),
                    'path': self._get_godot_executable(),
                    'projects': len(self.projects['godot'])
                },
                'unity': {
                    'installed': bool(self._get_unity_executable()),
                    'path': self._get_unity_executable(),
                    'projects': len(self.projects['unity'])
                }
            },
            'projects': {
                'godot': self.projects['godot'],
                'unity': self.projects['unity']
            },
            'system_context': self.system_context
        }

    def run_test(self):
        """Ejecuta pruebas de lanzamiento de Godot y Unity"""
        logger.info("🧪 Iniciando pruebas de lanzamiento de motores de desarrollo...")

        # Probar Godot
        godot_success = self.launch_godot()
        logger.info(f"🎮 Prueba de Godot: {'✅ Éxito' if godot_success else '❌ Fallo'}")

        # Probar Unity (si está instalado)
        unity_success = False
        if self._get_unity_executable():
            unity_success = self.launch_unity()
            logger.info(f"🎮 Prueba de Unity: {'✅ Éxito' if unity_success else '❌ Fallo (no instalado)'}")
        else:
            logger.info("🎮 Prueba de Unity: ❌ No instalado")

        # Mostrar estado del sistema
        status = self.get_system_status()
        logger.info("\n📊 Estado del sistema de desarrollo:")
        logger.info(f"  Godot instalado: {'✅' if status['engines']['godot']['installed'] else '❌'}")
        logger.info(f"  Unity instalado: {'✅' if status['engines']['unity']['installed'] else '❌'}")
        logger.info(f"  Proyectos Godot: {status['engines']['godot']['projects']}")
        logger.info(f"  Proyectos Unity: {status['engines']['unity']['projects']}")

        return {
            'godot': godot_success,
            'unity': unity_success,
            'status': status
        }

def main():
    """Punto de entrada principal"""
    bridge = DevBridge()

    # Modo de prueba
    if os.getenv('TEST_MODE') == 'true':
        logger.info("🧪 Modo de prueba activado")
        results = bridge.run_test()

        # Guardar resultados en JSON
        with open('dev_bridge_test_results.json', 'w') as f:
            json.dump(results, f, indent=2)

        logger.info("📝 Resultados guardados en dev_bridge_test_results.json")
        return

    # Modo interactivo
    print("AURA Development Bridge - Menú Principal")
    print("1. Lanzar Godot")
    print("2. Lanzar Unity")
    print("3. Compilar proyecto Godot")
    print("4. Compilar proyecto Unity")
    print("5. Ver estado del sistema")
    print("6. Ejecutar pruebas")
    print("0. Salir")

    choice = input("Seleccione una opción: ")

    if choice == '1':
        # Lanzar Godot
        project_path = input("Ruta al proyecto Godot (dejar vacío para editor vacío): ")
        editor = input("¿Lanzar editor? (s/n): ").lower() == 's'
        success = bridge.launch_godot(project_path if project_path else None, editor)
        print(f"Resultado: {'✅ Éxito' if success else '❌ Fallo'}")

    elif choice == '2':
        # Lanzar Unity
        project_path = input("Ruta al proyecto Unity (directorio con Assets): ")
        success = bridge.launch_unity(project_path if project_path else None)
        print(f"Resultado: {'✅ Éxito' if success else '❌ Fallo'}")

    elif choice == '3':
        # Compilar proyecto Godot
        project_path = input("Ruta al proyecto Godot: ")
        export_path = input("Ruta de exportación: ")
        platform = input("Plataforma (Windows/Linux/macOS): ").lower()
        success = bridge.compile_godot_project(project_path, export_path, platform)
        print(f"Resultado: {'✅ Éxito' if success else '❌ Fallo'}")

    elif choice == '4':
        # Compilar proyecto Unity
        project_path = input("Ruta al proyecto Unity: ")
        build_path = input("Ruta de compilación: ")
        platform = input("Plataforma (StandaloneWindows64, etc.): ")
        success = bridge.compile_unity_project(project_path, build_path, platform)
        print(f"Resultado: {'✅ Éxito' if success else '❌ Fallo'}")

    elif choice == '5':
        # Ver estado del sistema
        status = bridge.get_system_status()
        print(json.dumps(status, indent=2))

    elif choice == '6':
        # Ejecutar pruebas
        results = bridge.run_test()
        print(json.dumps(results, indent=2))

    elif choice == '0':
        print("Saliendo...")
    else:
        print("Opción no válida")

if __name__ == "__main__":
    main()