import subprocess
import shutil
import os
import sys
import json
from pathlib import Path

# --- CONFIGURACIÓN DE ARQUITECTURA ---
AURA_CORE_PATH = Path(__file__).parent.parent
TARGETS_DIR = AURA_CORE_PATH / "targets"
OUTPUT_FILE = TARGETS_DIR / "live_subdomains.txt"

PERMUTATION_WORDS = [
    "dev",
    "staging",
    "api",
    "admin",
    "test",
    "app",
    "www",
    "mail",
    "ftp",
    "db",
    "backup",
    "old",
    "new",
    "v1",
    "v2",
]


def check_tool_availability(tool_name):
    if shutil.which(tool_name):
        return True
    else:
        print(f"[ERROR] La herramienta '{tool_name}' no se encontró en el PATH.")
        install_commands = {
            "subfinder": "go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest",
            "assetfinder": "go install -v github.com/tomnomnom/assetfinder@latest",
            "httpx": "go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest",
            "gau": "go install -v github.com/lc/gau/v2/cmd/gau@latest",
        }
        if tool_name in install_commands:
            print(
                f"[INFO] Para instalar '{tool_name}', ejecuta manualmente: {install_commands[tool_name]}"
            )
        return False


def run_command(command):
    try:
        result = subprocess.run(
            command,
            shell=False,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except subprocess.CalledProcessError as e:
        print(
            f"[ERROR] El comando '{command}' falló con código de salida {e.returncode}."
        )
        return []


def enumerate_subdomains(domain):
    print(f"[*] Iniciando enumeración de subdominios para {domain}...")
    subdomains = set()

    if check_tool_availability("subfinder"):
        subfinder_results = run_command(["subfinder", "-d", domain, "-silent"])
        subdomains.update(subfinder_results)

    if check_tool_availability("assetfinder"):
        assetfinder_results = run_command(["assetfinder", "--subs-only", domain])
        subdomains.update(assetfinder_results)

    return list(subdomains)


def permute_subdomains(base_subdomains, domain):
    print("[*] Generando permutaciones...")
    permutations = set()
    for sub in base_subdomains:
        for word in PERMUTATION_WORDS:
            permutations.add(f"{word}.{sub}")
    for word in PERMUTATION_WORDS:
        permutations.add(f"{word}.{domain}")
    return list(permutations)


def verify_subdomains(subdomain_list):
    print("[*] Verificando subdominios vivos con httpx...")
    if not check_tool_availability("httpx"):
        return []

    temp_file_path = "temp_subdomains.txt"
    with open(temp_file_path, "w") as f:
        f.write("\n".join(subdomain_list))

    httpx_results = run_command(["httpx", "-l", temp_file_path, "-json", "-silent"])
    os.remove(temp_file_path)

    live_hosts = []
    for line in httpx_results:
        try:
            data = json.loads(line)
            live_hosts.append(
                {
                    "url": data.get("url"),
                    "status_code": data.get("status_code"),
                    "title": data.get("title"),
                }
            )
        except json.JSONDecodeError:
            continue

    return live_hosts


def save_results_to_file(live_hosts):
    TARGETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        for host in live_hosts:
            f.write(f"{host['url']}\n")


def run_subdomain_enum(domain):
    if not domain:
        return {"error": "No se proporcionó un dominio."}

    enumerated_subdomains = enumerate_subdomains(domain)
    permuted_subdomains = permute_subdomains(enumerated_subdomains, domain)
    full_subdomain_list = list(set(enumerated_subdomains + permuted_subdomains))
    live_hosts = verify_subdomains(full_subdomain_list)

    if live_hosts:
        save_results_to_file(live_hosts)

    return {
        "target_domain": domain,
        "enumerated_count": len(enumerated_subdomains),
        "permuted_count": len(permuted_subdomains),
        "live_hosts_count": len(live_hosts),
        "results": live_hosts,
    }
