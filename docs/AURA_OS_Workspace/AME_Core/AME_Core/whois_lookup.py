import json
import sys
import os
try:
    import whois
except ImportError:
    print(json.dumps({"error": "Libreria 'python-whois' no instalada. Ejecuta: pip install python-whois"}))
    sys.exit(1)

def lookup_domain(domain):
    """Realiza una consulta Whois básica y optimizada."""
    try:
        w = whois.whois(domain)
        
        # Seleccionamos solo los datos más críticos para ahorrar RAM y espacio
        # Convertimos todo a string para evitar errores de serialización JSON
        data = {
            "domain": domain,
            "registrar": str(w.registrar),
            "creation_date": str(w.creation_date) if isinstance(w.creation_date, str) else str(w.creation_date[0] if isinstance(w.creation_date, list) else w.creation_date),
            "expiration_date": str(w.expiration_date) if isinstance(w.expiration_date, str) else str(w.expiration_date[0] if isinstance(w.expiration_date, list) else w.expiration_date),
            "name_servers": w.name_servers if isinstance(w.name_servers, list) else [str(w.name_servers)],
            "status": str(w.status) if isinstance(w.status, str) else str(w.status[0] if isinstance(w.status, list) else w.status)
        }
        return data
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Falta el dominio a consultar"}))
        sys.exit(1)

    target_domain = sys.argv[1]
    result = lookup_domain(target_domain)
    
    # Guardar en JSON optimizado (sin espacios, compacto)
    output_file = f"whois_{target_domain}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=None, separators=(',', ':'))
    
    print(json.dumps({"status": "success", "file": output_file}))