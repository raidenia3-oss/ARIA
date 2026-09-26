#!/usr/bin/env python3
"""
Memory Manager para AURA.
Usa ChromaDB para almacenar y recuperar información en una base de datos vectorial.
"""

import chromadb
from chromadb.utils import embedding_functions
import os
from datetime import datetime

class MemoryManager:
    def __init__(self, db_name="aura_memory_db"):
        self.client = chromadb.PersistentClient(path=db_name)
        self.collection = self.client.get_or_create_collection(name="aura_knowledge")

    def add_memory(self, content, metadata=None, embedding_function=None):
        """
        Añadir un nuevo elemento a la memoria vectorial.
        """
        if metadata is None:
            metadata = {
                "source": "user_input",
                "timestamp": datetime.now().isoformat(),
                "type": "knowledge"
            }

        if embedding_function is None:
            embedding_function = embedding_functions.DefaultEmbeddingFunction()

        self.collection.add(
            documents=[content],
            metadatas=[metadata],
            embeddings=[embedding_function([content])[0]]
        )
        print(f"📝 Memoria añadida: {metadata.get('source', 'desconocido')}")

    def query_memory(self, query, n_results=3):
        """
        Consultar la memoria vectorial para encontrar elementos similares.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results

    def get_all_memories(self):
        """
        Obtener todos los elementos almacenados en la memoria.
        """
        return self.collection.get()

    def delete_memory(self, ids):
        """
        Eliminar elementos específicos de la memoria.
        """
        self.collection.delete(ids=ids)
        print(f"🗑️ Memorias eliminadas: {len(ids)} elementos")

# Ejemplo de uso
if __name__ == "__main__":
    memory_manager = MemoryManager()

    # Añadir algunas memorias de ejemplo
    memory_manager.add_memory(
        content="Ejemplo de información sobre seguridad informática.",
        metadata={"source": "osint_report", "topic": "security"}
    )

    memory_manager.add_memory(
        content="Cómo usar gestos para controlar el dashboard táctico.",
        metadata={"source": "user_guide", "topic": "gestures"}
    )

    # Consultar la memoria
    results = memory_manager.query_memory("seguridad informática")
    print("🔍 Resultados de la consulta:")
    for i, (doc, meta, score) in enumerate(zip(results['documents'], results['metadatas'], results['distances'])):
        print(f"{i+1}. {doc[:50]}... (Score: {1 - score:.2f})")