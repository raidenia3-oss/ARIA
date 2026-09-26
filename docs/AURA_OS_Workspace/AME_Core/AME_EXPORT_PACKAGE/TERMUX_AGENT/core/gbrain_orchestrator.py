#!/usr/bin/env python3
"""
GBrain Orchestrator - Motor de indexación semántica y relacional para AURA/AME
Integración híbrida Obsidian + GBrain (PG Lite)
"""

import os
import json
import sqlite3
import hashlib
import time
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import markdown
import networkx as nx
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

class GBrainOrchestrator:
    """
    Motor de indexación semántica y relacional para la bóveda de conocimiento AURA/AME.
    Combina Obsidian (frontend visual) con GBrain (backend semántico/relacional).
    """

    def __init__(self, vault_path: str, config_path: str = "config/gbrain_config.json"):
        """
        Inicializa el orquestador GBrain.

        Args:
            vault_path: Ruta a la bóveda de conocimiento (AURA_INTELLIGENCE_VAULT)
            config_path: Ruta al archivo de configuración
        """
        self.vault_path = Path(vault_path)
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.vector_db_path = self.vault_path / "04_Memory_Index" / "vectors.db"
        self.graph_db_path = self.vault_path / "04_Memory_Index" / "graph.db"
        self.index_path = self.vault_path / "04_Memory_Index" / "index.json"
        self.metadata_path = self.vault_path / "04_Memory_Index" / "metadata.json"

        # Inicializar bases de datos
        self._init_vector_db()
        self._init_graph_db()

        # Cargar modelo de embeddings
        self.model = SentenceTransformer(self.config.get('embedding_model', 'all-MiniLM-L6-v2'))

        # Cargar grafo relacional
        self.graph = nx.DiGraph()

        # Cargar índice de archivos
        self.file_index = self._load_index()

    def _load_config(self) -> Dict:
        """Carga la configuración de GBrain."""
        if not self.config_path.exists():
            return {
                'embedding_model': 'all-MiniLM-L6-v2',
                'chunk_size': 500,
                'chunk_overlap': 100,
                'similarity_threshold': 0.75,
                'graph_update_interval': 3600,  # 1 hora
                'max_vectors': 10000,
                'metadata_fields': ['title', 'path', 'created', 'modified', 'word_count']
            }

        with open(self.config_path, 'r') as f:
            return json.load(f)

    def _init_vector_db(self):
        """Inicializa la base de datos de vectores."""
        if not self.vector_db_path.exists():
            conn = sqlite3.connect(self.vector_db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT UNIQUE,
                    chunk_id TEXT,
                    content TEXT,
                    embedding BLOB,
                    metadata JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_embedding ON vectors(embedding)
            ''')
            conn.commit()
            conn.close()

    def _init_graph_db(self):
        """Inicializa la base de datos del grafo relacional."""
        if not self.graph_db_path.exists():
            conn = sqlite3.connect(self.graph_db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT UNIQUE,
                    title TEXT,
                    path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_node_id INTEGER,
                    to_node_id INTEGER,
                    relationship_type TEXT,
                    weight REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (from_node_id) REFERENCES nodes(id),
                    FOREIGN KEY (to_node_id) REFERENCES nodes(id)
                )
            ''')
            conn.commit()
            conn.close()

    def _load_index(self) -> Dict:
        """Carga el índice de archivos procesados."""
        if not self.index_path.exists():
            return {}

        with open(self.index_path, 'r') as f:
            return json.load(f)

    def _save_index(self):
        """Guarda el índice de archivos procesados."""
        with open(self.index_path, 'w') as f:
            json.dump(self.file_index, f, indent=2)

    def _generate_file_id(self, file_path: str) -> str:
        """Genera un ID único para un archivo."""
        return hashlib.sha256(file_path.encode()).hexdigest()

    def _generate_chunk_id(self, file_id: str, chunk_idx: int) -> str:
        """Genera un ID único para un chunk."""
        return f"{file_id}_chunk_{chunk_idx}"

    def _extract_metadata(self, file_path: str) -> Dict:
        """Extrae metadatos de un archivo Markdown."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extraer título del archivo
        title_match = re.search(r'^#\s*(.*)', content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else file_path.stem

        # Extraer fecha de creación y modificación
        stat = os.stat(file_path)
        created = datetime.fromtimestamp(stat.st_ctime).isoformat()
        modified = datetime.fromtimestamp(stat.st_mtime).isoformat()

        return {
            'title': title,
            'path': str(file_path),
            'created': created,
            'modified': modified,
            'word_count': len(content.split()),
            'file_id': self._generate_file_id(file_path)
        }

    def _chunk_text(self, text: str) -> List[str]:
        """Divide el texto en chunks para procesamiento."""
        config = self.config
        words = text.split()
        chunks = []

        for i in range(0, len(words), config['chunk_size'] - config['chunk_overlap']):
            chunk = ' '.join(words[i:i + config['chunk_size']])
            chunks.append(chunk)

        return chunks

    def _process_markdown_file(self, file_path: str) -> List[Tuple[str, Dict]]:
        """Procesa un archivo Markdown y extrae chunks con metadatos."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Convertir Markdown a HTML para mejor procesamiento
        html = markdown.markdown(content)

        # Extraer metadatos
        metadata = self._extract_metadata(file_path)

        # Dividir en chunks
        chunks = self._chunk_text(html)

        # Generar embeddings para cada chunk
        embeddings = self.model.encode(chunks)

        # Crear registros para cada chunk
        file_id = metadata['file_id']
        results = []

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = self._generate_chunk_id(file_id, i)
            chunk_metadata = {
                'chunk_id': chunk_id,
                'file_id': file_id,
                'chunk_index': i,
                'chunk_size': len(chunk.split()),
                **metadata
            }

            results.append((chunk, chunk_metadata, embedding))

        return results

    def _save_chunk_to_db(self, chunk: str, metadata: Dict, embedding: np.ndarray):
        """Guarda un chunk en la base de datos de vectores."""
        conn = sqlite3.connect(self.vector_db_path)
        cursor = conn.cursor()

        # Convertir embedding a bytes
        embedding_bytes = embedding.tobytes()

        cursor.execute('''
            INSERT OR REPLACE INTO vectors
            (file_id, chunk_id, content, embedding, metadata)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            metadata['file_id'],
            metadata['chunk_id'],
            chunk,
            embedding_bytes,
            json.dumps(metadata)
        ))

        conn.commit()
        conn.close()

    def _save_node_to_db(self, metadata: Dict):
        """Guarda un nodo en la base de datos del grafo."""
        conn = sqlite3.connect(self.graph_db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO nodes
            (file_id, title, path)
            VALUES (?, ?, ?)
        ''', (
            metadata['file_id'],
            metadata['title'],
            metadata['path']
        ))

        conn.commit()
        conn.close()

    def _save_edge_to_db(self, from_node_id: int, to_node_id: int, relationship_type: str, weight: float):
        """Guarda una arista en la base de datos del grafo."""
        conn = sqlite3.connect(self.graph_db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO edges
            (from_node_id, to_node_id, relationship_type, weight)
            VALUES (?, ?, ?, ?)
        ''', (
            from_node_id,
            to_node_id,
            relationship_type,
            weight
        ))

        conn.commit()
        conn.close()

    def _load_nodes_from_db(self) -> List[Dict]:
        """Carga los nodos del grafo desde la base de datos."""
        conn = sqlite3.connect(self.graph_db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT id, file_id, title, path FROM nodes')
        nodes = cursor.fetchall()

        conn.close()

        return [{
            'id': node[0],
            'file_id': node[1],
            'title': node[2],
            'path': node[3]
        } for node in nodes]

    def _load_edges_from_db(self) -> List[Dict]:
        """Carga las aristas del grafo desde la base de datos."""
        conn = sqlite3.connect(self.graph_db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, from_node_id, to_node_id, relationship_type, weight
            FROM edges
        ''')
        edges = cursor.fetchall()

        conn.close()

        return [{
            'id': edge[0],
            'from_node_id': edge[1],
            'to_node_id': edge[2],
            'relationship_type': edge[3],
            'weight': edge[4]
        } for edge in edges]

    def _build_graph(self):
        """Construye el grafo relacional a partir de la base de datos."""
        nodes = self._load_nodes_from_db()
        edges = self._load_edges_from_db()

        # Crear nodos en el grafo
        for node in nodes:
            self.graph.add_node(node['id'], **node)

        # Crear aristas en el grafo
        for edge in edges:
            self.graph.add_edge(
                edge['from_node_id'],
                edge['to_node_id'],
                relationship_type=edge['relationship_type'],
                weight=edge['weight']
            )

    def _detect_relationships(self, chunks: List[Tuple[str, Dict, np.ndarray]]) -> List[Tuple[int, int, str, float]]:
        """
        Detecta relaciones entre chunks basadas en similitud semántica.
        """
        relationships = []
        config = self.config

        # Comparar todos los chunks entre sí
        for i, (chunk1, _, emb1) in enumerate(chunks):
            for j, (chunk2, _, emb2) in enumerate(chunks):
                if i != j:
                    # Calcular similitud coseno
                    similarity = cosine_similarity([emb1], [emb2])[0][0]

                    if similarity > config['similarity_threshold']:
                        # Determinar tipo de relación
                        rel_type = self._determine_relationship_type(chunk1, chunk2, similarity)

                        relationships.append((
                            chunks[i][1]['chunk_id'],
                            chunks[j][1]['chunk_id'],
                            rel_type,
                            similarity
                        ))

        return relationships

    def _determine_relationship_type(self, chunk1: str, chunk2: str, similarity: float) -> str:
        """
        Determina el tipo de relación entre dos chunks basados en su contenido y similitud.
        """
        # Analizar palabras clave y patrones
        chunk1_lower = chunk1.lower()
        chunk2_lower = chunk2.lower()

        # Si comparten palabras clave importantes
        if (('arquitectura' in chunk1_lower and 'arquitectura' in chunk2_lower) or
            ('configuración' in chunk1_lower and 'configuración' in chunk2_lower) or
            ('módulo' in chunk1_lower and 'módulo' in chunk2_lower)):
            return "relacion_tecnica"

        # Si uno es una definición y el otro un ejemplo
        if ('ejemplo' in chunk1_lower and 'definición' in chunk2_lower) or \
           ('definición' in chunk1_lower and 'ejemplo' in chunk2_lower):
            return "ejemplo_definicion"

        # Si hay alta similitud semántica pero no patrones claros
        if similarity > 0.85:
            return "relacion_fuerte"

        # Si hay similitud moderada
        if similarity > 0.75:
            return "relacion_debil"

        return "relacion_general"

    def _build_chunk_graph(self, chunks: List[Tuple[str, Dict, np.ndarray]]) -> nx.DiGraph:
        """Construye un grafo de relaciones entre chunks."""
        chunk_graph = nx.DiGraph()

        # Añadir nodos (chunks)
        for chunk_id, (_, metadata, _) in enumerate(chunks):
            chunk_graph.add_node(chunk_id, **metadata)

        # Detectar relaciones
        relationships = self._detect_relationships(chunks)

        # Añadir aristas al grafo
        for from_chunk_id, to_chunk_id, rel_type, weight in relationships:
            chunk_graph.add_edge(
                from_chunk_id,
                to_chunk_id,
                relationship_type=rel_type,
                weight=weight
            )

        return chunk_graph

    def _aggregate_chunk_graph(self, chunk_graph: nx.DiGraph) -> nx.DiGraph:
        """
        Agrega el grafo de chunks a nivel de archivos.
        Combina relaciones entre chunks para crear relaciones entre archivos.
        """
        file_graph = nx.DiGraph()

        # Agregar nodos (archivos)
        for node in chunk_graph.nodes(data=True):
            file_id = node[1]['file_id']
            if file_id not in file_graph.nodes:
                file_graph.add_node(file_id, **{
                    'title': node[1]['title'],
                    'path': node[1]['path']
                })

        # Agregar aristas (relaciones entre archivos)
        for from_node, to_node, data in chunk_graph.edges(data=True):
            from_file = chunk_graph.nodes[from_node]['file_id']
            to_file = chunk_graph.nodes[to_node]['file_id']

            if from_file != to_file:  # No relaciones dentro del mismo archivo
                if file_graph.has_edge(from_file, to_file):
                    # Sumar pesos si ya existe la relación
                    existing_weight = file_graph.edges[from_file, to_file]['weight']
                    file_graph.edges[from_file, to_file]['weight'] = existing_weight + data['weight']
                else:
                    # Crear nueva relación
                    file_graph.add_edge(
                        from_file,
                        to_file,
                        relationship_type=data['relationship_type'],
                        weight=data['weight']
                    )

        return file_graph

    def _update_graph_database(self, file_graph: nx.DiGraph):
        """Actualiza la base de datos del grafo con las relaciones detectadas."""
        # Obtener nodos existentes
        existing_nodes = self._load_nodes_from_db()
        existing_node_map = {node['file_id']: node['id'] for node in existing_nodes}

        # Procesar nodos nuevos/actualizados
        for node_data in file_graph.nodes(data=True):
            file_id = node_data[0]
            node_info = node_data[1]

            if file_id in existing_node_map:
                # Actualizar nodo existente
                node_id = existing_node_map[file_id]
                self._save_node_to_db({
                    'id': node_id,
                    'file_id': file_id,
                    'title': node_info['title'],
                    'path': node_info['path']
                })
            else:
                # Insertar nuevo nodo
                self._save_node_to_db({
                    'file_id': file_id,
                    'title': node_info['title'],
                    'path': node_info['path']
                })

        # Reconstruir el mapeo de nodos después de actualizar
        existing_nodes = self._load_nodes_from_db()
        existing_node_map = {node['file_id']: node['id'] for node in existing_nodes}

        # Procesar aristas
        for from_file, to_file, data in file_graph.edges(data=True):
            from_node_id = existing_node_map[from_file]
            to_node_id = existing_node_map[to_file]

            # Verificar si ya existe la relación
            conn = sqlite3.connect(self.graph_db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id FROM edges
                WHERE from_node_id = ? AND to_node_id = ?
            ''', (from_node_id, to_node_id))

            existing_edge = cursor.fetchone()

            if existing_edge:
                # Actualizar relación existente
                cursor.execute('''
                    UPDATE edges
                    SET relationship_type = ?, weight = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (data['relationship_type'], data['weight'], existing_edge[0]))
            else:
                # Insertar nueva relación
                cursor.execute('''
                    INSERT INTO edges
                    (from_node_id, to_node_id, relationship_type, weight)
                    VALUES (?, ?, ?, ?)
                ''', (
                    from_node_id,
                    to_node_id,
                    data['relationship_type'],
                    data['weight']
                ))

            conn.commit()
            conn.close()

    def _scan_vault(self) -> List[Path]:
        """Escanea la bóveda y devuelve los archivos Markdown válidos."""
        valid_files = []

        for root, _, files in os.walk(self.vault_path):
            for file in files:
                if file.endswith('.md'):
                    file_path = Path(root) / file
                    valid_files.append(file_path)

        return valid_files

    def _process_file(self, file_path: Path):
        """Procesa un archivo individual y actualiza las bases de datos."""
        print(f"Procesando archivo: {file_path}")

        # Procesar el archivo para extraer chunks
        chunks = self._process_markdown_file(file_path)

        # Guardar chunks en la base de datos de vectores
        for chunk, metadata, embedding in chunks:
            self._save_chunk_to_db(chunk, metadata, embedding)

        # Guardar metadatos del archivo en la base de datos del grafo
        metadata = self._extract_metadata(file_path)
        self._save_node_to_db(metadata)

        # Actualizar el índice de archivos
        self.file_index[metadata['file_id']] = metadata
        self._save_index()

        return chunks

    def process_vault(self):
        """Procesa toda la bóveda de conocimiento."""
        print("Iniciando procesamiento de la bóveda de conocimiento...")

        # Escanear bóveda
        files_to_process = self._scan_vault()

        # Procesar cada archivo
        all_chunks = []
        for file_path in files_to_process:
            chunks = self._process_file(file_path)
            all_chunks.extend(chunks)

        # Construir grafo de chunks
        chunk_graph = self._build_chunk_graph(all_chunks)

        # Agregar grafo a nivel de archivos
        file_graph = self._aggregate_chunk_graph(chunk_graph)

        # Actualizar base de datos del grafo
        self._update_graph_database(file_graph)

        # Reconstruir el grafo en memoria
        self._build_graph()

        print("Procesamiento de la bóveda completado.")

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Realiza una búsqueda semántica en la bóveda de conocimiento.

        Args:
            query: Consulta de búsqueda
            top_k: Número de resultados a devolver

        Returns:
            Lista de resultados ordenados por relevancia
        """
        # Generar embedding de la consulta
        query_embedding = self.model.encode([query])[0]

        # Consultar base de datos de vectores
        conn = sqlite3.connect(self.vector_db_path)
        cursor = conn.cursor()

        # Convertir embedding a bytes para la consulta
        query_embedding_bytes = query_embedding.tobytes()

        # Usar SQLite FTS5 para búsqueda vectorial (simplificado)
        # En una implementación real, usaríamos un motor de búsqueda vectorial especializado
        cursor.execute('''
            SELECT id, file_id, chunk_id, content, metadata, embedding
            FROM vectors
            ORDER BY similarity(embedding, ?) DESC
            LIMIT ?
        ''', (query_embedding_bytes, top_k))

        results = cursor.fetchall()

        conn.close()

        # Procesar resultados
        processed_results = []
        for result in results:
            result_id, file_id, chunk_id, content, metadata_json, embedding_bytes in result

            # Convertir embedding de vuelta a array
            embedding = np.frombuffer(embedding_bytes, dtype=np.float32)

            # Calcular similitud
            similarity = cosine_similarity([query_embedding], [embedding])[0][0]

            # Parsear metadatos
            metadata = json.loads(metadata_json)

            processed_results.append({
                'id': result_id,
                'file_id': file_id,
                'chunk_id': chunk_id,
                'content': content,
                'metadata': metadata,
                'similarity': float(similarity),
                'path': metadata['path'],
                'title': metadata['title']
            })

        return processed_results

    def get_related_files(self, file_id: str, top_k: int = 3) -> List[Dict]:
        """
        Obtiene archivos relacionados con un archivo específico basado en el grafo.

        Args:
            file_id: ID del archivo de referencia
            top_k: Número de archivos relacionados a devolver

        Returns:
            Lista de archivos relacionados ordenados por relevancia
        """
        if file_id not in self.file_index:
            return []

        # Obtener el ID del nodo en el grafo
        node_id = None
        for n in self.graph.nodes(data=True):
            if n[1]['file_id'] == file_id:
                node_id = n[0]
                break

        if not node_id:
            return []

        # Obtener vecinos en el grafo
        neighbors = list(self.graph.neighbors(node_id))

        # Ordenar por peso de la relación
        related_files = []
        for neighbor in neighbors:
            weight = self.graph.edges[node_id, neighbor]['weight']
            rel_type = self.graph.edges[node_id, neighbor]['relationship_type']

            # Obtener metadatos del archivo relacionado
            neighbor_data = self.graph.nodes[neighbor]
            related_files.append({
                'file_id': neighbor_data['file_id'],
                'title': neighbor_data['title'],
                'path': neighbor_data['path'],
                'weight': weight,
                'relationship_type': rel_type
            })

        # Ordenar por peso descendente
        related_files.sort(key=lambda x: x['weight'], reverse=True)

        return related_files[:top_k]

    def get_graph_structure(self) -> Dict:
        """
        Obtiene la estructura del grafo relacional.

        Returns:
            Representación del grafo en formato JSON
        """
        return {
            'nodes': [{'id': n, **data} for n, data in self.graph.nodes(data=True)],
            'edges': [{'from': u, 'to': v, **data} for u, v, data in self.graph.edges(data=True)]
        }

    def repair_broken_links(self):
        """
        Repara enlaces rotos en la bóveda detectando archivos que deberían estar conectados
        pero no lo están debido a cambios en los nombres o estructura.
        """
        print("Iniciando reparación de enlaces rotos...")

        # Escanear bóveda actual
        current_files = {self._generate_file_id(str(f)): f for f in self._scan_vault()}

        # Obtener archivos registrados en el índice
        registered_files = {f['file_id']: f for f in self.file_index.values()}

        # Detectar archivos eliminados
        deleted_files = set(registered_files.keys()) - set(current_files.keys())

        # Detectar archivos nuevos
        new_files = set(current_files.keys()) - set(registered_files.keys())

        # Procesar archivos nuevos
        for file_id in new_files:
            file_path = current_files[file_id]
            print(f"Detectado archivo nuevo: {file_path}")
            self._process_file(file_path)

        # Procesar archivos eliminados (marcar como eliminados en el grafo)
        for file_id in deleted_files:
            print(f"Detectado archivo eliminado: {registered_files[file_id]['path']}")
            # En una implementación real, marcaríamos estos archivos como eliminados
            # y actualizaríamos el grafo para reflejar esto

        # Reconstruir el grafo para detectar nuevas relaciones
        self.process_vault()

        print("Reparación de enlaces completada.")

    def run_dream_cycle(self):
        """
        Ejecuta un ciclo completo de mantenimiento de la base de conocimiento.
        """
        print("Iniciando ciclo de sueño de GBrain...")

        # 1. Procesar bóveda para detectar cambios
        self.process_vault()

        # 2. Reparar enlaces rotos
        self.repair_broken_links()

        # 3. Optimizar bases de datos
        self._optimize_databases()

        print("Ciclo de sueño de GBrain completado.")

    def _optimize_databases(self):
        """Optimiza las bases de datos para mejorar rendimiento."""
        print("Optimizando bases de datos...")

        # Optimizar base de datos de vectores
        conn = sqlite3.connect(self.vector_db_path)
        conn.execute("VACUUM")
        conn.close()

        # Optimizar base de datos del grafo
        conn = sqlite3.connect(self.graph_db_path)
        conn.execute("VACUUM")
        conn.close()

        print("Optimización de bases de datos completada.")

    def get_knowledge_graph(self) -> Dict:
        """
        Obtiene el grafo de conocimiento completo en formato JSON.

        Returns:
            Representación del grafo de conocimiento
        """
        return {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'node_count': self.graph.number_of_nodes(),
                'edge_count': self.graph.number_of_edges(),
                'files_processed': len(self.file_index)
            },
            'graph': self.get_graph_structure()
        }

if __name__ == "__main__":
    # Ejemplo de uso
    orchestrator = GBrainOrchestrator(
        vault_path="AME_EXPORT_PACKAGE/AURA_INTELLIGENCE_VAULT",
        config_path="AME_EXPORT_PACKAGE/TERMUX_AGENT/config/gbrain_config.json"
    )

    # Procesar la bóveda (solo la primera vez)
    # orchestrator.process_vault()

    # Ejemplo de búsqueda
    results = orchestrator.search("¿Cómo funciona el módulo Nmap Avanzado?", top_k=3)
    for result in results:
        print(f"\nResultado (similaridad: {result['similarity']:.2f}):")
        print(f"Archivo: {result['title']} ({result['path']})")
        print(f"Contenido: {result['content'][:200]}...")

    # Ejemplo de obtención de archivos relacionados
    related = orchestrator.get_related_files(results[0]['file_id'])
    print("\nArchivos relacionados:")
    for rel in related:
        print(f"- {rel['title']} (peso: {rel['weight']:.2f})")

    # Ejemplo de obtención del grafo de conocimiento
    graph_data = orchestrator.get_knowledge_graph()
    print(f"\nGrafo de conocimiento: {graph_data['metadata']['node_count']} nodos, {graph_data['metadata']['edge_count']} aristas")