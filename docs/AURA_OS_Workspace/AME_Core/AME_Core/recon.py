import json
import sys
import argparse
from metadata_extractor import extract_metadata
from whois_lookup import lookup_domain

def search_username(username):
    """Simula una búsqueda de usernames en plataformas clave (Lógica ligera)."""
    # En una implementación real, aquí irían llamadas a APIs o scrapers ligeros
    # Para mantener la ligereza en LG Q60, simulamos la verificación de disponibilidad
    platforms = ["GitHub", "Twitter", "Instagram", "LinkedIn", "Reddit"]
    results = {}
    
    for p in platforms:
        # Simulamos una verificación rápida (en la vida real sería un request HTTP)
        results[p] = "Verification Pending" 
    
    return {
        "username": username,
        "platforms": results,
        "status": "Simulation mode active"
    }

def main():
    parser = argparse.ArgumentParser(description="AME Recon Tool - Unified OSINT Entry Point")
    parser.add_argument("--user", help="Username to search")
    parser.add_argument("--meta", help="Path to image for metadata extraction")
    parser.add_argument("--whois", help="Domain for WHOIS lookup")
    
    args = parser.parse_args()
    result = None

    if args.user:
        result = search_username(args.user)
    elif args.meta:
        result = extract_metadata(args.meta)
    elif args.whois:
        result = lookup_domain(args.whois)
    else:
        print(json.dumps({"error": "No se especificó ninguna acción. Use --user, --meta o --whois."}))
        sys.exit(1)

    # Salida optimizada en JSON compacto
    print(json.dumps(result, separators=(',', ':')))

if __name__ == "__main__":
    main()