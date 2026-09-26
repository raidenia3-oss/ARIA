#!/usr/bin/env python3
"""
Utilidades para GBrain - Herramientas complementarias para el motor de conocimiento
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime
import sqlite3
import hashlib
import shutil
import subprocess
import sys
import networkx as nx
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import markdown
import re
import yaml
import base64
import zlib
import pickle
from gbrain_orchestrator import GBrainOrchestrator

class GBrainUtils:
    """
    Clase con utilidades complementarias para el motor GBrain.
    """

    def __init__(self, vault_path: str, config_path: str = "TERMUX_AGENT/config/gbrain_config.json"):
        """
        Inicializa las utilidades de GBrain.

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

    def _load_config(self) -> Dict:
        """Carga la configuración de utilidades."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Archivo de configuración no encontrado: {self.config_path}")

        with open(self.config_path, 'r') as f:
            return json.load(f)

    def _setup_logger(self) -> logging.Logger:
        """Configura el logger para las utilidades."""
        logger = logging.getLogger('GBrainUtils')
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
        log_file = log_dir / f"utils_{datetime.now().strftime('%Y%m%d')}.log"

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
        """Instala las dependencias requeridas para las utilidades."""
        required_packages = self.config.get('dependencies', {}).get('required_packages', [])

        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *required_packages])
            self.logger.info(f"Dependencias instaladas: {', '.join(required_packages)}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error al instalar dependencias: {str(e)}")
            return False

    def _get_utils_config(self) -> Dict:
        """Obtiene la configuración específica de utilidades."""
        return self.config.get('utils', {
            'enabled': True,
            'cache_enabled': True,
            'cache_size_mb': 100,
            'cache_expiration_days': 7,
            'compression_enabled': True,
            'compression_level': 6,
            'security': {
                'encryption_enabled': False,
                'encryption_key': None
            },
            'export': {
                'enabled': True,
                'export_formats': ['json', 'graphml', 'csv', 'yaml'],
                'max_export_size_mb': 500
            }
        })

    def _get_cache_path(self, cache_type: str) -> Path:
        """Obtiene la ruta del caché para un tipo específico."""
        cache_dir = self.vault_path / "04_Memory_Index" / "cache"
        cache_dir.mkdir(exist_ok=True)

        return cache_dir / f"{cache_type}.cache"

    def _load_from_cache(self, cache_type: str, key: str) -> Optional[Union[Dict, List, str]]:
        """Carga datos desde el caché."""
        cache_path = self._get_cache_path(cache_type)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'rb') as f:
                cache_data = pickle.load(f)

            if key in cache_data:
                return cache_data[key]
            return None
        except Exception as e:
            self.logger.error(f"Error al cargar desde caché: {str(e)}")
            return None

    def _save_to_cache(self, cache_type: str, key: str, data: Union[Dict, List, str], expire_days: int = 7):
        """Guarda datos en el caché."""
        cache_path = self._get_cache_path(cache_type)
        cache_data = {}

        try:
            # Cargar caché existente si existe
            if cache_path.exists():
                with open(cache_path, 'rb') as f:
                    cache_data = pickle.load(f)

            # Agregar o actualizar datos
            cache_data[key] = {
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'expires': (datetime.now() + timedelta(days=expire_days)).isoformat()
            }

            # Guardar caché actualizada
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f)

        except Exception as e:
            self.logger.error(f"Error al guardar en caché: {str(e)}")

    def _clean_cache(self):
        """Limpia el caché eliminando entradas expiradas."""
        cache_path = self._get_cache_path('general')

        if not cache_path.exists():
            return

        try:
            with open(cache_path, 'rb') as f:
                cache_data = pickle.load(f)

            current_time = datetime.now()
            cleaned_data = {}

            for key, value in cache_data.items():
                try:
                    expires = datetime.fromisoformat(value['expires'])
                    if current_time < expires:
                        cleaned_data[key] = value
                except:
                    # Si no hay fecha de expiración o hay error, mantener el dato
                    cleaned_data[key] = value

            # Guardar caché limpia
            if cleaned_data:
                with open(cache_path, 'wb') as f:
                    pickle.dump(cleaned_data, f)

        except Exception as e:
            self.logger.error(f"Error al limpiar caché: {str(e)}")

    def _compress_data(self, data: Union[str, bytes, Dict, List]) -> bytes:
        """Comprime datos usando zlib."""
        if isinstance(data, (dict, list)):
            data = json.dumps(data).encode('utf-8')
        elif isinstance(data, str):
            data = data.encode('utf-8')

        return zlib.compress(data, level=self.config.get('utils', {}).get('compression_level', 6))

    def _decompress_data(self, compressed_data: bytes) -> Union[str, Dict, List]:
        """Descomprime datos comprimidos."""
        decompressed = zlib.decompress(compressed_data)

        try:
            return json.loads(decompressed.decode('utf-8'))
        except json.JSONDecodeError:
            return decompressed.decode('utf-8')

    def _encrypt_data(self, data: Union[str, bytes], key: Optional[str] = None) -> bytes:
        """Encripta datos usando AES (simplificado)."""
        if not self.config.get('utils', {}).get('security', {}).get('encryption_enabled', False):
            return data

        if not key:
            key = self.config.get('utils', {}).get('security', {}).get('encryption_key', None)

        if not key:
            self.logger.warning("No se proporcionó clave de encriptación")
            return data

        # En una implementación real usaríamos AES o similar
        # Esto es solo un ejemplo simplificado
        if isinstance(data, str):
            data = data.encode('utf-8')

        # XOR simplificado (no seguro para producción)
        return bytes([b ^ ord(key[i % len(key)]) for i, b in enumerate(data)])

    def _decrypt_data(self, encrypted_data: bytes, key: Optional[str] = None) -> Union[str, bytes]:
        """Desencripta datos (simplificado)."""
        if not self.config.get('utils', {}).get('security', {}).get('encryption_enabled', False):
            return encrypted_data

        if not key:
            key = self.config.get('utils', {}).get('security', {}).get('encryption_key', None)

        if not key:
            self.logger.warning("No se proporcionó clave de encriptación")
            return encrypted_data

        # XOR simplificado (no seguro para producción)
        return bytes([b ^ ord(key[i % len(key)]) for i, b in enumerate(encrypted_data)])

    def _validate_knowledge_graph(self) -> Dict:
        """
        Valida la integridad del grafo de conocimiento.

        Returns:
            Diccionario con métricas de validación
        """
        graph = self.orchestrator.graph
        metrics = {
            'nodes': graph.number_of_nodes(),
            'edges': graph.number_of_edges(),
            'isolated_nodes': 0,
            'orphaned_nodes': 0,
            'self_loops': 0,
            'duplicate_edges': 0,
            'missing_metadata': 0,
            'valid': True,
            'warnings': [],
            'errors': []
        }

        # Contar nodos aislados
        metrics['isolated_nodes'] = len([n for n in graph.nodes() if graph.degree(n) == 0])

        # Contar bucles auto-referenciales
        metrics['self_loops'] = len([n for n in graph.nodes() if graph.has_edge(n, n)])

        # Verificar metadatos en nodos
        for node in graph.nodes(data=True):
            node_id, node_data = node
            if 'title' not in node_data or 'path' not in node_data:
                metrics['missing_metadata'] += 1
                metrics['warnings'].append(f"Nodo {node_id} falta metadata (title o path)")

        # Verificar aristas duplicadas
        edge_list = list(graph.edges(data=True))
        seen_edges = set()

        for edge in edge_list:
            from_node, to_node = edge[:2]
            edge_key = (from_node, to_node)

            if edge_key in seen_edges:
                metrics['duplicate_edges'] += 1
                metrics['warnings'].append(f"Arista duplicada entre nodos {from_node} y {to_node}")
            else:
                seen_edges.add(edge_key)

        # Verificar nodos huérfanos (sin aristas entrantes)
        for node in graph.nodes():
            if graph.in_degree(node) == 0 and graph.out_degree(node) == 0:
                metrics['orphaned_nodes'] += 1
                metrics['warnings'].append(f"Nodo huérfano detectado: {node}")

        # Verificar si hay errores críticos
        if metrics['isolated_nodes'] > metrics['nodes'] * 0.2:
            metrics['errors'].append(f"Demasiados nodos aislados ({metrics['isolated_nodes']} de {metrics['nodes']})")
            metrics['valid'] = False

        if metrics['self_loops'] > 0:
            metrics['errors'].append(f"Bucles auto-referenciales detectados: {metrics['self_loops']}")
            metrics['valid'] = False

        if metrics['duplicate_edges'] > 0:
            metrics['warnings'].append(f"Aristas duplicadas detectadas: {metrics['duplicate_edges']}")

        if metrics['missing_metadata'] > 0:
            metrics['warnings'].append(f"Metadatos faltantes en {metrics['missing_metadata']} nodos")

        return metrics

    def _analyze_knowledge_distribution(self) -> Dict:
        """
        Analiza la distribución del conocimiento en el grafo.

        Returns:
            Diccionario con métricas de distribución
        """
        graph = self.orchestrator.graph
        analysis = {
            'total_nodes': graph.number_of_nodes(),
            'total_edges': graph.number_of_edges(),
            'average_degree': 0,
            'max_degree': 0,
            'min_degree': float('inf'),
            'degree_distribution': {},
            'centrality_metrics': {},
            'topics': {},
            'file_types': {},
            'modularity': 0,
            'density': 0,
            'connected_components': 0
        }

        # Calcular grados promedio, máximo y mínimo
        degrees = [graph.degree(n) for n in graph.nodes()]
        analysis['average_degree'] = sum(degrees) / len(degrees) if degrees else 0
        analysis['max_degree'] = max(degrees) if degrees else 0
        analysis['min_degree'] = min(degrees) if degrees else float('inf')

        # Distribución de grados
        for degree in degrees:
            analysis['degree_distribution'][degree] = analysis['degree_distribution'].get(degree, 0) + 1

        # Métricas de centralidad
        try:
            centrality = nx.degree_centrality(graph)
            analysis['centrality_metrics']['degree_centrality'] = {
                'max': max(centrality.values()) if centrality else 0,
                'min': min(centrality.values()) if centrality else 0,
                'avg': sum(centrality.values()) / len(centrality) if centrality else 0
            }

            betweenness = nx.betweenness_centrality(graph, weight='weight')
            analysis['centrality_metrics']['betweenness_centrality'] = {
                'max': max(betweenness.values()) if betweenness else 0,
                'min': min(betweenness.values()) if betweenness else 0,
                'avg': sum(betweenness.values()) / len(betweenness) if betweenness else 0
            }

            closeness = nx.closeness_centrality(graph)
            analysis['centrality_metrics']['closeness_centrality'] = {
                'max': max(closeness.values()) if closeness else 0,
                'min': min(closeness.values()) if closeness else 0,
                'avg': sum(closeness.values()) / len(closeness) if closeness else 0
            }

        except Exception as e:
            self.logger.warning(f"Error al calcular métricas de centralidad: {str(e)}")

        # Densidad del grafo
        analysis['density'] = nx.density(graph)

        # Componentes conectados
        analysis['connected_components'] = nx.number_connected_components(graph)

        # Modularidad (simplificado)
        try:
            communities = nx.algorithms.community.greedy_modularity_communities(graph)
            analysis['modularity'] = nx.algorithms.community.modularity(graph, communities)
        except Exception as e:
            self.logger.warning(f"Error al calcular modularidad: {str(e)}")

        # Analizar temas (simplificado)
        for node in graph.nodes(data=True):
            node_id, node_data = node
            file_path = node_data.get('path', '')

            # Extraer tema del título o path
            if 'title' in node_data and node_data['title']:
                # Analizar palabras clave en el título
                title = node_data['title'].lower()
                for word in ['arquitectura', 'configuración', 'módulo', 'táctico', 'osint', 'nmap', 'termux', 'android']:
                    if word in title:
                        analysis['topics'][word] = analysis['topics'].get(word, 0) + 1
                        break

            # Analizar tipo de archivo
            if file_path:
                file_type = os.path.splitext(file_path)[1].lower()
                if file_type:
                    analysis['file_types'][file_type] = analysis['file_types'].get(file_type, 0) + 1

        return analysis

    def _export_knowledge_graph(self, format: str = 'json', output_path: Optional[str] = None) -> str:
        """
        Exporta el grafo de conocimiento en diferentes formatos.

        Args:
            format: Formato de exportación (json, graphml, csv, yaml)
            output_path: Ruta de salida (None para usar ruta por defecto)

        Returns:
            Ruta del archivo exportado
        """
        if format not in self.config.get('utils', {}).get('export', {}).get('export_formats', []):
            raise ValueError(f"Formato de exportación no soportado: {format}")

        graph_data = self.orchestrator.get_knowledge_graph()

        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = self.vault_path / f"04_Memory_Index/exports/knowledge_graph_{timestamp}.{format}"

        # Crear directorio de exportación si no existe
        export_dir = self.vault_path / "04_Memory_Index" / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        try:
            if format == 'json':
                with open(output_path, 'w') as f:
                    json.dump(graph_data, f, indent=2, ensure_ascii=False)

            elif format == 'graphml':
                import xml.etree.ElementTree as ET
                from xml.dom import minidom

                # Crear estructura XML
                graphml = ET.Element('graphml', xmlns='http://graphml.graphdrawing.org/xmlns')
                graphml.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
                graphml.set('xsi:schemaLocation', 'http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd')

                # Añadir datos
                key_default = ET.SubElement(graphml, 'key', id='d0', for_='node', attr_name='label', attr_type='string')
                key_weight = ET.SubElement(graphml, 'key', id='e0', for_='edge', attr_name='weight', attr_type='double')

                graph = ET.SubElement(graphml, 'graph', id='G', edgedefault='directed')

                # Añadir nodos
                for node in graph_data['graph']['nodes']:
                    node_elem = ET.SubElement(graph, 'node', id=str(node['id']))
                    ET.SubElement(node_elem, 'data', key='d0').text = node.get('title', str(node['id']))

                # Añadir aristas
                for edge in graph_data['graph']['edges']:
                    edge_elem = ET.SubElement(graph, 'edge', source=str(edge['from']), target=str(edge['to']))
                    ET.SubElement(edge_elem, 'data', key='e0').text = str(edge.get('weight', 1.0))

                # Formatear XML
                rough_string = ET.tostring(graphml, 'utf-8')
                reparsed = minidom.parseString(rough_string)
                pretty_xml = reparsed.toprettyxml(indent="  ")

                with open(output_path, 'w') as f:
                    f.write(pretty_xml.decode('utf-8'))

            elif format == 'csv':
                # Exportar nodos
                nodes_path = output_path.with_suffix('.nodes.csv')
                with open(nodes_path, 'w') as f:
                    f.write('id,title,path\n')
                    for node in graph_data['graph']['nodes']:
                        f.write(f"{node['id']},{node.get('title', '')},{node.get('path', '')}\n")

                # Exportar aristas
                edges_path = output_path.with_suffix('.edges.csv')
                with open(edges_path, 'w') as f:
                    f.write('from,to,weight,relationship_type\n')
                    for edge in graph_data['graph']['edges']:
                        f.write(f"{edge['from']},{edge['to']},{edge.get('weight', 1.0)},{edge.get('relationship_type', '')}\n")

                # Devolver ruta del directorio con ambos archivos
                return str(nodes_path.parent)

            elif format == 'yaml':
                with open(output_path, 'w') as f:
                    yaml.dump(graph_data, f, allow_unicode=True, default_flow_style=False)

            self.logger.info(f"Grafo de conocimiento exportado a: {output_path}")
            return str(output_path)

        except Exception as e:
            self.logger.error(f"Error al exportar grafo de conocimiento: {str(e)}")
            raise

    def _import_knowledge_graph(self, input_path: str, format: str = 'json') -> bool:
        """
        Importa un grafo de conocimiento desde un archivo.

        Args:
            input_path: Ruta al archivo de importación
            format: Formato del archivo (json, graphml, csv, yaml)

        Returns:
            True si la importación fue exitosa
        """
        if format not in self.config.get('utils', {}).get('export', {}).get('export_formats', []):
            raise ValueError(f"Formato de importación no soportado: {format}")

        try:
            if format == 'json':
                with open(input_path, 'r') as f:
                    graph_data = json.load(f)

                # Reconstruir el grafo
                graph = nx.DiGraph()

                # Añadir nodos
                for node in graph_data.get('graph', {}).get('nodes', []):
                    graph.add_node(node['id'], **node)

                # Añadir aristas
                for edge in graph_data.get('graph', {}).get('edges', []):
                    graph.add_edge(
                        edge['from'],
                        edge['to'],
                        **edge
                    )

                # Actualizar el orquestador con el nuevo grafo
                self.orchestrator.graph = graph

                # Guardar cambios en la base de datos
                self.orchestrator._update_graph_database(graph)

                self.logger.info(f"Grafo de conocimiento importado desde {input_path}")
                return True

            elif format == 'graphml':
                import xml.etree.ElementTree as ET

                tree = ET.parse(input_path)
                root = tree.getroot()

                graph = nx.DiGraph()

                # Procesar nodos
                for node in root.findall('.//node'):
                    node_id = node.get('id')
                    label = node.find('.//data[@key="d0"]').text if node.find('.//data[@key="d0"]') is not None else str(node_id)
                    graph.add_node(node_id, title=label)

                # Procesar aristas
                for edge in root.findall('.//edge'):
                    source = edge.get('source')
                    target = edge.get('target')
                    weight = float(edge.find('.//data[@key="e0"]').text) if edge.find('.//data[@key="e0"]') is not None else 1.0
                    graph.add_edge(source, target, weight=weight)

                # Actualizar el orquestador con el nuevo grafo
                self.orchestrator.graph = graph

                # Guardar cambios en la base de datos
                self.orchestrator._update_graph_database(graph)

                self.logger.info(f"Grafo de conocimiento importado desde {input_path}")
                return True

            elif format == 'csv':
                # Leer nodos
                nodes_path = Path(input_path).with_suffix('.nodes.csv')
                edges_path = Path(input_path).with_suffix('.edges.csv')

                if not nodes_path.exists() or not edges_path.exists():
                    raise FileNotFoundError("Archivos CSV de nodos y aristas no encontrados")

                graph = nx.DiGraph()

                # Leer nodos
                with open(nodes_path, 'r') as f:
                    next(f)  # Saltar encabezado
                    for line in f:
                        parts = line.strip().split(',')
                        if len(parts) >= 3:
                            node_id, title, path = parts[0], parts[1], parts[2]
                            graph.add_node(node_id, title=title, path=path)

                # Leer aristas
                with open(edges_path, 'r') as f:
                    next(f)  # Saltar encabezado
                    for line in f:
                        parts = line.strip().split(',')
                        if len(parts) >= 4:
                            from_node, to_node, weight, rel_type = parts[0], parts[1], float(parts[2]), parts[3]
                            graph.add_edge(from_node, to_node, weight=weight, relationship_type=rel_type)

                # Actualizar el orquestador con el nuevo grafo
                self.orchestrator.graph = graph

                # Guardar cambios en la base de datos
                self.orchestrator._update_graph_database(graph)

                self.logger.info(f"Grafo de conocimiento importado desde {input_path}")
                return True

            elif format == 'yaml':
                with open(input_path, 'r') as f:
                    graph_data = yaml.safe_load(f)

                # Reconstruir el grafo (igual que en JSON)
                graph = nx.DiGraph()

                # Añadir nodos
                for node in graph_data.get('graph', {}).get('nodes', []):
                    graph.add_node(node['id'], **node)

                # Añadir aristas
                for edge in graph_data.get('graph', {}).get('edges', []):
                    graph.add_edge(
                        edge['from'],
                        edge['to'],
                        **edge
                    )

                # Actualizar el orquestador con el nuevo grafo
                self.orchestrator.graph = graph

                # Guardar cambios en la base de datos
                self.orchestrator._update_graph_database(graph)

                self.logger.info(f"Grafo de conocimiento importado desde {input_path}")
                return True

        except Exception as e:
            self.logger.error(f"Error al importar grafo de conocimiento: {str(e)}")
            raise

    def _analyze_text_similarity(self, text1: str, text2: str) -> float:
        """
        Analiza la similitud semántica entre dos textos.

        Args:
            text1: Primer texto
            text2: Segundo texto

        Returns:
            Score de similitud (0-1)
        """
        try:
            model = SentenceTransformer(self.config.get('embedding_model', 'all-MiniLM-L6-v2'))
            embedding1 = model.encode(text1)
            embedding2 = model.encode(text2)

            similarity = cosine_similarity([embedding1], [embedding2])[0][0]
            return float(similarity)

        except Exception as e:
            self.logger.error(f"Error al analizar similitud de texto: {str(e)}")
            return 0.0

    def _extract_key_phrases(self, text: str, top_k: int = 5) -> List[str]:
        """
        Extrae frases clave de un texto usando análisis de frecuencia y embeddings.

        Args:
            text: Texto de entrada
            top_k: Número de frases clave a extraer

        Returns:
            Lista de frases clave ordenadas por relevancia
        """
        try:
            # Tokenizar y analizar frecuencia de palabras
            words = re.findall(r'\b\w+\b', text.lower())
            word_freq = {}
            for word in words:
                word_freq[word] = word_freq.get(word, 0) + 1

            # Obtener palabras más frecuentes (excluyendo stopwords comunes)
            stopwords = {'el', 'la', 'los', 'las', 'de', 'y', 'a', 'en', 'que', 'con', 'no', 'se', 'del', 'por', 'para'}
            filtered_words = {word: freq for word, freq in word_freq.items() if word not in stopwords and len(word) > 3}

            if not filtered_words:
                return []

            # Obtener las palabras más frecuentes
            top_words = sorted(filtered_words.items(), key=lambda x: x[1], reverse=True)[:top_k]

            # Generar frases clave combinando palabras frecuentes
            key_phrases = []
            for word, _ in top_words:
                # Buscar frases que contengan esta palabra
                phrases = re.findall(r'(?i)\b.*\b' + re.escape(word) + r'\b.*', text)
                for phrase in phrases:
                    # Limpiar y normalizar la frase
                    clean_phrase = ' '.join(phrase.split()).strip()
                    if clean_phrase not in key_phrases:
                        key_phrases.append(clean_phrase)

            # Ordenar frases por longitud y frecuencia
            key_phrases.sort(key=lambda x: (-len(x.split()), -sum(1 for w in x.split() if w in filtered_words)))

            return key_phrases[:top_k]

        except Exception as e:
            self.logger.error(f"Error al extraer frases clave: {str(e)}")
            return []

    def _summarize_text(self, text: str, ratio: float = 0.2) -> str:
        """
        Genera un resumen de un texto usando análisis de frecuencia y embeddings.

        Args:
            text: Texto de entrada
            ratio: Proporción del texto a mantener en el resumen (0-1)

        Returns:
            Texto resumido
        """
        try:
            # Tokenizar el texto
            sentences = re.split(r'(?<=[.!?])\s+', text)
            if not sentences:
                return text

            # Calcular longitud objetivo del resumen
            target_length = int(len(text) * ratio)

            # Analizar importancia de cada oración usando embeddings
            model = SentenceTransformer(self.config.get('embedding_model', 'all-MiniLM-L6-v2'))
            embeddings = model.encode(sentences)

            # Calcular similitud entre oraciones (para detectar oraciones redundantes)
            similarity_matrix = cosine_similarity(embeddings)

            # Puntuar oraciones (combinando longitud y similitud con otras oraciones)
            scores = []
            for i, sentence in enumerate(sentences):
                # Puntuación base por longitud (oraciones más largas suelen ser más importantes)
                length_score = len(sentence.split()) / max(5, len(sentences[0].split()))

                # Puntuación por similitud (oraciones muy similares a otras pueden ser redundantes)
                sim_score = 1.0
                for j, sim in enumerate(similarity_matrix[i]):
                    if i != j and sim > 0.7:  # Umbral de similitud
                        sim_score *= 0.9  # Reducir puntuación por redundancia

                # Puntuación combinada
                score = length_score * sim_score
                scores.append(score)

            # Ordenar oraciones por puntuación (de mayor a menor)
            ranked_sentences = sorted(zip(sentences, scores), key=lambda x: x[1], reverse=True)

            # Seleccionar oraciones para el resumen
            summary_sentences = []
            current_length = 0
            for sentence, score in ranked_sentences:
                if current_length + len(sentence) <= target_length:
                    summary_sentences.append(sentence)
                    current_length += len(sentence)
                else:
                    break

            # Combinar oraciones en un texto coherente
            summary = ' '.join(summary_sentences)

            # Añadir puntos finales si faltan
            if not summary.endswith(('.', '!', '?')):
                summary += '.'

            return summary.strip()

        except Exception as e:
            self.logger.error(f"Error al generar resumen: {str(e)}")
            return text[:min(len(text), 500)]  # Devolver fragmento si falla

    def _generate_context_from_query(self, query: str, top_k: int = 3) -> Dict:
        """
        Genera contexto relevante a partir de una consulta usando el grafo de conocimiento.

        Args:
            query: Consulta de búsqueda
            top_k: Número de archivos relacionados a incluir

        Returns:
            Diccionario con contexto relevante
        """
        context = {
            'query': query,
            'results': [],
            'related_files': [],
            'summary': '',
            'key_phrases': [],
            'graph_analysis': {}
        }

        try:
            # 1. Buscar archivos relevantes
            search_results = self.orchestrator.search(query, top_k=top_k)
            context['results'] = search_results

            # 2. Obtener archivos relacionados
            if search_results:
                file_id = search_results[0]['file_id']
                related_files = self.orchestrator.get_related_files(file_id, top_k=top_k)
                context['related_files'] = related_files

            # 3. Generar resumen del contenido relevante
            if search_results:
                relevant_content = []
                for result in search_results:
                    relevant_content.append(result['content'])

                combined_content = ' '.join(relevant_content)
                context['summary'] = self._summarize_text(combined_content, ratio=0.3)

            # 4. Extraer frases clave
            if search_results:
                all_content = ' '.join([result['content'] for result in search_results])
                context['key_phrases'] = self._extract_key_phrases(all_content, top_k=5)

            # 5. Analizar el grafo de conocimiento
            context['graph_analysis'] = self._analyze_knowledge_distribution()

        except Exception as e:
            self.logger.error(f"Error al generar contexto: {str(e)}")

        return context

    def _generate_knowledge_report(self) -> Dict:
        """
        Genera un informe completo del estado del conocimiento.

        Returns:
            Diccionario con el informe de conocimiento
        """
        report = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'vault_path': str(self.vault_path),
                'gbrain_version': self.config.get('version', '1.0.0')
            },
            'status': self._validate_knowledge_graph(),
            'analysis': self._analyze_knowledge_distribution(),
            'metrics': {
                'files_processed': len(self.orchestrator.file_index),
                'nodes_in_graph': self.orchestrator.graph.number_of_nodes(),
                'edges_in_graph': self.orchestrator.graph.number_of_edges(),
                'vault_size_mb': self._get_vault_size_mb(),
                'last_sync': self._get_last_sync_time(),
                'dependencies': {
                    'installed': self._verify_dependencies(),
                    'missing': [] if self._verify_dependencies() else self._get_missing_dependencies()
                }
            },
            'sample_data': {
                'sample_nodes': [],
                'sample_edges': [],
                'sample_search': []
            }
        }

        try:
            # Obtener nodos de ejemplo
            nodes = list(self.orchestrator.graph.nodes(data=True))
            report['sample_data']['sample_nodes'] = nodes[:min(5, len(nodes))]

            # Obtener aristas de ejemplo
            edges = list(self.orchestrator.graph.edges(data=True))
            report['sample_data']['sample_edges'] = edges[:min(5, len(edges))]

            # Ejecutar una búsqueda de ejemplo
            example_query = "arquitectura del sistema"
            search_results = self.orchestrator.search(example_query, top_k=3)
            report['sample_data']['sample_search'] = search_results

        except Exception as e:
            self.logger.error(f"Error al generar informe de conocimiento: {str(e)}")

        return report

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

    def get_utils_status(self) -> Dict:
        """Obtiene el estado actual de las utilidades."""
        return {
            'status': 'active',
            'cache_enabled': self.config.get('utils', {}).get('cache_enabled', True),
            'compression_enabled': self.config.get('utils', {}).get('compression_enabled', True),
            'security_enabled': self.config.get('utils', {}).get('security', {}).get('encryption_enabled', False),
            'export_formats': self.config.get('utils', {}).get('export', {}).get('export_formats', []),
            'vault_size_mb': self._get_vault_size_mb(),
            'last_sync': self._get_last_sync_time(),
            'utils_config': self._get_utils_config(),
            'dependencies': {
                'installed': self._verify_dependencies(),
                'missing': [] if self._verify_dependencies() else self._get_missing_dependencies()
            }
        }

    def update_config(self, new_config: Dict):
        """
        Actualiza la configuración de utilidades.

        Args:
            new_config: Nuevo diccionario de configuración
        """
        self.config.update(new_config)

        # Guardar configuración actualizada
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

        self.logger.info("Configuración actualizada con éxito")

    def clean_cache(self):
        """Limpia el caché de utilidades."""
        self._clean_cache()
        self.logger.info("Caché limpiado con éxito")

    def compress_data(self, data: Union[str, bytes, Dict, List]) -> bytes:
        """Comprime datos usando zlib."""
        return self._compress_data(data)

    def decompress_data(self, compressed_data: bytes) -> Union[str, Dict, List]:
        """Descomprime datos comprimidos."""
        return self._decompress_data(compressed_data)

    def encrypt_data(self, data: Union[str, bytes], key: Optional[str] = None) -> bytes:
        """Encripta datos."""
        return self._encrypt_data(data, key)

    def decrypt_data(self, encrypted_data: bytes, key: Optional[str] = None) -> Union[str, bytes]:
        """Desencripta datos."""
        return self._decrypt_data(encrypted_data, key)

    def validate_knowledge_graph(self) -> Dict:
        """Valida la integridad del grafo de conocimiento."""
        return self._validate_knowledge_graph()

    def analyze_knowledge_distribution(self) -> Dict:
        """Analiza la distribución del conocimiento en el grafo."""
        return self._analyze_knowledge_distribution()

    def export_knowledge_graph(self, format: str = 'json', output_path: Optional[str] = None) -> str:
        """Exporta el grafo de conocimiento."""
        return self._export_knowledge_graph(format, output_path)

    def import_knowledge_graph(self, input_path: str, format: str = 'json') -> bool:
        """Importa un grafo de conocimiento desde un archivo."""
        return self._import_knowledge_graph(input_path, format)

    def analyze_text_similarity(self, text1: str, text2: str) -> float:
        """Analiza la similitud semántica entre dos textos."""
        return self._analyze_text_similarity(text1, text2)

    def extract_key_phrases(self, text: str, top_k: int = 5) -> List[str]:
        """Extrae frases clave de un texto."""
        return self._extract_key_phrases(text, top_k)

    def summarize_text(self, text: str, ratio: float = 0.2) -> str:
        """Genera un resumen de un texto."""
        return self._summarize_text(text, ratio)

    def generate_context_from_query(self, query: str, top_k: int = 3) -> Dict:
        """Genera contexto relevante a partir de una consulta."""
        return self._generate_context_from_query(query, top_k)

    def generate_knowledge_report(self) -> Dict:
        """Genera un informe completo del estado del conocimiento."""
        return self._generate_knowledge_report()

if __name__ == "__main__":
    # Ejemplo de uso
    utils = GBrainUtils(
        vault_path="AME_EXPORT_PACKAGE/AURA_INTELLIGENCE_VAULT",
        config_path="AME_EXPORT_PACKAGE/TERMUX_AGENT/config/gbrain_config.json"
    )

    print("Estado actual de las utilidades:")
    print(json.dumps(utils.get_utils_status(), indent=2))

    # Ejemplo de validación del grafo
    print("\nValidación del grafo de conocimiento:")
    print(json.dumps(utils.validate_knowledge_graph(), indent=2))

    # Ejemplo de análisis de distribución
    print("\nAnálisis de distribución del conocimiento:")
    print(json.dumps(utils.analyze_knowledge_distribution(), indent=2))

    # Ejemplo de generación de contexto
    print("\nGenerando contexto a partir de consulta...")
    context = utils.generate_context_from_query("¿Cómo funciona el módulo Nmap Avanzado?", top_k=3)
    print(json.dumps(context, indent=2))

    # Ejemplo de exportación
    # print("\nExportando grafo de conocimiento...")
    # export_path = utils.export_knowledge_graph(format='json')
    # print(f"Grafo exportado a: {export_path}")

    # Ejemplo de generación de informe
    # print("\nGenerando informe de conocimiento...")
    # report = utils.generate_knowledge_report()
    # print(json.dumps(report, indent=2))