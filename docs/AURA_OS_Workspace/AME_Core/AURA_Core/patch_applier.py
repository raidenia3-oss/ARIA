#!/usr/bin/env python3
"""
Patch Applier para AURA.
Aplica parches sugeridos por el Code Auditor a los archivos del sistema.
"""

import os
import json
import sys
from datetime import datetime

class PatchApplier:
    def __init__(self, roadmap_file="feature_roadmap.json"):
        self.roadmap_file = roadmap_file

    def load_roadmap(self):
        """Cargar el feature_roadmap.json."""
        if os.path.exists(self.roadmap_file):
            with open(self.roadmap_file, 'r') as f:
                return json.load(f)
        return {"improvements": []}

    def save_roadmap(self, roadmap):
        """Guardar el feature_roadmap.json actualizado."""
        with open(self.roadmap_file, 'w') as f:
            json.dump(roadmap, f, indent=2)

    def get_ticket(self, ticket_id):
        """Obtener un ticket específico del roadmap."""
        roadmap = self.load_roadmap()
        ticket = next((t for t in roadmap.get("improvements", []) if t["id"] == ticket_id), None)
        return ticket, roadmap

    def apply_patch_from_ticket(self, ticket_id):
        """Aplicar un parche basado en un ticket específico."""
        ticket, roadmap = self.get_ticket(ticket_id)

        if not ticket:
            print(f"❌ Ticket no encontrado: {ticket_id}")
            return False

        if not ticket.get("code_patch"):
            print(f"❌ El ticket {ticket_id} no tiene un parche sugerido.")
            return False

        if not ticket["context"].get("file"):
            print(f"❌ El ticket {ticket_id} no tiene contexto de archivo.")
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
                    lines.insert(line_number, ticket["code_patch"])
                    new_content = '\n'.join(lines)
                else:
                    print(f"⚠️ Número de línea fuera de rango: {ticket['context']['line']}")
                    new_content = content
            else:
                # Si no hay línea específica, añadir el parche al final del archivo
                new_content = content + "\n\n" + ticket["code_patch"]

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            # Actualizar el estado del ticket
            ticket["status"] = "applied"
            ticket["updated_at"] = datetime.now().isoformat()
            ticket["applied_by"] = "automated_patch_applier"
            self.save_roadmap(roadmap)

            print(f"✅ Parche aplicado a {file_path}")
            print(f"📝 Parche aplicado: {ticket['code_patch']}")
            return True
        except Exception as e:
            print(f"❌ Error al aplicar parche: {e}")
            ticket["status"] = "failed"
            ticket["updated_at"] = datetime.now().isoformat()
            ticket["error"] = str(e)
            self.save_roadmap(roadmap)
            return False

    def list_tickets(self):
        """Listar todos los tickets disponibles."""
        roadmap = self.load_roadmap()
        tickets = roadmap.get("improvements", [])
        if not tickets:
            print("⚠️ No hay tickets de mejora disponibles.")
            return

        print("📋 Tickets de mejora disponibles:")
        for ticket in tickets:
            status = ticket.get("status", "pending")
            print(f"  - {ticket['id']}: {ticket['title']} (Status: {status}, Severidad: {ticket['severity']})")

def main():
    """Función principal para aplicar parches."""
    print("=" * 50)
    print("🔧 Patch Applier para AURA")
    print("=" * 50)

    applier = PatchApplier()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--list":
            applier.list_tickets()
        elif len(sys.argv) > 2 and sys.argv[1] == "--apply":
            ticket_id = sys.argv[2]
            success = applier.apply_patch_from_ticket(ticket_id)
            if success:
                print("✅ Parche aplicado con éxito.")
            else:
                print("❌ Error al aplicar el parche.")
        else:
            print("Uso:")
            print("  python patch_applier.py --list")
            print("  python patch_applier.py --apply <ticket_id>")
    else:
        print("Uso:")
        print("  python patch_applier.py --list (para listar tickets)")
        print("  python patch_applier.py --apply <ticket_id> (para aplicar un parche)")
        print("\nEjemplo:")
        print("  python patch_applier.py --list")
        print("  python patch_applier.py --apply IMP-1")

if __name__ == "__main__":
    main()