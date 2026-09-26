#!/usr/bin/env python3
"""
Demostración del sistema de failover de AURA.
Muestra cómo el router elige el mejor proveedor automáticamente.
"""
import sys
from pathlib import Path

# Agregar AURA_Core al path
sys.path.insert(0, str(Path(__file__).parent / "AURA_Core"))

from ai_router import AuraCognitiveRouter

def main():
    print("=" * 80)
    print("🚀 DEMOSTRACIÓN DE SISTEMA DE FAILOVER DE AURA")
    print("=" * 80)
    print()
    
    router = AuraCognitiveRouter()
    
    # Test 1: Información de proveedores
    print("📋 PROVEEDORES DISPONIBLES:")
    providers = router.list_available_providers()
    for i, p in enumerate(providers, 1):
        if p.get("type") == "local":
            print(f"   {i}. {p['name'].upper()} (Local)")
        else:
            print(f"   {i}. {p['name']} (Cloud API)")
    print()
    
    # Test 2: Prueba de ruteo con failover
    print("-" * 80)
    print("🧪 PRUEBA DE RUTEO AUTOMÁTICO:")
    print("-" * 80)
    
    test_prompts = [
        ("¿Cómo funciona Python?", "Pregunta general - ruteo normal"),
        ("Escribe un bucle en JavaScript", "Código - detección de tarea específica"),
        ("Explica paso a paso cuál es la capital de Francia", "Razonamiento - tarea compleja"),
    ]
    
    for prompt, description in test_prompts:
        print(f"\n📝 {description}")
        print(f"   Prompt: '{prompt}'")
        
        # Detectar tipo de tarea
        task_type = router._detect_task_type(prompt)
        best_model = router._get_best_model(prompt)
        print(f"   → Tarea detectada: {task_type}")
        print(f"   → Modelo Ollama seleccionado: {best_model}")
        
        # Hacer la llamada con failover
        print(f"   → Buscando proveedor disponible...")
        result = router.route(prompt)
        
        if result["response"]:
            provider = result.get("provider", "?")
            model = result.get("model", "?")
            print(f"   ✓ Respuesta obtenida desde: {provider} ({model})")
            print(f"   ✓ Primeras 60 caracteres: {result['response'][:60]}...")
            
            # Mostrar info de failover si se usó
            if result.get("fallback_info"):
                fb = result["fallback_info"]
                if len(fb["attempted"]) > 1:
                    print(f"   ℹ️  Failover: Intentó {fb['attempted']}")
        else:
            print(f"   ✗ No se pudo obtener respuesta")
            print(f"   Error: {result.get('error', 'desconocido')}")
    
    print()
    print("=" * 80)
    print("✅ DEMOSTRACIÓN COMPLETADA")
    print("=" * 80)
    print()
    print("💡 NOTAS:")
    print("   • El router intenta Ollama primero (mejor rendimiento)")
    print("   • Si Ollama no está disponible, usa APIs cloud en orden de prioridad")
    print("   • Failover automático: Si un proveedor falla, intenta el siguiente")
    print("   • Las claves de API nunca se exponen en los logs")
    print()

if __name__ == "__main__":
    main()
