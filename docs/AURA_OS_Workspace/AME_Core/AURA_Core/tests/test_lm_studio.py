"""
Test de Diagnostico — LM Studio + Self-Mutation Engine
=======================================================
Verifica que AURA pueda comunicarse con LM Studio (puerto 1234)
y ejecutar su primera auto-mutacion de sintaxis.
Ejecutar: python tests/test_lm_studio.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from neural.local_router import LMStudioLocalRouter
from neural.self_mutation import SelfMutationEngine


async def main():
    print("=" * 60)
    print("[-] Conectando con el servidor local de LM Studio...")
    print("=" * 60)

    router = LMStudioLocalRouter()
    mutation_engine = SelfMutationEngine()

    test_prompt = (
        "Crea una funcion llamada 'actualizar_interfaz' que imprima 'HUD de AME mutado con exito'."
    )

    print("\n[-] Solicitando codigo al modelo cargado en LM Studio...")
    generated_code = await router.generate_code(test_prompt)

    print("\n[+] Codigo generado por la IA:")
    print(generated_code)
    print("-" * 50)

    if generated_code.startswith("ERROR"):
        print(f"\n[!] {generated_code}")
        print("\n   Asegurate de que LM Studio este corriendo con:")
        print("   1. Abre LM Studio")
        print("   2. Carga un modelo (Qwen 2.5 Coder 7B o similar)")
        print("   3. Ve a la pestana del servidor web (icono antena)")
        print("   4. Verifica que el puerto sea 1234")
        print("   5. Presiona 'Start Server'")
        return

    print("\n[-] Validando estructura con el motor AST...")
    success = mutation_engine.write_new_module("ame_hud_update", generated_code)

    if success:
        modulo = mutation_engine.hot_reload("ame_hud_update")
        if modulo and hasattr(modulo, "actualizar_interfaz"):
            print("\n[✓] TEST COMPLETADO: El codigo se valido, guardo e importo en caliente.")
            print("    Ejecutando funcion generada por IA:")
            modulo.actualizar_interfaz()
        else:
            print("\n[!] Modulo importado pero no se encontro la funcion 'actualizar_interfaz'.")
    else:
        print("\n[!] Error: El codigo devuelto no es Python valido.")

    print("\n" + "=" * 60)
    print("Diagnostico completado")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
