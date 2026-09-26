"""
Test de Diagnostico del Sistema de Auto-Mutacion
==================================================
Verifica que el entorno local se comunica con Ollama y que el
motor de auto-mutacion (SelfMutationEngine) funciona correctamente.
Ejecutar: python tests/test_mutation.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from neural.local_router import OllamaLocalRouter
from neural.self_mutation import SelfMutationEngine


async def test_main():
    print("=" * 60)
    print("[-] Iniciando Diagnostico de Red Neuronal Local...")
    print("=" * 60)

    router = OllamaLocalRouter()
    mutation_engine = SelfMutationEngine()

    # 1. Probar la inferencia con una tarea de diseno simple
    test_prompt = (
        "Genera una funcion de python llamada 'calcular_metricas_hud' "
        "que devuelva un diccionario con claves 'cpu', 'ram' simulados."
    )
    print("\n[-] Solicitando codigo a Qwen-Coder local (Ollama)...")
    generated_code = await router.generate_code(test_prompt)

    print("\n[+] Codigo Recibido de la IA:")
    print(generated_code)
    print("-" * 40)

    # 2. Validar sintaxis y guardar en caliente
    print("[-] Pasando codigo por el filtro de seguridad AST...")
    success = mutation_engine.write_new_module("hud_metrics", generated_code)

    if success:
        # 3. Importar dinamicamente el codigo que la IA acaba de escribir
        module = mutation_engine.hot_reload("hud_metrics")
        if module and hasattr(module, "calcular_metricas_hud"):
            resultado = module.calcular_metricas_hud()
            print(f"[✓] EXITO GLOBAL: Modulo autogenerado y ejecutado. Resultado: {resultado}")
        else:
            print("[!] El modulo cargo pero carece de la funcion esperada.")
    else:
        print("[!] Abortado: El codigo de la IA contenia errores criticos de compilacion.")

    print("\n" + "=" * 60)
    print("Diagnostico completado")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_main())
