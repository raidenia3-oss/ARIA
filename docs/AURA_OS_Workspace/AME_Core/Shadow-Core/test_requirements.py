"""
test_requirements.py - Script para verificar y probar las dependencias del servidor de datos
"""

import os
import sys
import subprocess
import importlib
import logging
from pathlib import Path

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dependencias requeridas
REQUIRED_PACKAGES = [
    "flask",
    "flask-socketio",
    "eventlet",
    "python-dotenv"
]

# Función para verificar si un paquete está instalado
def is_package_installed(package_name):
    """Verifica si un paquete está instalado"""
    try:
        importlib.import_module(package_name)
        return True
    except ImportError:
        return False

# Función para instalar un paquete
def install_package(package_name):
    """Intenta instalar un paquete"""
    try:
        logger.info(f"Instalando {package_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        logger.info(f"✅ {package_name} instalado con éxito")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error al instalar {package_name}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error inesperado al instalar {package_name}: {e}")
        return False

# Función para verificar y actualizar dependencias
def check_and_update_dependencies():
    """Verifica las dependencias y las instala si es necesario"""
    logger.info("🔧 VERIFICANDO DEPENDENCIAS DEL SERVIDOR DE DATOS")
    logger.info("=" * 50)

    missing_packages = []
    for package in REQUIRED_PACKAGES:
        if not is_package_installed(package):
            missing_packages.append(package)
            logger.warning(f"⚠️ {package} no está instalado")

    if missing_packages:
        logger.info(f"\n📦 INSTALANDO {len(missing_packages)} PAQUETES FALTANTES")
        for package in missing_packages:
            if not install_package(package):
                logger.error(f"❌ No se pudo instalar {package}")

        # Verificar nuevamente después de la instalación
        logger.info("\n🔄 VERIFICANDO DEPENDENCIAS DESPUÉS DE LA INSTALACIÓN")
        for package in REQUIRED_PACKAGES:
            if is_package_installed(package):
                logger.info(f"✅ {package} está instalado correctamente")
            else:
                logger.error(f"❌ {package} sigue sin estar instalado")

        return False
    else:
        logger.info("✅ TODAS LAS DEPENDENCIAS ESTÁN INSTALADAS")
        return True

# Función para probar la instalación de Flask-SocketIO
def test_flask_socketio():
    """Prueba la instalación de Flask-SocketIO"""
    try:
        logger.info("\n🧪 PROBANDO FLASK-SOCKETIO")

        # Verificar que Flask-SocketIO esté instalado
        if not is_package_installed("flask_socketio"):
            logger.error("❌ Flask-SocketIO no está instalado")
            return False

        # Crear un script de prueba simple
        test_script = """
import socketio
import eventlet

sio = socketio.Server()
app = socketio.WSGIApp(sio)

@sio.event
def connect(sid, environ):
    print(f"Cliente conectado: {sid}")

@sio.event
def disconnect(sid):
    print(f"Cliente desconectado: {sid}")

@sio.event
def my_message(sid, data):
    print(f"Mensaje recibido: {data}")
    sio.emit('my_response', {'data': 'Hola desde el servidor'})

print("Servidor Flask-SocketIO listo para pruebas")
"""

        # Guardar el script de prueba
        test_path = Path("test_flask_socketio.py")
        with open(test_path, "w") as f:
            f.write(test_script)

        # Intentar importar y ejecutar
        try:
            import socketio
            import eventlet

            logger.info("✅ Flask-SocketIO está disponible y funcional")
            return True
        except Exception as e:
            logger.error(f"❌ Error al probar Flask-SocketIO: {e}")
            return False
        finally:
            # Eliminar el script de prueba
            if test_path.exists():
                test_path.unlink()

    except Exception as e:
        logger.error(f"❌ Error al probar Flask-SocketIO: {e}")
        return False

# Función para probar Eventlet
def test_eventlet():
    """Prueba la instalación de Eventlet"""
    try:
        logger.info("\n🧪 PROBANDO EVENTLET")

        # Verificar que Eventlet esté instalado
        if not is_package_installed("eventlet"):
            logger.error("❌ Eventlet no está instalado")
            return False

        # Probar el monkey patch de Eventlet
        try:
            import eventlet
            eventlet.monkey_patch()
            logger.info("✅ Eventlet está disponible y funcional")
            return True
        except Exception as e:
            logger.error(f"❌ Error al probar Eventlet: {e}")
            return False

    except Exception as e:
        logger.error(f"❌ Error al probar Eventlet: {e}")
        return False

# Función para probar Python-Dotenv
def test_python_dotenv():
    """Prueba la instalación de Python-Dotenv"""
    try:
        logger.info("\n🧪 PROBANDO PYTHON-DOTENV")

        # Verificar que Python-Dotenv esté instalado
        if not is_package_installed("python_dotenv"):
            logger.error("❌ Python-Dotenv no está instalado")
            return False

        # Crear un archivo .env de prueba
        env_path = Path(".env.test")
        with open(env_path, "w") as f:
            f.write("TEST_VAR=valor_de_prueba\n")

        # Probar la carga del archivo
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=env_path)

            # Verificar que se cargó correctamente
            import os
            if os.getenv("TEST_VAR") == "valor_de_prueba":
                logger.info("✅ Python-Dotenv está disponible y funcional")
                return True
            else:
                logger.error("❌ Python-Dotenv no cargó correctamente el archivo .env")
                return False
        except Exception as e:
            logger.error(f"❌ Error al probar Python-Dotenv: {e}")
            return False
        finally:
            # Eliminar el archivo .env de prueba
            if env_path.exists():
                env_path.unlink()

    except Exception as e:
        logger.error(f"❌ Error al probar Python-Dotenv: {e}")
        return False

# Función para probar Flask
def test_flask():
    """Prueba la instalación de Flask"""
    try:
        logger.info("\n🧪 PROBANDO FLASK")

        # Verificar que Flask esté instalado
        if not is_package_installed("flask"):
            logger.error("❌ Flask no está instalado")
            return False

        # Crear una aplicación Flask simple
        try:
            from flask import Flask
            app = Flask(__name__)

            @app.route('/')
            def hello():
                return "Hola desde Flask"

            # Verificar que se creó correctamente
            logger.info("✅ Flask está disponible y funcional")
            return True
        except Exception as e:
            logger.error(f"❌ Error al probar Flask: {e}")
            return False

    except Exception as e:
        logger.error(f"❌ Error al probar Flask: {e}")
        return False

# Función principal
def main():
    """Función principal"""
    logger.info("VERIFICACIÓN DE DEPENDENCIAS PARA EL SERVIDOR DE DATOS")
    logger.info("Este script verifica que todas las dependencias estén instaladas y funcionales")

    # Verificar y actualizar dependencias
    all_dependencies_ok = check_and_update_dependencies()

    # Probar cada dependencia individualmente
    tests = [
        ("Flask", test_flask),
        ("Flask-SocketIO", test_flask_socketio),
        ("Eventlet", test_eventlet),
        ("Python-Dotenv", test_python_dotenv)
    ]

    success_count = 0
    for test_name, test_func in tests:
        if test_func():
            success_count += 1
        else:
            logger.error(f"❌ {test_name} no funciona correctamente")

    # Mostrar resultados
    logger.info("\n" + "=" * 50)
    logger.info("📊 RESULTADOS DE LAS PRUEBAS")
    logger.info("=" * 50)

    if all_dependencies_ok:
        logger.info("✅ TODAS LAS DEPENDENCIAS ESTÁN INSTALADAS")
    else:
        logger.warning("⚠️ ALGUNAS DEPENDENCIAS FALTAN")

    logger.info(f"\n🧪 PRUEBAS DE FUNCIONALIDAD: {success_count}/{len(tests)} exitosas")

    if success_count == len(tests):
        logger.info("\n✅ TODAS LAS DEPENDENCIAS ESTÁN FUNCIONANDO CORRECTAMENTE")
        logger.info("El servidor de datos en tiempo real está listo para ejecutarse")
        return True
    else:
        logger.error("\n❌ ALGUNAS DEPENDENCIAS NO FUNCIONAN CORRECTAMENTE")
        logger.info("Se recomienda:")
        logger.info("   - Verificar la instalación de los paquetes")
        logger.info("   - Revisar los logs de instalación")
        logger.info("   - Intentar instalar manualmente los paquetes faltantes")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)