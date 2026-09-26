"""
test_evolutionary_memory.py - Prueba del sistema de aprendizaje evolutivo de AURA
Simula decisiones de aprobación/rechazo y verifica que el perfil se ajuste.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "Shadow-Core"))

from user_learning_profile import log_decision, generate_and_save_profile, print_profile_summary
import logging

logging.basicConfig(level=logging.INFO)

def simulate_decisions():
    """Simula decisiones para probar las reglas de aprendizaje."""
    
    print("=" * 60)
    print("🧠 PRUEBA DEL SISTEMA DE APRENDIZAJE EVOLUTIVO")
    print("=" * 60)
    
    # ===== PASO 1: Probar 3 rechazos del mismo tipo → auto-mute =====
    print("\n📛 PASO 1: 3 rechazos del mismo tipo → auto-mute")
    print("-" * 40)
    
    for i in range(3):
        decision = {
            'id': f"test_reject_{i}",
            'type': 'security_news',
            'source': 'test_simulation',
            'threat_level': 2,
            'title': f'Noticia de seguridad rechazada #{i+1}',
        }
        log_decision('REJECTED', decision)
        print(f"  ❌ Rechazo #{i+1}: security_news (threat: 2)")
    
    # ===== PASO 2: Probar 3 aprobaciones de otro tipo → boost prioridad =====
    print("\n⬆ PASO 2: 3 aprobaciones del mismo tipo → boost prioridad")
    print("-" * 40)
    
    for i in range(3):
        decision = {
            'id': f"test_approve_{i}",
            'type': 'phishing',
            'source': 'test_simulation',
            'threat_level': 6,
            'title': f'Alerta de phishing aprobada #{i+1}',
        }
        log_decision('APPROVED', decision)
        print(f"  ✅ Aprobación #{i+1}: phishing (threat: 6)")
    
    # ===== PASO 3: Probar auto-ejecución (Ghost Mode) =====
    print("\n👻 PASO 3: 2 auto-ejecuciones (Ghost Mode)")
    print("-" * 40)
    
    for i in range(2):
        decision = {
            'id': f"test_auto_{i}",
            'type': 'info_log',
            'source': 'test_simulation',
            'threat_level': 1,
            'title': f'Log informativo auto-ejecutado #{i+1}',
        }
        log_decision('AUTO', decision)
        print(f"  🤖 Auto-ejecución #{i+1}: info_log (threat: 1)")
    
    # ===== PASO 4: Generar perfil y mostrar resultados =====
    print("\n" + "=" * 60)
    print("📊 GENERANDO PERFIL DE USUARIO ACTUALIZADO...")
    print("=" * 60)
    
    result = generate_and_save_profile()
    print_profile_summary(result)
    
    # ===== VERIFICACIÓN DETALLADA =====
    print("\n" + "=" * 60)
    print("🔍 VERIFICACIÓN DETALLADA")
    print("=" * 60)
    
    profile = result.get('profile', {})
    adjustments = result.get('adjustments', {})
    
    # Verificar auto-mute
    auto_mute = adjustments.get('auto_mute', {})
    print(f"\n📛 AUTO-MUTE activos: {len(auto_mute)}")
    if 'security_news' in auto_mute:
        print("   ✅ security_news → AUTO-MUTE ACTIVADO (3 rechazos)")
    else:
        print("   ❌ security_news → NO AUTO-MUTE (error)")
    
    # Verificar boost de prioridad  
    priority_boost = adjustments.get('priority_boost', {})
    print(f"\n⬆ PRIORIDAD AUMENTADA: {len(priority_boost)}")
    if 'phishing' in priority_boost:
        boost_value = priority_boost['phishing']
        print(f"   ✅ phishing → PRIORIDAD +{boost_value} (3 aprobaciones)")
    else:
        print("   ❌ phishing → SIN BOOST (error)")
    
    # Verificar umbral Ghost Mode
    ghost_threshold = adjustments.get('ghost_mode_threshold', 4)
    print(f"\n👻 Umbral Ghost Mode: {ghost_threshold}")
    print(f"   Decisiones analizadas: {profile.get('total_decisions_analyzed', 0)}")
    print(f"   Tasa de aprobación: {profile.get('approval_rate', '?')}%")
    
    # Verificar estadísticas
    patterns = profile.get('patterns', {})
    print(f"\n📈 ESTADÍSTICAS:")
    print(f"   Aprobadas: {dict(patterns.get('approved', {}))}")
    print(f"   Rechazadas: {dict(patterns.get('rejected', {}))}")
    print(f"   Auto-ejecutadas: {dict(patterns.get('auto', {}))}")
    
    # ===== RESUMEN FINAL =====
    print("\n" + "=" * 60)
    print("✅ RESULTADO DE LA PRUEBA")
    print("=" * 60)
    
    if len(auto_mute) >= 1 and len(priority_boost) >= 1:
        print("\n🎉 AURA ha aprendido de tus preferencias:")
        print("   - 📛 Los 'security_news' de bajo riesgo se descartarán automáticamente")
        print("   - ⬆ Las 'phishing' de alto riesgo tendrán prioridad aumentada")
        print("   - 👻 El umbral de Ghost Mode se ajustó según tu tasa de aprobación")
        print("\n✅ PRUEBA COMPLETADA CON ÉXITO")
    else:
        print("\n⚠️ Algunas reglas no se activaron. Verifica los logs.")
    
    print("=" * 60)

if __name__ == "__main__":
    simulate_decisions()