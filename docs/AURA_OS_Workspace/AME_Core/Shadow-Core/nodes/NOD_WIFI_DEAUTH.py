"""
NODO_WIFI_DEAUTH - Escaneo profundo de puertos abiertos y detección de sistemas operativos.

ESTRUCTURA:
- NODE_ID: NOD_WIFI_DEAUTH
- INPUT_INTERFACE: {'target_ip': str, 'timeout': int, 'ports': list, 'os_detection': bool}
- CORE_LOGIC: Escaneo de puertos con nmap y detección de OS usando técnicas sigilosas
- OUTPUT_INTERFACE: {
    'target': str,
    'status': str,
    'open_ports': list,
    'services': dict,
    'os_detection': {
        'os': str,
        'confidence': float,
        'methods': list
    },
    'timestamp': str,
    'metadata': dict
}
"""

import json
import subprocess
import socket
import re
from datetime import datetime
import platform
import logging
from typing import Dict, List, Optional, Union

# Importar la clase base de nodos tácticos
from Shadow-Core.Nodes.node_base import TacticalNode, logger

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuración del módulo
DEFAULT_TIMEOUT = 30  # segundos
DEFAULT_PORTS = [
    21, 22, 23, 25, 53, 67, 68, 80, 110, 111, 135, 139, 143, 161, 162, 389, 443, 445,
    465, 512, 513, 514, 515, 546, 547, 587, 636, 993, 995, 1024, 1025, 1080, 1433,
    1521, 1723, 1812, 2049, 2082, 2083, 2100, 2103, 2105, 2106, 2222, 27017, 3306,
    3389, 5000, 5432, 5900, 6379, 8000, 8080, 8443, 9000, 9200
]

class NOD_WIFI_DEAUTH(TacticalNode):
    """
    Nodo avanzado para escaneo profundo de puertos y detección de sistemas operativos.
    """

    def __init__(self):
        super().__init__()
        self.node_id = "NOD_WIFI_DEAUTH"
        self.version = "1.0.0"
        self.status = "inactive"
        self._initialized = False

    def validate_input(self, input_data: Dict) -> bool:
        """
        Valida la entrada del nodo según el INPUT_INTERFACE.
        """
        required_fields = ['target_ip']
        for field in required_fields:
            if field not in input_data:
                logger.error(f"❌ Campo requerido faltante: {field}")
                return False

        if not isinstance(input_data.get('target_ip'), str):
            logger.error("❌ target_ip debe ser un string (IP o dominio)")
            return False

        if not input_data.get('timeout', DEFAULT_TIMEOUT) > 0:
            logger.error("❌ timeout debe ser un número positivo")
            return False

        if not input_data.get('ports', DEFAULT_PORTS):
            logger.error("❌ ports no puede estar vacío")
            return False

        return True

    def run_nmap_scan(self, target: str, ports: List[int], timeout: int) -> Dict:
        """
        Ejecuta un escaneo de puertos usando nmap con opciones sigilosas.
        """
        try:
            # Construir comando nmap con opciones sigilosas
            nmap_cmd = [
                'nmap',
                '-Pn',  # No Ping
                '-T4',  # Velocidad rápida
                '--min-rate=1000',  # Paquetes por segundo
                '-sV',  # Detección de versiones
                '--version-intensity=5',  # Intensidad moderada
                '-sC',  # Scripts por defecto (sigilosos)
                '-oG',  # Formato de salida para procesar
                '-'
            ]

            # Añadir puertos específicos
            if isinstance(ports, list) and len(ports) > 0:
                nmap_cmd.extend([f'-p{","}'.join(map(str, ports))])
            else:
                nmap_cmd.append('-p-')  # Escanear todos los puertos

            # Añadir timeout
            nmap_cmd.extend(['--max-retries=1', '--host-timeout', str(timeout)])

            # Ejecutar nmap
            result = subprocess.run(
                nmap_cmd + [target],
                capture_output=True,
                text=True,
                check=True
            )

            # Procesar la salida de nmap
            output = result.stdout
            return self._parse_nmap_output(output, target)

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Error al ejecutar nmap: {e.stderr}")
            return {
                'error': str(e),
                'target': target,
                'status': 'scan_failed'
            }
        except Exception as e:
            logger.error(f"❌ Error inesperado en nmap_scan: {e}")
            return {
                'error': str(e),
                'target': target,
                'status': 'scan_error'
            }

    def _parse_nmap_output(self, output: str, target: str) -> Dict:
        """
        Parsea la salida de nmap en formato de salida normalizada.
        """
        result = {
            'target': target,
            'status': 'success',
            'open_ports': [],
            'services': {},
            'os_detection': {
                'os': 'unknown',
                'confidence': 0.0,
                'methods': []
            },
            'timestamp': datetime.now().isoformat(),
            'metadata': {}
        }

        # Procesar líneas de puertos abiertos
        for line in output.split('\n'):
            if line.startswith('#'):
                continue

            if 'open' in line.lower():
                # Extraer información del puerto
                port_match = re.search(r'(\d+)/(\w+)', line)
                if port_match:
                    port = int(port_match.group(1))
                    protocol = port_match.group(2).upper()

                    # Extraer servicio y versión
                    service_match = re.search(r'(\S+)\s+(\S+)', line.split('open')[1].strip())
                    if service_match:
                        service = service_match.group(1)
                        version = service_match.group(2) if len(service_match.groups()) > 1 else 'unknown'

                        result['open_ports'].append({
                            'port': port,
                            'protocol': protocol,
                            'service': service,
                            'version': version
                        })

                        result['services'][port] = {
                            'service': service,
                            'version': version,
                            'protocol': protocol
                        }

            # Detección de OS (buscar líneas con "OS:")
            if 'OS:' in line:
                os_info = line.split('OS:')[1].strip()
                result['os_detection']['os'] = os_info
                result['os_detection']['methods'].append('nmap_os_detection')

                # Calcular confianza basada en la cantidad de información
                if 'Windows' in os_info or 'Linux' in os_info or 'macOS' in os_info:
                    result['os_detection']['confidence'] = 0.9
                elif 'router' in os_info or 'embedded' in os_info:
                    result['os_detection']['confidence'] = 0.7
                else:
                    result['os_detection']['confidence'] = 0.5

        # Si no se detectó OS, intentar con técnicas adicionales
        if result['os_detection']['os'] == 'unknown':
            result['os_detection']['methods'].append('tcp_stack_fingerprinting')
            result['os_detection']['confidence'] = 0.3

        return result

    def run_os_fingerprinting(self, target: str, ports: List[int] = None) -> Dict:
        """
        Realiza fingerprinting de OS usando técnicas de stack TCP.
        """
        try:
            # Usar hping3 para fingerprinting (requiere instalación)
            hping_cmd = [
                'hping3',
                '-S',  # Paquete SYN
                '-p', '80',  # Puerto común
                '--tcp',  # Modo TCP
                '-c', '1',  # Solo un paquete
                '-V',  # Verbose
                '-o',  # Mostrar flags
                target
            ]

            result = subprocess.run(
                hping_cmd,
                capture_output=True,
                text=True,
                check=True
            )

            # Analizar la salida para detectar patrones de OS
            output = result.stdout
            tcp_flags = re.search(r'flags=(\S+)', output)

            fingerprint = {
                'tcp_flags': tcp_flags.group(1) if tcp_flags else 'unknown',
                'ttl': re.search(r'ttl=(\d+)', output),
                'window_size': re.search(r'win=(\d+)', output)
            }

            # Intentar determinar OS basado en fingerprint
            os_info = self._analyze_tcp_fingerprint(fingerprint)

            return {
                'target': target,
                'status': 'success',
                'os_fingerprint': fingerprint,
                'os_detection': {
                    'os': os_info.get('os', 'unknown'),
                    'confidence': os_info.get('confidence', 0.0),
                    'methods': ['tcp_stack_fingerprinting']
                },
                'timestamp': datetime.now().isoformat()
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Error al ejecutar hping3: {e.stderr}")
            return {
                'error': str(e),
                'target': target,
                'status': 'fingerprint_failed'
            }
        except Exception as e:
            logger.error(f"❌ Error inesperado en os_fingerprinting: {e}")
            return {
                'error': str(e),
                'target': target,
                'status': 'fingerprint_error'
            }

    def _analyze_tcp_fingerprint(self, fingerprint: Dict) -> Dict:
        """
        Analiza el fingerprint TCP para intentar determinar el sistema operativo.
        """
        # Patrones conocidos de sistemas operativos
        os_patterns = {
            'Windows': {
                'tcp_flags': ['SA', 'SAc', 'SAcR'],  # SYN+ACK, SYN+ACK+RST
                'ttl': {'min': 120, 'max': 130},
                'window_size': {'min': 512, 'max': 65535}
            },
            'Linux': {
                'tcp_flags': ['SA', 'SAc'],
                'ttl': {'min': 50, 'max': 70},
                'window_size': {'min': 5840, 'max': 65535}
            },
            'macOS': {
                'tcp_flags': ['SA'],
                'ttl': {'min': 60, 'max': 64},
                'window_size': {'min': 5720, 'max': 65535}
            },
            'Router': {
                'tcp_flags': ['SA'],
                'ttl': {'min': 250, 'max': 255},
                'window_size': {'min': 4096, 'max': 8192}
            },
            'Embedded': {
                'tcp_flags': ['SA'],
                'ttl': {'min': 60, 'max': 100},
                'window_size': {'min': 1024, 'max': 4096}
            }
        }

        # Evaluar cada patrón
        best_match = {'os': 'unknown', 'confidence': 0.0}

        for os_name, pattern in os_patterns.items():
            confidence = 0.0

            # Evaluar flags TCP
            if 'tcp_flags' in pattern and fingerprint.get('tcp_flags') in pattern['tcp_flags']:
                confidence += 0.3

            # Evaluar TTL
            if 'ttl' in pattern and fingerprint.get('ttl'):
                ttl = int(fingerprint['ttl'].group(1))
                if (pattern['ttl']['min'] <= ttl <= pattern['ttl']['max']):
                    confidence += 0.4

            # Evaluar window size
            if 'window_size' in pattern and fingerprint.get('window_size'):
                win_size = int(fingerprint['window_size'].group(1))
                if (pattern['window_size']['min'] <= win_size <= pattern['window_size']['max']):
                    confidence += 0.3

            # Actualizar mejor coincidencia
            if confidence > best_match['confidence']:
                best_match = {
                    'os': os_name,
                    'confidence': confidence,
                    'pattern': pattern
                }

        return best_match

    def execute(self, input_data: Dict) -> Dict:
        """
        Ejecuta el nodo con los datos de entrada proporcionados.
        """
        if not self.validate_input(input_data):
            return {
                'node_id': self.node_id,
                'status': 'input_validation_failed',
                'error': 'Datos de entrada inválidos',
                'timestamp': datetime.now().isoformat()
            }

        self.status = "active"
        target_ip = input_data['target_ip']
        timeout = input_data.get('timeout', DEFAULT_TIMEOUT)
        ports = input_data.get('ports', DEFAULT_PORTS)
        os_detection = input_data.get('os_detection', True)

        logger.info(f"🔍 Iniciando escaneo de {target_ip} con {len(ports)} puertos")

        # Ejecutar escaneo de puertos
        scan_result = self.run_nmap_scan(target_ip, ports, timeout)

        if scan_result.get('status') != 'success':
            return {
                **scan_result,
                'node_id': self.node_id,
                'version': self.version
            }

        # Si se requiere detección de OS y no se detectó, intentar con fingerprinting
        if os_detection and scan_result['os_detection']['os'] == 'unknown':
            fingerprint_result = self.run_os_fingerprinting(target_ip, ports)
            if fingerprint_result.get('status') == 'success':
                # Combinar resultados
                combined_os = {
                    'os': fingerprint_result['os_detection']['os'],
                    'confidence': max(
                        scan_result['os_detection']['confidence'],
                        fingerprint_result['os_detection']['confidence']
                    ),
                    'methods': scan_result['os_detection']['methods'] + fingerprint_result['os_detection']['methods']
                }
                scan_result['os_detection'] = combined_os

        # Añadir metadata
        scan_result.update({
            'node_id': self.node_id,
            'version': self.version,
            'status': 'completed',
            'metadata': {
                'platform': platform.system(),
                'python_version': platform.python_version(),
                'timestamp': datetime.now().isoformat()
            }
        })

        self.status = "inactive"
        return scan_result

    def get_info(self) -> Dict:
        """Devuelve información del nodo."""
        return {
            'node_id': self.node_id,
            'version': self.version,
            'status': self.status,
            'description': 'Escaneo profundo de puertos y detección de sistemas operativos',
            'input_interface': {
                'target_ip': 'Dirección IP o dominio del objetivo',
                'timeout': 'Tiempo de espera para el escaneo (segundos)',
                'ports': 'Lista de puertos a escanear (opcional)',
                'os_detection': 'Habilitar detección de sistema operativo (bool)'
            },
            'output_interface': {
                'target': 'Dirección IP del objetivo',
                'status': 'Estado del escaneo',
                'open_ports': 'Lista de puertos abiertos con servicios y versiones',
                'services': 'Diccionario de servicios por puerto',
                'os_detection': {
                    'os': 'Sistema operativo detectado',
                    'confidence': 'Confianza en la detección (0-1)',
                    'methods': 'Métodos usados para la detección'
                },
                'timestamp': 'Fecha y hora del escaneo',
                'metadata': 'Información adicional del sistema'
            }
        }

# Ejemplo de uso
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=f"{NODE_ID} - Escaneo profundo de puertos y detección de OS")
    parser.add_argument("target", help="Dirección IP o dominio del objetivo")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Tiempo de espera para el escaneo")
    parser.add_argument("--ports", nargs='+', type=int, help="Lista de puertos a escanear")
    parser.add_argument("--no-os", action='store_true', help="Deshabilitar detección de sistema operativo")
    args = parser.parse_args()

    node = NOD_WIFI_DEAUTH()

    input_data = {
        'target_ip': args.target,
        'timeout': args.timeout,
        'ports': args.ports if args.ports else DEFAULT_PORTS,
        'os_detection': not args.no_os
    }

    result = node.execute(input_data)

    print(json.dumps(result, indent=2))