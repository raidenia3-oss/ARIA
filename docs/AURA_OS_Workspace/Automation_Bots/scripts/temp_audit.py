import os, json
from pathlib import Path

# 1 ESCANEO GLOBAL Y RECOLECCIÓN DE ACTIVOS
root = Path(".")
ame_files = []
for p in root.rglob("*"):
    if p.is_file() and any(
        x in p.parts
        for x in [
            "AME_Core",
            "AME_ECOSYSTEM",
            "AME-termux",
            "AME_EXPORT_PACKAGE",
            "AME_Agent",
            "AME_Core",
        ]
    ):
        ame_files.append(str(p))

# Resumen por tipo
exts = {}
for f in ame_files:
    e = Path(f).suffix.lower() or "(no ext)"
    exts[e] = exts.get(e, 0) + 1

report_content = "=== BUILD READY REPORT: AME Android ===\n"
report_content += (
    "Fecha: "
    + os.popen("date /t").read().strip()
    + " "
    + os.popen("time /t").read().strip()
    + "\n\n"
)
report_content += "1) ESCANEO GLOBAL Y ACTIVOS\n"
report_content += f"- Total archivos AME: {len(ame_files)}\n"
report_content += "  Extensiones principales:\n"
for k, v in sorted(exts.items(), key=lambda x: x[1], reverse=True)[:15]:
    report_content += f"    {k}: {v}\n"

# Módulos Java principales detectados dinámicamente
java_modules_path = Path("AME_ECOSYSTEM/ame_app_android/app/src/main/java/com/ame/ecosystem")
java_files = sorted(
    [
        str(f.relative_to(java_modules_path))
        for f in java_modules_path.rglob("*.java")
        if f.is_file()
    ]
)
report_content += "\n- Módulos Java principales:\n"
for jf in java_files:
    report_content += f"  - {jf}\n"

# Recursos UI y lógicos
ui_js_files = sorted([str(p) for p in root.rglob("AME_Core/static/js/*.js")])
ui_css_files = sorted([str(p) for p in root.rglob("AME_Core/static/css/*.css")])
ui_html_files = sorted([str(p) for p in root.rglob("AME_Core/templates/*.html")])

if ui_js_files:
    report_content += "\n- Archivos JS de interfaz:\n"
    for f in ui_js_files:
        report_content += f"  - {f}\n"
if ui_css_files:
    report_content += "\n- Archivos CSS de interfaz:\n"
    for f in ui_css_files:
        report_content += f"  - {f}\n"
if ui_html_files:
    report_content += "\n- Archivos HTML de plantillas:\n"
    for f in ui_html_files:
        report_content += f"  - {f}\n"

python_modules = sorted(
    [str(p) for p in root.rglob("AURA_Core/modules/**/*.py")]
    + [str(p) for p in root.rglob("AURA_Core/nodes/**/*.py")]
)
if python_modules:
    report_content += "\n- Módulos Python (lógica de backend/nodos):\n"
    for f in python_modules:
        report_content += f"  - {f}\n"


report_content += "\n2) CONFIGURACIÓN Android / AUDITORÍA\n"
# 2 VERIFICAR DEPENDENCIAS EN build.gradle
with open("AME_ECOSYSTEM/ame_app_android/app/build.gradle") as f:
    gradle = f.read()

# Dependencias declaradas
import re

declared = re.findall(r"implementation\s+['\"]([^'\"]+)['\"]", gradle)
report_content += "  Configuración Gradle app: AME_ECOSYSTEM/ame_app_android/app/build.gradle\n"
report_content += "    Dependencias actuales:\n"
for d in declared:
    report_content += f"      - {d}\n"

# Librerías críticas faltantes detectadas
needed = {
    "com.squareup.okhttp3:okhttp": "4.12.0",
    "com.google.code.gson:gson": "2.10.1",
    "androidx.biometric:biometric": "1.1.0",
    "androidx.work:work-runtime-ktx": "2.9.0",
    "androidx.core:core-ktx": "1.13.1",
    "androidx.activity:activity-ktx": "1.9.0",
    "androidx.fragment:fragment-ktx": "1.8.0",
    "com.google.android.gms:play-services-base": "18.5.0",
    "androidx.lifecycle:lifecycle-livedata-ktx": "2.6.1",  # Added to cover common cases
    "androidx.lifecycle:lifecycle-viewmodel-ktx": "2.6.1",  # Already there
    "androidx.lifecycle:lifecycle-runtime-ktx": "2.6.1",  # Already there
    "com.google.android.gms:play-services-mlkit-barcode-scanning": "18.3.0",  # Already there
}
missing = []
for lib, ver in needed.items():
    if not any(lib in d for d in declared):
        missing.append((lib, ver))

if missing:
    report_content += "\n  Dependencias adicionales requeridas:\n"
    for lib, ver in missing:
        report_content += f"    - {lib}:{ver}\n"
else:
    report_content += "\n  No se detectan dependencias críticas faltantes.\n"

# 3 PERMISOS AndroidManifest
with open("AME_ECOSYSTEM/ame_app_android/app/src/main/AndroidManifest.xml") as f:
    manifest = f.read()
perms = re.findall(r'<uses-permission\s+android:name="([^"]+)"', manifest)
report_content += "\n- AndroidManifest.xml:\n"
report_content += "  Permisos actuales:\n"
for p in perms:
    report_content += f"    - {p}\n"

critical_perms = [
    "android.permission.FOREGROUND_SERVICE",
    "android.permission.FOREGROUND_SERVICE_CAMERA",
    "android.permission.FOREGROUND_SERVICE_MICROPHONE",
    "android.permission.SYSTEM_ALERT_WINDOW",  # For overlay
    "android.permission.USE_BIOMETRIC",
    "android.permission.USE_FINGERPRINT",  # Biometric fallback
    "android.permission.RECEIVE_BOOT_COMPLETED",
    "android.permission.POST_NOTIFICATIONS",
    "android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS",
    "android.permission.SCHEDULE_EXACT_ALARM",
]
missing_perms = [p for p in critical_perms if p not in perms]

if missing_perms:
    report_content += "\n  Permisos críticos adicionales que deben estar:\n"
    for p in missing_perms:
        report_content += f"    - {p}\n"
else:
    report_content += "\n  No se detectan permisos críticos faltantes.\n"

# 3 LIMPIEZA ABSOLUTA
report_content += "\n3) LIMPIEZA ABSOLUTA\n"
report_content += "  Se requiere ejecutar desde AME_ECOSYSTEM/ame_app_android:\n"
report_content += "    ./gradlew clean\n"

# 4 COMPILACIÓN INCONDICIONAL
report_content += "\n4) COMPILACIÓN INCONDICIONAL\n"
report_content += "  Ejecutar desde AME_ECOSYSTEM/ame_app_android:\n"
report_content += "    ./gradlew assembleDebug\n"
report_content += "  En caso de error, revisar:\n"
report_content += "    - Falta JDK 17 / variables JAVA_HOME\n"
report_content += "    - NDK/SDK actualizados en local.properties\n"
report_content += "    - Conflictos de versiones Gson/OkHttp/Retrofit\n"
report_content += (
    "    - ProGuard/R8: mantener minifyEnabled=false en buildType debug (ya configurado)\n"
)

# 5 ENTREGA DEL ARTEFACTO
report_content += "\n5) ENTREGA DEL ARTEFACTO\n"
report_content += "  Ruta candidata del APK debug:\n"
report_content += "    AME_ECOSYSTEM/ame_app_android/app/build/outputs/apk/debug/app-debug.apk\n"
report_content += "  Copiar/renombrar a:\n"
report_content += "    AURA_Core/outputs/AME_Definitive_Latest.apk\n"
report_content += "  Contenido esperado del paquete compilado:\n"
report_content += "    - Módulos Java, APIs cliente, servicios, workers, lógica OSINT, chat (GBrain), táctica, recon, minería, HUD, biometría, WebSocket\n"
report_content += "    - Archivos de interfaz (layouts XML, drawables, mipmaps, assets HTML/JS/CSS si están en res/raw o assets/)\n"


with open("AURA_Core/outputs/build_ready_report.txt", "w") as f:
    f.write(report_content)

print(report_content)
