import os
path = 'AME_Core/servidor_ame.py'
c = open(path, 'r', encoding='utf-8').read()
m = 'print(f"⚠️  No se pudo iniciar WiFi watchdog: {e}")'
inj = m + '\n\n# --- Registrar endpoints biometricos ---\ntry:\n    from biometric_endpoints import register_biometric_routes\n    register_biometric_routes(app)\n    print("Endpoints biometricos registrados")\nexcept ImportError as e:\n    print("biometric_endpoints no encontrado:", e)\nexcept Exception as e:\n    print("Error registrando endpoints biometricos:", e)'
n = c.count('register_biometric_routes(app)')
print(f'count={n}')
if m in c and n == 0:
    c = c.replace(m, inj, 1)
    open(path, 'w', encoding='utf-8').write(c)
    print('INJECTED')
else:
    print('SKIPPED')
import ast
ast.parse(c)
print('SYNTAX OK')