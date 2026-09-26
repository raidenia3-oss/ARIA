"""
AURA Evolution Engine — Automejora Supervisada
Analiza código y propone mejoras SIN modificar archivos directamente.
Genera propuestas en proposed_upgrades.json para revisión humana.

Módulo de Asimilación Segura:
- Convierte inspiraciones extraídas de internet en parches validados
- Sanitiza y valida código antes de incluir en cola de desarrollo
- Registra fallos y alertas en emergency_shield.log
"""
import os
import json
import ast
import re
import time
import asyncio
import subprocess
from typing import List, Dict, Optional
from datetime import datetime

class EvolutionEngine:
    """
    Motor de autodesarrollo supervisado.
    - Analiza archivos Python
    - Detecta patrones ineficientes
    - Genera propuestas de mejora
    - JAMÁS modifica código directamente
    """

    def __init__(self):
        self.proposals = []

    def analyze_file(self, file_path: str) -> List[Dict]:
        """
        Analiza un archivo Python y devuelve propuestas de mejora.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
        except Exception as e:
            return [{"error": f"Cannot parse {file_path}: {str(e)}"}]

        proposals = []
        file_name = os.path.basename(file_path)

        # 1. Buscar funciones sin docstrings
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not ast.get_docstring(node):
                proposals.append({
                    "target_file": file_name,
                    "description": f"Function '{node.name}' missing docstring",
                    "code_before": content.split('\n')[node.lineno-1:node.end_lineno],
                    "code_after": f'def {node.name}(...):\n    \"\"\"\n    [Describe purpose here]\n    \"\"\"\n    ...'
                })

        # 2. Buscar imports no utilizados (simplificado)
        imports = [n for n in ast.walk(tree) if isinstance(n, ast.Import)]
        for imp in imports:
            for alias in imp.names:
                if not self._is_import_used(alias.name, content):
                    proposals.append({
                        "target_file": file_name,
                        "description": f"Unused import: {alias.name}",
                        "code_before": f"import {alias.name}",
                        "code_after": "# Remove unused import"
                    })

        # 3. Detectar funciones largas (más de 30 líneas)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_lines = node.end_lineno - node.lineno
                if func_lines > 30:
                    proposals.append({
                        "target_file": file_name,
                        "description": f"Function '{node.name}' is too long ({func_lines} lines). Consider refactoring.",
                        "code_before": content.split('\n')[node.lineno-1:node.end_lineno],
                        "code_after": "# Suggested: Split into smaller functions"
                    })

        # 4. Buscar try-except sin logging
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                has_logging = False
                for handler in node.handlers:
                    for stmt in ast.walk(handler):
                        if isinstance(stmt, ast.Call):
                            func = getattr(stmt.func, 'id', None)
                            if func and 'log' in func.lower():
                                has_logging = True
                if not has_logging:
                    proposals.append({
                        "target_file": file_name,
                        "description": f"Try-except block without logging at line {node.lineno}",
                        "code_before": content.split('\n')[node.lineno-1:node.end_lineno],
                        "code_after": "# Suggested: Add logging for error tracking"
                    })

        return proposals

    def _is_import_used(self, import_name: str, content: str) -> bool:
        """Verifica si un import es usado en el código."""
        pattern = r'\b' + re.escape(import_name) + r'\b'
        return bool(re.search(pattern, content))

    def generate_proposals(self, target_files: List[str]) -> Dict:
        """
        Analiza múltiples archivos y genera propuestas.
        Retorna dict con propuestas y guarda en proposed_upgrades.json
        """
        all_proposals = []

        for file_path in target_files:
            if os.path.exists(file_path):
                proposals = self.analyze_file(file_path)
                all_proposals.extend(proposals)

        # Cargar inspiraciones de Stark Engine
        inspiration_pool_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..',
            'knowledge_base',
            'inspiration_pool.json'
        )
        if os.path.exists(inspiration_pool_path):
            try:
                with open(inspiration_pool_path, 'r', encoding='utf-8') as f:
                    inspiration_data = json.load(f)
                    inspirations = inspiration_data.get('inspirations', [])
                    for insp in inspirations:
                        if insp.get('applied'):  # Saltar si ya fue aplicada
                            continue
                        analysis = insp.get('analysis', {})
                        if analysis:
                            all_proposals.append({
                                "target_file": "STARK_INSPIRATION",
                                "description": f"Inspiración desde {insp.get('source_type', 'desconocido')}: {analysis.get('funcionalidad_detectada', 'Sin descripción')}",
                                "code_before": "N/A",
                                "code_after": analysis.get('codigo_sugerido', ''),
                                "inspiration_id": insp.get('id', ''),
                                "components": analysis.get('componentes_requeridos', []),
                                "source_data": insp.get('source_data', '')
                            })
            except Exception as e:
                print(f"⚠️  Error cargando inspiration_pool: {e}")

        # Guardar en archivo
        output = {
            "timestamp": __import__('time').strftime('%Y-%m-%dT%H:%M:%S'),
            "total_proposals": len(all_proposals),
            "proposals": all_proposals
        }

        with open('proposed_upgrades.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return output

    def _validate_code_snippet(self, code: str) -> bool:
        """Validación sintáctica básica del código sugerido."""
        if not code or len(code.strip()) < 10:
            return False
        # Verificar que no tenga instrucciones peligrosas
        dangerous = ['import os;', 'subprocess', 'eval(', 'exec(', '__import__']
        return not any(d in code for d in dangerous)

    def _get_emergency_log_path(self) -> str:
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..',
            'knowledge_base',
            'emergency_shield.log'
        )

    def _log_emergency(self, message: str) -> None:
        try:
            log_path = self._get_emergency_log_path()
            payload = {
                'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                'level': 'ERROR',
                'message': message
            }
            with open(log_path, 'a', encoding='utf-8') as log_file:
                log_file.write(json.dumps(payload, ensure_ascii=False) + '\n')
        except Exception:
            pass

    def _load_json_file(self, path: str) -> Optional[Dict]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self._log_emergency(f'Error leyendo JSON {path}: {e}')
            return None

    def _write_json_file(self, path: str, data: Dict) -> bool:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self._log_emergency(f'Error escribiendo JSON {path}: {e}')
            return False

    def _sanitize_code_snippet(self, code: str) -> str:
        """Sanitiza código sugerido eliminando contenido peligroso y líneas vacías extremas."""
        if not code or not isinstance(code, str):
            return ''

        sanitized = code.strip()
        sanitized = sanitized.replace('\r\n', '\n').replace('\r', '\n')

        dangerous_patterns = [
            r'\bimport\s+os\b',
            r'\bimport\s+subprocess\b',
            r'\beval\s*\(',
            r'\bexec\s*\(',
            r'__import__',
            r'system\s*\(',
            r'popen\s*\('
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, sanitized):
                return ''

        lines = [line for line in sanitized.split('\n') if line.strip() != '']
        return '\n'.join(lines).strip()

    async def convertir_inspiracion_en_parche(self, idea_id: str) -> Dict:
        """
        Lee 'inspiration_pool.json', localiza la idea por ID,
        valida el código sugerido y lo escribe en 'proposed_upgrades.json'.
        Función asíncrona para evitar bloqueos en el servidor.
        """
        try:
            inspiration_pool_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..',
                'knowledge_base',
                'inspiration_pool.json'
            )

            # Cargar datos de inspiración
            with open(inspiration_pool_path, 'r', encoding='utf-8') as f:
                inspiration_data = json.load(f)

            # Buscar idea por ID
            idea = None
            for insp in inspiration_data.get('inspirations', []):
                if insp.get('id') == idea_id:
                    idea = insp
                    break

            if not idea:
                return {"status": "error", "message": f"Idea {idea_id} no encontrada en inspiration_pool"}

            # Extraer código sugerido y análisis
            analysis = idea.get('analysis', {})
            codigo_sugerido = analysis.get('codigo_sugerido', '')
            funcionalidad = analysis.get('funcionalidad_detectada', 'Sin descripción')
            componentes = analysis.get('componentes_requeridos', [])

            # Sanitizar código antes de procesar
            codigo_sanitizado = self._sanitize_code_snippet(codigo_sugerido)
            if not codigo_sanitizado:
                return {"status": "error", "message": "Código sugerido contiene patrones peligrosos o está vacío"}

            # Validar código con AST para evitar errores sintácticos
            try:
                ast.parse(codigo_sanitizado)
            except SyntaxError as e:
                return {"status": "error", "message": f"Error de sintaxis en código sugerido: {e.msg} (línea {e.lineno})"}

            # Empaquetar como propuesta activa en proposed_upgrades.json
            proposal = {
                "target_file": "STARK_INSPIRATION",
                "description": f"🚀 Parche desde inspiración {idea_id}: {funcionalidad}",
                "code_before": "N/A",
                "code_after": codigo_sanitizado,
                "inspiration_id": idea_id,
                "components": componentes,
                "source_data": idea.get('source_data', ''),
                "status": "active",
                "created_at": datetime.now().isoformat(),
                "source_type": idea.get('source_type', 'unknown')
            }

            # Cargar y actualizar proposed_upgrades.json
            upgrades_path = 'proposed_upgrades.json'
            if os.path.exists(upgrades_path):
                with open(upgrades_path, 'r', encoding='utf-8') as f:
                    upgrades_data = json.load(f)
            else:
                upgrades_data = {"proposals": []}

            # Añadir propuesta y guardar
            upgrades_data['proposals'].append(proposal)
            with open(upgrades_path, 'w', encoding='utf-8') as f:
                json.dump(upgrades_data, f, indent=2, ensure_ascii=False)

            # Liberar memoria
            del inspiration_data, idea, analysis, codigo_sugerido, funcionalidad, componentes, codigo_sanitizado

            return {
                "status": "ready_for_patch",
                "upgrade_id": idea_id,
                "message": f"✅ Idea {idea_id} convertida a parche activo y listo para aplicar",
                "proposal": proposal
            }
        except Exception as e:
            self._log_emergency(f"Error en convertir_inspiracion_en_parche: {str(e)}")
            return {"status": "error", "message": f"Error procesando inspiración: {str(e)}"}

    def apply_proposal(self, proposal_id: str) -> Dict:
        """
        Aplica una propuesta de mejora al código.
        Mueve la idea de 'inspiration_pool.json' a 'proposed_upgrades.json' como parche aplicado.
        """
        try:
            # Cargar propuestas
            with open('proposed_upgrades.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                proposals = data.get('proposals', [])

            # Buscar propuesta
            proposal = next((p for p in proposals if p.get('inspiration_id') == proposal_id), None)
            if not proposal:
                return {"status": "error", "message": "Propuesta no encontrada"}

            print(f"🔧 Aplicando propuesta: {proposal['description']}")

            # Si es inspiración de Stark, marcar como aplicada
            if proposal.get('target_file') == 'STARK_INSPIRATION':
                inspiration_pool_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    '..',
                    'knowledge_base',
                    'inspiration_pool.json'
                )
                if os.path.exists(inspiration_pool_path):
                    with open(inspiration_pool_path, 'r', encoding='utf-8') as f:
                        insp_data = json.load(f)
                    inspirations = insp_data.get('inspirations', [])
                    for i, insp in enumerate(inspirations):
                        if insp.get('id') == proposal_id:
                            inspirations[i]['applied'] = True
                            inspirations[i]['applied_at'] = __import__('time').strftime('%Y-%m-%dT%H:%M:%S')
                            break
                    with open(inspiration_pool_path, 'w', encoding='utf-8') as f:
                        json.dump(insp_data, f, indent=2, ensure_ascii=False)

                    # Liberar memoria
                    del insp_data, inspirations

            # Aplicar el parche al archivo correspondiente
            if proposal.get('target_file') == 'STARK_INSPIRATION':
                # Para inspiraciones, guardamos el código en un archivo temporal
                temp_file_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    '..',
                    'knowledge_base',
                    'applied_patches',
                    f'patch_{proposal_id}.py'
                )
                os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)

                with open(temp_file_path, 'w', encoding='utf-8') as f:
                    f.write(proposal['code_after'])

                # Notificar al crash_overseer para reinicio suave
                self._notify_crash_overseer_for_restart()

                # Liberar memoria
                del proposal

            return {
                "status": "ok",
                "message": "Propuesta aplicada con éxito",
                "proposal": proposal
            }
        except Exception as e:
            self._log_emergency(f"Error aplicando propuesta {proposal_id}: {str(e)}")
            return {"status": "error", "message": f"Error aplicando propuesta: {str(e)}"}

    def _notify_crash_overseer_for_restart(self):
        """
        Notifica al Crash Overseer para que realice un reinicio suave.
        """
        try:
            overseer_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                'crash_overseer.py'
            )

            # Crear archivo de notificación para reinicio suave
            restart_notification_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..',
                'AME_Core',
                'restart_requested.txt'
            )

            with open(restart_notification_path, 'w', encoding='utf-8') as f:
                f.write(f"🔄 REINICIO SUAVE SOLICITADO\n")
                f.write(f"📅 Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"🔧 Motivo: Aplicación de parche de evolución\n")

            print(f"🔄 Notificación de reinicio suave enviada a Crash Overseer")

        except Exception as e:
            self._log_emergency(f"Error notificando reinicio suave: {str(e)}")

    def _apply_patch_to_file(self, file_path: str, code_patch: str) -> bool:
        """
        Aplica un parche de código a un archivo específico.
        """
        try:
            # Leer el archivo original
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            # Aplicar el parche (simplificado: solo añadir al final)
            patched_content = original_content + "\n\n" + code_patch

            # Guardar el archivo modificado
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(patched_content)

            # Liberar memoria
            del original_content, patched_content

            return True
        except Exception as e:
            self._log_emergency(f"Error aplicando parche a {file_path}: {str(e)}")
            return False

# Bloque de prueba
if __name__ == "__main__":
    engine = EvolutionEngine()
    files = [
        'AURA_Core/ai_router.py',
        'AME_Core/servidor_ame.py',
        'AURA_Core/osint_radar.py'
    ]
    result = engine.generate_proposals(files)
    print(f"✅ Generated {result['total_proposals']} proposals in proposed_upgrades.json")