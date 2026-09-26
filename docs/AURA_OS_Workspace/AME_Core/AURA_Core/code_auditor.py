#!/usr/bin/env python3
"""
Code Auditor para AURA.
Analiza los logs de ejecución en busca de patrones de errores recurrentes
y genera tickets de mejora en feature_roadmap.json.
"""

import os
import re
import json
from datetime import datetime
from collections import defaultdict

class CodeAuditor:
    def __init__(self, log_file="AURA_Core/system_health.log", roadmap_file="feature_roadmap.json"):
        self.log_file = log_file
        self.roadmap_file = roadmap_file
        self.error_patterns = [
            r"Error: (.+)",
            r"Exception: (.+)",
            r"Traceback \(most recent call last\)",
            r"File \"(.+)\", line (\d+), in (.+)",
            r"(\w+Error)",
            r"Failed to execute (.+)",
            r"TimeoutError",
            r"ConnectionError",
            r"ValueError",
            r"TypeError",
            r"IndexError",
            r"KeyError",
            r"AttributeError"
        ]
        self.error_threshold = 3  # Número mínimo de errores para generar un ticket

    def load_roadmap(self):
        """Cargar el feature_roadmap.json existente."""
        if os.path.exists(self.roadmap_file):
            with open(self.roadmap_file, 'r') as f:
                return json.load(f)
        return {"improvements": []}

    def save_roadmap(self, roadmap):
        """Guardar el feature_roadmap.json actualizado."""
        with open(self.roadmap_file, 'w') as f:
            json.dump(roadmap, f, indent=2)

    def parse_logs(self):
        """Analizar los logs en busca de errores recurrentes."""
        errors = defaultdict(int)
        error_details = defaultdict(list)

        if not os.path.exists(self.log_file):
            print(f"⚠️ Archivo de logs no encontrado: {self.log_file}")
            return errors, error_details

        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                for pattern in self.error_patterns:
                    match = re.search(pattern, line)
                    if match:
                        error_type = match.group(1) if match.group(1) else match.group(0)
                        if "File" in line and "line" in line:
                            file_match = re.search(r'File "(.+)", line (\d+)', line)
                            if file_match:
                                file_path = file_match.group(1)
                                line_number = file_match.group(2)
                                error_type = f"{error_type} en {file_path}:{line_number}"
                        errors[error_type] += 1
                        error_details[error_type].append(line.strip())
                        break

        return errors, error_details

    def generate_improvement_ticket(self, error_type, error_details):
        """Generar un ticket de mejora para un error recurrente."""
        timestamp = datetime.now().isoformat()
        ticket_id = f"IMP-{len(os.listdir('AURA_Core')) + 1}"

        ticket = {
            "id": ticket_id,
            "title": f"Error recurrente: {error_type}",
            "description": f"El error '{error_type}' ha ocurrido {len(error_details)} veces.\n\nDetalles:\n" + "\n".join(error_details),
            "severity": "high" if len(error_details) > self.error_threshold else "medium",
            "status": "pending",
            "created_at": timestamp,
            "updated_at": timestamp,
            "suggested_fix": "Por determinar",
            "context": {
                "file": None,
                "line": None,
                "function": None
            }
        }

        # Intentar extraer contexto del error
        for detail in error_details:
            if "File" in detail and "line" in detail:
                file_match = re.search(r'File "(.+)", line (\d+)', detail)
                if file_match:
                    ticket["context"]["file"] = file_match.group(1)
                    ticket["context"]["line"] = file_match.group(2)
                    function_match = re.search(r'in (.+)', detail)
                    if function_match:
                        ticket["context"]["function"] = function_match.group(1)
                    break

        return ticket

    def analyze_and_generate_tickets(self):
        """Analizar logs y generar tickets de mejora para errores recurrentes."""
        errors, error_details = self.parse_logs()
        roadmap = self.load_roadmap()

        for error_type, count in errors.items():
            if count >= self.error_threshold:
                ticket = self.generate_improvement_ticket(error_type, error_details[error_type])

                # Verificar si el ticket ya existe
                existing_tickets = [t["id"] for t in roadmap.get("improvements", [])]
                if ticket["id"] not in existing_tickets:
                    roadmap.setdefault("improvements", []).append(ticket)
                    print(f"✅ Generado ticket de mejora: {ticket['id']} - {ticket['title']}")

        # Guardar el roadmap actualizado
        self.save_roadmap(roadmap)
        return roadmap

    def suggest_fix(self, ticket_id):
        """Sugerir una solución para un ticket específico usando Ollama."""
        roadmap = self.load_roadmap()
        ticket = next((t for t in roadmap.get("improvements", []) if t["id"] == ticket_id), None)

        if not ticket:
            print(f"❌ Ticket no encontrado: {ticket_id}")
            return None

        # Usar Ollama para sugerir una solución
        import subprocess
        import json

        prompt = f"""
        Analiza el siguiente error recurrente en el código de AURA y sugiere una solución:

        Error: {ticket['title']}
        Detalles: {ticket['description']}

        Si el error ocurre en un archivo específico (ej: AURA_Core/aura_core.py), sugiere un parche para esa función.
        Si no hay contexto de archivo, sugiere una solución general para el tipo de error.

        Formato de respuesta:
        ```json
        {{
            "suggested_fix": "Descripción del parche o solución",
            "code_patch": "Código para aplicar (si es necesario)",
            "rationale": "Explicación de por qué esta solución es adecuada"
        }}
        """
        try:
            result = subprocess.run(
                ["ollama", "run", "dolphin-llama3", "--prompt", prompt],
                capture_output=True,
                text=True,
                check=True
            )

            response = result.stdout
            try:
                fix_data = json.loads(response)
                ticket["suggested_fix"] = fix_data.get("suggested_fix", "Solución sugerida por IA")
                ticket["code_patch"] = fix_data.get("code_patch", "")
                ticket["updated_at"] = datetime.now().isoformat()
                self.save_roadmap(roadmap)
                print(f"✅ Solución sugerida para ticket {ticket_id}")
                return fix_data
            except json.JSONDecodeError:
                print(f"⚠️ No se pudo parsear la respuesta de Ollama: {response}")
                ticket["suggested_fix"] = response.strip()
                ticket["updated_at"] = datetime.now().isoformat()
                self.save_roadmap(roadmap)
                return {"suggested_fix": response.strip()}

        except subprocess.CalledProcessError as e:
            print(f"❌ Error al consultar a Ollama: {e.stderr}")
            ticket["suggested_fix"] = "Error al obtener sugerencia de solución"
            ticket["updated_at"] = datetime.now().isoformat()
            self.save_roadmap(roadmap)
            return {"error": str(e.stderr)}

    def apply_patch(self, ticket_id, patch_content):
        """Aplicar un parche a un archivo específico."""
        roadmap = self.load_roadmap()
        ticket = next((t for t in roadmap.get("improvements", []) if t["id"] == ticket_id), None)

        if not ticket or not ticket["context"].get("file"):
            print(f"❌ No se puede aplicar parche: Ticket {ticket_id} no tiene contexto de archivo.")
            return False

        file_path = ticket["context"]["file"]
        if not os.path.exists(file_path):
            print(f"❌ Archivo no encontrado: {file_path}")
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Aplicar el parche
            if ticket["context"].get("line"):
                lines = content.split('\n')
                line_number = int(ticket["context"]["line"]) - 1
                if 0 <= line_number < len(lines):
                    # Insertar el parche antes de la línea del error
                    lines.insert(line_number, patch_content)
                    new_content = '\n'.join(lines)
                else:
                    print(f"⚠️ Número de línea fuera de rango: {ticket['context']['line']}")
                    new_content = content
            else:
                # Si no hay línea específica, añadir el parche al final del archivo
                new_content = content + "\n\n" + patch_content

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            ticket["status"] = "applied"
            ticket["updated_at"] = datetime.now().isoformat()
            self.save_roadmap(roadmap)
            print(f"✅ Parche aplicado a {file_path}")
            return True
        except Exception as e:
            print(f"❌ Error al aplicar parche: {e}")
            ticket["status"] = "failed"
            ticket["updated_at"] = datetime.now().isoformat()
            self.save_roadmap(roadmap)
            return False

def main():
    """Función principal para analizar logs y generar tickets."""
    print("=" * 50)
    print("🔍 Analizando logs en busca de errores recurrentes...")
    print("=" * 50)

    auditor = CodeAuditor()
    roadmap = auditor.analyze_and_generate_tickets()

    print("\n📋 Tickets de mejora generados:")
    for ticket in roadmap.get("improvements", []):
        print(f"  - {ticket['id']}: {ticket['title']} (Severidad: {ticket['severity']})")

    print("\n📊 Resumen de errores detectados:")
    errors, _ = auditor.parse_logs()
    for error_type, count in sorted(errors.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {error_type}: {count} ocurrencias")

    print("\n🔧 Para sugerir soluciones, ejecuta:")
    print("  python AURA_Core/code_auditor.py --suggest <ticket_id>")
    print("  python AURA_Core/code_auditor.py --apply <ticket_id> <patch_content>")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "--suggest" and len(sys.argv) > 2:
            auditor = CodeAuditor()
            fix = auditor.suggest_fix(sys.argv[2])
            print("\n💡 Solución sugerida:")
            print(json.dumps(fix, indent=2))
        elif sys.argv[1] == "--apply" and len(sys.argv) > 3:
            auditor = CodeAuditor()
            success = auditor.apply_patch(sys.argv[2], sys.argv[3])
            if success:
                print("✅ Parche aplicado con éxito.")
            else:
                print("❌ Error al aplicar el parche.")
        else:
            print("Uso:")
            print("  python code_auditor.py [--suggest <ticket_id>]")
            print("  python code_auditor.py [--apply <ticket_id> <patch_content>]")
            print("  (Sin argumentos: analizar logs y generar tickets)")
    else:
        main()