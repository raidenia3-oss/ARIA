#!/usr/bin/env python3
"""
Controlador de Android Studio para Cline.
Compila APK, instala en dispositivo, arregla errores comunes.
"""

import subprocess, os, sys, json, time, glob, shutil, asyncio
from pathlib import Path
from datetime import datetime

class AndroidStudioController:
    PROJECT_DIR = r"C:\Users\User\Downloads\AURA\android"
    AURA_DIR    = r"C:\Users\User\Downloads\AURA"
    OUTPUT_DIR  = r"C:\Users\User\Downloads\AURA\output"
    GRADLEW     = r"C:\Users\User\Downloads\AURA\android\gradlew.bat"

    def __init__(self):
        self.as_path  = self._find_android_studio()
        self.adb_path = self._find_adb()
        self.sdk_path = self._find_sdk()
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)

    def _find_android_studio(self) -> str:
        candidates = [
            r"C:\Program Files\Android\Android Studio\bin\studio64.exe",
            r"C:\Program Files\Android\Android Studio\bin\studio.exe",
            os.path.expandvars(
                r"%LOCALAPPDATA%\Programs\Android Studio\bin\studio64.exe"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        result = subprocess.run(
            ["where", "studio64"], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else ""

    def _find_adb(self) -> str:
        candidates = [
            os.path.expandvars(
                r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
            r"C:\Users\User\AppData\Local\Android\Sdk\platform-tools\adb.exe",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        result = subprocess.run(
            ["where", "adb"], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else "adb"

    def _find_sdk(self) -> str:
        candidates = [
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk"),
            r"C:\Users\User\AppData\Local\Android\Sdk",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return ""

    def status(self) -> dict:
        s = {
            "android_studio": self.as_path or "No encontrado",
            "adb":   self.adb_path or "No encontrado",
            "sdk":   self.sdk_path or "No encontrado",
            "project_exists": os.path.exists(self.PROJECT_DIR),
            "gradlew_exists": os.path.exists(self.GRADLEW),
        }
        if self.adb_path:
            r = subprocess.run([self.adb_path, "devices"],
                               capture_output=True, text=True)
            devices = [l for l in r.stdout.splitlines() if "\tdevice" in l]
            s["devices_connected"] = len(devices)
            s["devices"] = devices
        return s

    def open_project(self) -> bool:
        if not self.as_path:
            print("Android Studio no encontrado")
            return False
        subprocess.Popen([self.as_path, self.PROJECT_DIR])
        print(f"Android Studio abierto: {self.PROJECT_DIR}")
        return True

    def sync_capacitor(self) -> bool:
        print("Sincronizando Capacitor...")
        r1 = subprocess.run(["npm", "run", "build"], cwd=self.AURA_DIR,
                            shell=True, capture_output=True, text=True)
        if r1.returncode != 0:
            print(f"Build web falló: {r1.stderr[-500:]}")
            return False
        r2 = subprocess.run(["npx", "cap", "sync", "android"],
                            cwd=self.AURA_DIR, shell=True,
                            capture_output=True, text=True)
        if r2.returncode != 0:
            print(f"Cap sync falló: {r2.stderr[-500:]}")
            return False
        print("Capacitor sincronizado")
        return True

    def build_apk(self, release=False, sync_first=True) -> str | None:
        if sync_first and not self.sync_capacitor():
            return None
        task = "assembleRelease" if release else "assembleDebug"
        print(f"Compilando APK {'release' if release else 'debug'}...")
        start = time.time()
        result = subprocess.run([self.GRADLEW, task], cwd=self.PROJECT_DIR,
                                capture_output=True, text=True, shell=True)
        elapsed = round(time.time() - start)
        if result.returncode != 0:
            print(f"Build falló ({elapsed}s)")
            error = self._analyze_build_error(result.stderr)
            print(f"Causa: {error['cause']}\nSolución: {error['fix']}")
            return None
        apk = self._find_latest_apk(release)
        if apk:
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            out = os.path.join(
                self.OUTPUT_DIR,
                f"AME_{'release' if release else 'debug'}_{ts}.apk")
            shutil.copy(apk, out)
            size = os.path.getsize(out) // (1024*1024)
            print(f"APK compilado en {elapsed}s, {size}MB -> {out}")
            return out
        return None

    def _find_latest_apk(self, release=False) -> str | None:
        pattern = os.path.join(
            self.PROJECT_DIR, "app", "build", "outputs", "apk",
            "release" if release else "debug", "*.apk")
        apks = glob.glob(pattern)
        return max(apks, key=os.path.getmtime) if apks else None

    def _analyze_build_error(self, stderr: str) -> dict:
        errors = {
            "SDK location not found": {
                "cause": "ANDROID_HOME no configurado",
                "fix": "Crear local.properties con sdk.dir"},
            "Minimum supported Gradle": {
                "cause": "Gradle desactualizado",
                "fix": "Actualizar gradle-wrapper.properties"},
            "compileSdkVersion": {
                "cause": "SDK version no instalada",
                "fix": "Instalar SDK en Android Studio"},
            "JAVA_HOME": {
                "cause": "Java no encontrado",
                "fix": "Instalar JDK 17 desde adoptium.net"},
            "duplicate class": {
                "cause": "Dependencias duplicadas",
                "fix": "Ejecutar: gradlew dependencies"},
        }
        for key, solution in errors.items():
            if key in stderr:
                return solution
        return {"cause": "Error desconocido",
                "fix": "gradlew assembleDebug --stacktrace"}

    def fix_common_issues(self) -> None:
        print("Arreglando problemas comunes...")
        local_props = os.path.join(self.PROJECT_DIR, "local.properties")
        if not os.path.exists(local_props) and self.sdk_path:
            sdk = self.sdk_path.replace("\\", "\\\\")
            with open(local_props, "w") as f:
                f.write(f"sdk.dir={sdk}\n")
            print("local.properties creado")
        manifest = os.path.join(
            self.PROJECT_DIR, "app", "src", "main", "AndroidManifest.xml")
        if os.path.exists(manifest):
            with open(manifest) as f:
                content = f.read()
            needed = ["INTERNET", "ACCESS_NETWORK_STATE",
                      "ACCESS_FINE_LOCATION", "CAMERA", "RECORD_AUDIO",
                      "VIBRATE", "FOREGROUND_SERVICE"]
            missing = [p for p in needed
                       if f'android.permission.{p}' not in content]
            if missing:
                perms = "\n".join(
                    [f'<uses-permission android:name="android.permission.{p}"/>'
                     for p in missing])
                content = content.replace(
                    "<application", f"{perms}\n\n<application")
                with open(manifest, "w") as f:
                    f.write(content)
                print(f"Añadidos {len(missing)} permisos: {missing}")
        print("Revisión completada")

    def install_apk(self, apk_path: str) -> bool:
        if not self.adb_path:
            print("ADB no encontrado")
            return False
        print("Instalando APK via ADB...")
        r = subprocess.run([self.adb_path, "install", "-r", apk_path],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print("APK instalado")
            return True
        print(f"Error: {r.stderr}")
        return False

    async def send_apk_wireless(self, apk_path: str,
                                aura_ws="ws://localhost:8765"):
        import base64, websockets
        apk_data = Path(apk_path).read_bytes()
        b64 = base64.b64encode(apk_data).decode()
        chunk_size = 50000
        chunks = [b64[i:i+chunk_size]
                  for i in range(0, len(b64), chunk_size)]
        print(f"Enviando APK en {len(chunks)} partes...")
        try:
            async with websockets.connect(aura_ws) as ws:
                await ws.send(json.dumps({
                    "node": "BUILD_SYSTEM", "event": "APK_TRANSFER_START",
                    "payload": {"filename": os.path.basename(apk_path),
                                "total_chunks": len(chunks),
                                "size": len(apk_data)}}))
                for i, chunk in enumerate(chunks):
                    await ws.send(json.dumps({
                        "node": "BUILD_SYSTEM", "event": "APK_CHUNK",
                        "payload": {"index": i, "data": chunk,
                                    "total": len(chunks)}}))
                    if i % 10 == 0:
                        print(f"  {round((i/len(chunks))*100)}%")
                await ws.send(json.dumps({
                    "node": "BUILD_SYSTEM",
                    "event": "APK_TRANSFER_COMPLETE",
                    "payload": {"filename": os.path.basename(apk_path)}}))
                print("APK enviado")
        except Exception as e:
            print(f"Error: {e}")

    def get_logs(self, package="com.arquitecto.ame", lines=100) -> str:
        r = subprocess.run(
            [self.adb_path, "logcat", "-d", "-t", str(lines)],
            capture_output=True, text=True)
        return r.stdout

    def run_tests(self) -> dict:
        print("Corriendo tests...")
        r = subprocess.run(
            [self.GRADLEW, "connectedDebugAndroidTest"],
            cwd=self.PROJECT_DIR, capture_output=True, text=True, shell=True)
        return {"passed": r.returncode == 0, "output": r.stdout[-1000:]}