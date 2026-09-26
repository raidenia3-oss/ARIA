#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AURA Crash Overseer — Supervisor de reinicios y auto-diagnóstico.
Encapsulado en `AuraEmergencyShield` para aislamiento de variables y
reglas estrictas de no interacción con el motor de evolución por ahora.
"""
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER_SCRIPT = ROOT / 'AME_Core' / 'servidor_ame.py'
OVERSEER_LOG = ROOT / 'AURA_Core' / 'logs' / 'crash_overseer.log'
EMERGENCY_LOG = ROOT / 'knowledge_base' / 'emergency_shield.log'
LOG_CANDIDATES = [
    ROOT / 'AURA_Core' / 'logs' / 'aura-error.log',
    ROOT / 'AURA_Core' / 'logs' / 'aura-out.log',
    ROOT / 'logs' / 'aura-error.log',
    ROOT / 'logs' / 'aura-out.log',
    ROOT / 'error.log',
    ROOT / 'AME_Core' / 'logs' / 'error.log'
]
MAX_CRASHES = 3
CRASH_WINDOW_SECONDS = 60
RESTART_DELAY_SECONDS = 5


class AuraEmergencyShield:
    """Clase aislada que supervisa el servidor Flask y protege contra bucles.

    Reglas de aislamiento aplicadas:
    - No llamar a `evolution_core.py` ni escribir en `proposed_upgrades.json`.
    - Registrar incidentes en `knowledge_base/emergency_shield.log` solamente.
    """

    def __init__(self):
        self.root = ROOT
        self.server_script = SERVER_SCRIPT
        self.overseer_log = OVERSEER_LOG
        self.emergency_log = EMERGENCY_LOG
        self.log_candidates = LOG_CANDIDATES
        self.max_crashes = MAX_CRASHES
        self.crash_window = CRASH_WINDOW_SECONDS
        self.restart_delay = RESTART_DELAY_SECONDS
        # Circuit breaker state
        self.circuit_state = 'CLOSED'  # other state: 'OPEN_CIRCUIT'
        self.max_crash_attempts = MAX_CRASHES
        self.time_window = CRASH_WINDOW_SECONDS
        # Ensure directories exist
        try:
            self.overseer_log.parent.mkdir(parents=True, exist_ok=True)
            self.emergency_log.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _log(self, message: str):
        ts = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        line = f'[{ts}] {message}'
        print(line)
        try:
            with open(self.overseer_log, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except Exception:
            pass

    def _write_emergency_log(self, exit_code: int, analysis: dict):
        """Escribe un registro pasivo en `knowledge_base/emergency_shield.log`.
        Contendrá timestamp, exit_code, diagnosis y fix sugerido.
        """
        ts = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        lines = [
            f'[{ts}] CRASH detected - exit_code={exit_code}',
            f"Severity: {analysis.get('severity', 'UNKNOWN')}",
            f"Diagnosis: {analysis.get('diagnosis', '')}",
            f"ProposedFix: {analysis.get('fix', '')}",
            '---'
        ]
        try:
            with open(self.emergency_log, 'a', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
            self._log(f'✅ Emergency shield logged incident to {self.emergency_log}')
        except Exception:
            self._log('⚠️  No se pudo escribir en emergency log')

    def _read_last_lines(self, path: Path, count: int = 50):
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.read().splitlines()
                    return lines[-count:]
        except Exception:
            pass
        return []

    def _find_trace_source(self):
        for candidate in self.log_candidates:
            if candidate.exists():
                return candidate
        return None

    def _extract_failure_trace(self, output: str):
        if output:
            lines = output.splitlines()
            if lines:
                return lines[-50:]
        path = self._find_trace_source()
        if path:
            return self._read_last_lines(path, 50)
        return ['No se encontró traza de error en los logs.']

    def _analyze_traceback(self, trace_lines):
        # Función interna de análisis (simula lógica de Mistral localmente)
        trace_text = '\n'.join(trace_lines)
        diagnosis = 'Se detectó un fallo en el servidor Flask.'
        fix = 'Revisar la traza y corregir el módulo responsable.'
        severity = 'HIGH'
        target = str(self.server_script)

        if 'ModuleNotFoundError' in trace_text or 'No module named' in trace_text:
            imported = 'unknown'
            for line in trace_lines:
                if 'ModuleNotFoundError' in line or 'No module named' in line:
                    imported = line.strip()
                    break
            diagnosis = f'Módulo faltante detectado: {imported}.'
            fix = ('Instalar el paquete faltante o corregir el import. ' 
                   'Ejecutar `pip install <paquete>` o ajustar el nombre del módulo en el código.')
            target = 'dependencies / imports'
        elif 'ImportError' in trace_text:
            diagnosis = 'ImportError detectado en la inicialización del servidor.'
            fix = 'Verificar rutas y dependencias importadas en AME_Core/servidor_ame.py.'
            target = str(self.server_script)
        elif 'SyntaxError' in trace_text:
            diagnosis = 'Error de sintaxis detectado en el código Python.'
            fix = 'Corregir la línea señalada en la traza de error.'
        elif 'FileNotFoundError' in trace_text:
            diagnosis = 'Archivo o recurso no encontrado durante el arranque.'
            fix = 'Asegurar que las rutas de recursos y plantillas existen y son accesibles.'
        elif 'TypeError' in trace_text:
            diagnosis = 'TypeError grave durante el arranque del servidor.'
            fix = 'Verificar tipos de datos y llamadas a funciones en la traza señalada.'
        elif 'OSError' in trace_text or 'PermissionError' in trace_text:
            diagnosis = 'Error de sistema: permisos o recursos no disponibles.'
            fix = 'Validar permisos de archivos/directorios y reiniciar con acceso correcto.'
        else:
            diagnosis = 'La traza no fue categorizada automáticamente, requiere revisión manual.'
            fix = 'Analizar el stack trace completo y aplicar el parche crítico necesario.'
            severity = 'HIGH'

        return {
            'severity': severity,
            'diagnosis': diagnosis,
            'fix': fix,
            'target': target,
            'trace': trace_lines
        }

    def _freeze_restarts(self, crash_count, trace_lines, exit_code):
        analysis = self._analyze_traceback(trace_lines)
        # Por ahora NO escribimos en proposed_upgrades.json ni contactamos evolution_core
        # Solo registramos de forma pasiva en el emergency log.
        self._write_emergency_log(exit_code, analysis)
        self._log('❄️ Reinicios automáticos congelados tras detectar bucle de crash.')

    def _open_circuit(self, crash_count, trace_lines, exit_code):
        """Activa el disyuntor: genera EMERGENCY_LOCK.txt y sale con código 1."""
        # Mark circuit state
        try:
            self.circuit_state = 'OPEN_CIRCUIT'
        except Exception:
            pass

        # Keep passive logs and emergency shield entry
        self._freeze_restarts(crash_count, trace_lines, exit_code)

        # Write emergency lock file at repository root
        lock_path = ROOT / 'EMERGENCY_LOCK.txt'
        try:
            with open(lock_path, 'w', encoding='utf-8') as f:
                f.write('AURA bloqueado preventivamente por colapso continuo. Bucle infinito evitado con éxito.')
            self._log(f'🔒 EMERGENCY_LOCK written to {lock_path}')
        except Exception:
            self._log('⚠️ No se pudo escribir EMERGENCY_LOCK.txt')

        # Exit immediately to avoid further restarts
        sys.exit(1)

    def run(self):
        if not self.server_script.exists():
            self._log(f'❌ No se encontró el servidor objetivo: {self.server_script}')
            sys.exit(1)

        self._log('🔧 AURA Crash Overseer iniciado. Supervisando servidor Flask...')
        crash_timestamps = []
        while True:
            if len(crash_timestamps) > 0:
                window_start = time.time() - self.crash_window
                crash_timestamps = [t for t in crash_timestamps if t >= window_start]

            self._log(f'▶️ Lanzando servidor: {self.server_script}')
            process = subprocess.Popen(
                [sys.executable, str(self.server_script)],
                cwd=self.server_script.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            stdout, _ = process.communicate()
            exit_code = process.returncode
            now = time.time()

            if exit_code == 0:
                self._log('✅ El servidor terminó sin errores. No hay reinicios pendentes.')
                break

            crash_timestamps.append(now)
            crash_count = len([t for t in crash_timestamps if t >= now - self.crash_window])
            trace_lines = self._extract_failure_trace(stdout)
            self._log(f'🔥 Se detectó crash #{crash_count} con código {exit_code}.')

            if crash_count > self.max_crashes:
                self._log('🚫 Umbral de reinicios superado. Congelando autorestart.');
                self._freeze_restarts(crash_count, trace_lines, exit_code)
                break

            self._log(f'⏳ Reinicio programado en {self.restart_delay}s...')
            time.sleep(self.restart_delay)


def main():
    shield = AuraEmergencyShield()
    shield.run()


if __name__ == '__main__':
    if '--dry-run' in sys.argv:
        s = AuraEmergencyShield()
        s._log(f'DRY RUN: servidor objetivo = {s.server_script}')
        s._log(f'Root path = {s.root}')
        sys.exit(0)
    try:
        main()
    except KeyboardInterrupt:
        print('✋ Interrupción manual recibida. Saliendo.')
        sys.exit(0)
    except Exception as exc:
        print(f'❌ Error inesperado del Crash Overseer: {exc}')
        sys.exit(1)
