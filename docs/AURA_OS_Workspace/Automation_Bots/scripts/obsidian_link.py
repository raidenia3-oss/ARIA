"""
obsidian_link.py - Integración de AURA con bóveda de Obsidian
Sistema de indexación de notas para memoria a largo plazo
"""

import os
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import hashlib
import markdown
from datetime import datetime

# Configuración global
KNOWLEDGE_BASE_FILE = "knowledge_base.json"
MAX_NOTE_LENGTH = 2000  # Caracteres máximos por nota en la base de datos
SEARCH_INDEX_FILE = "search_index.json"
CHUNK_SIZE = 500  # Tamaño de los fragmentos para búsqueda

class ObsidianIndexer:
    """
    Clase para indexar y buscar notas de Obsidian.
    """

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.knowledge_base = {}
        self.search_index = {}
        self.last_indexed = None

        # Validar que la bóveda exista
        if not self.vault_path.exists():
            raise FileNotFoundError(f"La bóveda de Obsidian no existe en {self.vault_path}")

        # Crear directorios si no existen
        self.vault_path.mkdir(parents=True, exist_ok=True)

        # Cargar base de conocimiento existente
        self.load_knowledge_base()

    def load_knowledge_base(self) -> None:
        """Cargar la base de conocimiento existente."""
        if os.path.exists(KNOWLEDGE_BASE_FILE):
            with open(KNOWLEDGE_BASE_FILE, "r", encoding="utf-8") as f:
                try:
                    self.knowledge_base = json.load(f)
                    self.last_indexed = self.knowledge_base.get("last_indexed")
                except json.JSONDecodeError:
                    self.knowledge_base = {}
                    self.last_indexed = None

        if os.path.exists(SEARCH_INDEX_FILE):
            with open(SEARCH_INDEX_FILE, "r", encoding="utf-8") as f:
                try:
                    self.search_index = json.load(f)
                except json.JSONDecodeError:
                    self.search_index = {}

    def save_knowledge_base(self) -> None:
        """Guardar la base de conocimiento."""
        self.knowledge_base["last_indexed"] = datetime.now().isoformat()
        with open(KNOWLEDGE_BASE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.knowledge_base, f, indent=2, ensure_ascii=False)

        with open(SEARCH_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(self.search_index, f, indent=2, ensure_ascii=False)

    def index_vault(self, recursive: bool = True) -> Dict[str, int]:
        """
        Indexar todas las notas .md en la bóveda de Obsidian.
        Retorna un dict con estadísticas del indexado.
        """
        stats = {
            "total_files": 0,
            "indexed_files": 0,
            "new_files": 0,
            "updated_files": 0,
            "skipped_files": 0,
            "error_files": 0
        }

        # Recorrer la bóveda
        for root, _, files in os.walk(self.vault_path):
            for file in files:
                if file.endswith(".md"):
                    file_path = Path(root) / file
                    stats["total_files"] += 1

                    try:
                        self._index_single_file(file_path, stats)
                    except Exception as e:
                        stats["error_files"] += 1
                        print(f"⚠️  Error indexando {file_path}: {e}")

        self.save_knowledge_base()
        return stats

    def _index_single_file(self, file_path: Path, stats: Dict) -> None:
        """Indexar un solo archivo .md."""
        file_hash = self._calculate_file_hash(file_path)
        file_key = str(file_path.relative_to(self.vault_path))

        # Leer contenido del archivo
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Procesar contenido (convertir markdown a texto plano)
        html = markdown.markdown(content)
        text = markdown.markdown(content, output_format="plain")

        # Extraer metadata del frontmatter (si existe)
        metadata = self._extract_metadata(content)

        # Crear entrada para la base de conocimiento
        note_entry = {
            "path": file_key,
            "title": metadata.get("title", file_path.stem),
            "tags": metadata.get("tags", []),
            "created": metadata.get("created", None),
            "modified": metadata.get("modified", None),
            "content": text,
            "html": html,
            "hash": file_hash,
            "last_indexed": datetime.now().isoformat(),
            "chunks": self._create_text_chunks(text)
        }

        # Verificar si el archivo ya existe en la base
        if file_key in self.knowledge_base:
            old_entry = self.knowledge_base[file_key]
            if old_entry.get("hash") == file_hash:
                stats["skipped_files"] += 1
                return  # No ha cambiado

            # Actualizar estadísticas
            stats["updated_files"] += 1
        else:
            stats["new_files"] += 1

        # Guardar en la base de conocimiento
        self.knowledge_base[file_key] = note_entry
        stats["indexed_files"] += 1

        # Actualizar índice de búsqueda
        self._update_search_index(note_entry)

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calcular hash SHA-256 del contenido de un archivo."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(4096), b""):
                h.update(block)
        return h.hexdigest()

    def _extract_metadata(self, content: str) -> Dict:
        """Extraer metadata del frontmatter de un archivo markdown."""
        metadata = {}

        # Buscar frontmatter (--- ... ---)
        frontmatter_match = re.search(r"^---\s*(.*?)\s*---\s*(?=\n|$)", content, re.DOTALL)
        if frontmatter_match:
            frontmatter_content = frontmatter_match.group(1)

            # Procesar cada línea del frontmatter
            for line in frontmatter_content.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()

                    # Procesar valores especiales
                    if key == "tags":
                        value = [tag.strip() for tag in value.split(',')]
                    elif key in ["created", "modified"]:
                        try:
                            value = datetime.fromisoformat(value.strip())
                        except ValueError:
                            pass

                    metadata[key] = value

        # Extraer título si no está en el frontmatter
        if "title" not in metadata:
            title_match = re.search(r"^#\s*(.*)", content, re.MULTILINE)
            if title_match:
                metadata["title"] = title_match.group(1).strip()

        return metadata

    def _create_text_chunks(self, text: str) -> List[str]:
        """Dividir el texto en fragmentos para búsqueda."""
        chunks = []
        for i in range(0, len(text), CHUNK_SIZE):
            chunk = text[i:i+CHUNK_SIZE].strip()
            if chunk:
                chunks.append(chunk)
        return chunks

    def _update_search_index(self, note_entry: Dict) -> None:
        """Actualizar el índice de búsqueda con los fragmentos de texto."""
        # Limpiar índice antiguo para esta nota
        old_key = f"note:{note_entry['path']}"
        if old_key in self.search_index:
            del self.search_index[old_key]

        # Añadir nuevos fragmentos
        for i, chunk in enumerate(note_entry["chunks"]):
            chunk_key = f"note:{note_entry['path']}:chunk:{i}"
            self.search_index[chunk_key] = {
                "note_path": note_entry["path"],
                "chunk_index": i,
                "content": chunk,
                "score": 1.0  # Puntuación base
            }

            # Indexar palabras clave
            words = re.findall(r'\b\w{3,}\b', chunk.lower())
            for word in words:
                word_key = f"word:{word}"
                if word_key not in self.search_index:
                    self.search_index[word_key] = {
                        "type": "word",
                        "word": word,
                        "references": []
                    }

                # Añadir referencia al fragmento
                self.search_index[word_key]["references"].append(chunk_key)

    def search_notes(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Buscar notas en la base de conocimiento.
        Retorna una lista de fragmentos relevantes.
        """
        if not query or not self.search_index:
            return []

        # Procesar la consulta
        words = re.findall(r'\b\w{3,}\b', query.lower())
        if not words:
            return []

        # Buscar palabras clave en el índice
        results = {}
        for word in words:
            word_key = f"word:{word}"
            if word_key in self.search_index:
                for ref in self.search_index[word_key]["references"]:
                    if ref not in results:
                        results[ref] = 0
                    results[ref] += 1

        # Ordenar resultados por relevancia
        scored_results = []
        for ref, score in results.items():
            entry = self.search_index.get(ref, {})
            if entry and "note_path" in entry:
                note_path = entry["note_path"]
                chunk_index = entry.get("chunk_index", 0)
                content = entry.get("content", "")

                # Calcular puntuación final
                final_score = score * (1.0 + (1.0 / (chunk_index + 1)))

                scored_results.append({
                    "ref": ref,
                    "note_path": note_path,
                    "chunk_index": chunk_index,
                    "content": content,
                    "score": final_score,
                    "note": self.knowledge_base.get(note_path, {})
                })

        # Ordenar por puntuación (descendente)
        scored_results.sort(key=lambda x: x["score"], reverse=True)

        # Limitar resultados
        return scored_results[:limit]

    def get_note_by_path(self, note_path: str) -> Optional[Dict]:
        """Obtener una nota completa por su ruta."""
        return self.knowledge_base.get(note_path)

    def get_note_preview(self, note_path: str, length: int = 200) -> Optional[str]:
        """Obtener un preview de una nota."""
        note = self.get_note_by_path(note_path)
        if note and "content" in note:
            return note["content"][:length] + ("..." if len(note["content"]) > length else "")
        return None

def main():
    """Interfaz de línea de comandos para el indexador de Obsidian."""
    print("""
    📚 OBSIDIAN LINK - INDEXADOR DE NOTAS
    ====================================
    """)

    # Solicitar ruta de la bóveda
    vault_path = input("📁 Ruta de tu bóveda de Obsidian (ej: C:/Users/User/ObsidianVault): ").strip()
    if not vault_path:
        vault_path = "C:/Users/User/ObsidianVault"  # Valor por defecto

    try:
        # Crear indexador
        indexer = ObsidianIndexer(vault_path)

        # Verificar si ya hay una base de conocimiento
        if indexer.knowledge_base:
            print(f"\n📊 Base de conocimiento existente encontrada ({len(indexer.knowledge_base)} notas)")
            print(f"   Última indexación: {indexer.last_indexed}")
        else:
            print(f"\n⚠️  No se encontró base de conocimiento. Se creará una nueva.")

        # Preguntar si quiere indexar
        while True:
            action = input("\n🔍 ¿Qué deseas hacer?\n"
                          "1. Indexar bóveda completa\n"
                          "2. Buscar en notas indexadas\n"
                          "3. Salir\n"
                          "Opción: ").strip()

            if action == "1":
                print("\n🔄 Indexando bóveda de Obsidian...")
                start_time = time.time()
                stats = indexer.index_vault()
                elapsed = time.time() - start_time

                print(f"\n📊 Estadísticas de indexación:")
                print(f"   Archivos totales: {stats['total_files']}")
                print(f"   Archivos indexados: {stats['indexed_files']}")
                print(f"   Nuevos archivos: {stats['new_files']}")
                print(f"   Archivos actualizados: {stats['updated_files']}")
                print(f"   Archivos saltados: {stats['skipped_files']}")
                print(f"   Errores: {stats['error_files']}")
                print(f"   Tiempo transcurrido: {elapsed:.2f} segundos")

                print(f"\n🎉 Indexación completada. Base de conocimiento actualizada con {len(indexer.knowledge_base)} notas.")

            elif action == "2":
                if not indexer.knowledge_base:
                    print("⚠️  No hay notas indexadas. Primero indexa la bóveda.")
                    continue

                query = input("\n🔍 Consulta de búsqueda (ej: 'shadow core osint'): ").strip()
                if not query:
                    print("⚠️  Por favor ingresa una consulta.")
                    continue

                print("\n🔍 Buscando en notas...")
                results = indexer.search_notes(query)

                if not results:
                    print("❌ No se encontraron resultados.")
                    continue

                print(f"\n📌 Resultados ({len(results)}):")
                for i, result in enumerate(results, 1):
                    note = result["note"]
                    print(f"\n{i}. {note.get('title', 'Nota sin título')}")
                    print(f"   Ruta: {result['note_path']}")
                    print(f"   Puntuación: {result['score']:.2f}")
                    print(f"   Fragmento: {result['content'][:100]}...")

                    if input("\n📖 ¿Ver nota completa? (s/n): ").lower() == 's':
                        preview = indexer.get_note_preview(result["note_path"], 500)
                        if preview:
                            print(f"\n📄 Contenido de la nota:")
                            print(preview)
                        else:
                            print("⚠️  No se pudo obtener el preview de la nota.")

            elif action == "3":
                print("\n👋 Saliendo del indexador de Obsidian.")
                break

            else:
                print("⚠️  Opción no válida. Intenta nuevamente.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Verifica que la ruta de la bóveda sea correcta y que los archivos .md sean accesibles.")

if __name__ == "__main__":
    main()