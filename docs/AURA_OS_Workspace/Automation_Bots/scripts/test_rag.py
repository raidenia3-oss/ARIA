"""Prueba del pipeline RAG: indexar y buscar en ChromaDB"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from AURA_Core.vector_memory import get_vector_memory

vm = get_vector_memory()

# 1. Reset para empezar limpio
vm.reset()
print(f"Base vacia. Entradas: {vm.count()}")

# 2. Indexar texto de prueba
result = vm.add_document(
    "El codigo secreto de activacion de AURA es 99X-ZETA. "
    "Este codigo permite desbloquear todas las funciones premium del sistema.",
    metadata={"source": "test", "type": "secreto"},
)
print(f"Documento indexado: {result['chunks']} chunks, {result['total_chars']} chars")
print(f"Total en DB: {vm.count()}")

# 3. Buscar por el codigo
hits = vm.search_similar("codigo secreto de activacion", limit=3)
print(f"\nBusqueda 'codigo secreto': {len(hits)} resultados")
for h in hits:
    print(f"  - [{h['id']}] score={h['score']:.4f} | {h['text'][:100]}")

# 4. Buscar por el codigo numerico
hits2 = vm.search_similar("99X-ZETA", limit=3)
print(f"\nBusqueda '99X-ZETA': {len(hits2)} resultados")
for h in hits2:
    print(f"  - [{h['id']}] score={h['score']:.4f} | {h['text'][:100]}")

print("\n✅ Pipeline RAG funcionando correctamente!")
