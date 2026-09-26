import os
import time
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

# 1. Configuración de Firebase
cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://aura-protector-98b7e-default-rtdb.firebaseio.com/' # <--- CAMBIA ESTO
})

# Referencia a la sección de alertas en tu base de datos
ref_alertas = db.reference('aura/escudo/alertas')
ref_estado = db.reference('aura/escudo/estado')

def check_connections():
    print("[🛡️ AURA MONITOR] Vigilando actividad...")
    connections = os.popen("netstat -tuln").read()
    
    # Marcamos que el búnker está online en Firebase
    ref_estado.set({
        'last_check': time.ctime(),
        'status': 'Protegido'
    })

    # Detección de puertos sospechosos
    puertos_rat = ["4444", "5555", "8888"]
    for puerto in puertos_rat:
        if puerto in connections:
            print(f"⚠️ ¡PELIGRO! Puerto {puerto} detectado.")
            # ENVIAR ALERTA A FIREBASE
            ref_alertas.push({
                'timestamp': time.ctime(),
                'puerto': puerto,
                'mensaje': "Actividad sospechosa detectada en el Búnker",
                'nivel': "CRITICO"
            })

# Ejecutar la revisión una sola vez para la nube
try:
    check_connections()
    print("[🛡️ AURA] Revisión completada con éxito.")
except Exception as e:
    print(f"Error de conexión: {e}")