import subprocess, os, sys

AGENT_DIR    = r"C:\Users\User\Downloads\AURA\AME_Agent"
PHONE_DIR    = "/sdcard/AURA_workspace/AME_Agent"
AURA_URL     = "ws://localhost:8765"

def sync_via_ssh():
    """Copia via SSH/Tailscale si esta conectado"""
    import json
    ip_file = r"C:\Users\User\Desktop\termux_ip.txt"
    ip = "100.102.245.117"
    if os.path.exists(ip_file):
        with open(ip_file) as f:
            ip = f.read().strip()

    print(f"Conectando a Termux via SSH ({ip})...")
    # Crear directorio destino
    cmd_mkdir = f'ssh -p 8022 u0_a1167@{ip} "mkdir -p {PHONE_DIR}"'
    result = subprocess.run(cmd_mkdir, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error al crear directorio: {result.stderr}")
        return False

    # Copiar cada archivo
    files = ["agent.py", "tools.py", "llm_client.py", "memory.py", "install.sh"]
    for f in files:
        src = os.path.join(AGENT_DIR, f)
        dst = f"u0_a1167@{ip}:{PHONE_DIR}/{f}"
        cmd = f'scp -P 8022 "{src}" {dst}'
        print(f"  Copiando {f}...")
        subprocess.run(cmd, shell=True, capture_output=True)

    print("AME Agent copiado al celular via SSH")
    print("")
    print("En Termux ejecuta:")
    print(f"  cd {PHONE_DIR}")
    print("  bash install.sh")
    return True

def sync_via_github():
    """Alternativa: push a GitHub y el celular hace pull"""
    print("Subiendo AME Agent a GitHub...")
    aura_dir = r"C:\Users\User\Downloads\AURA"
    subprocess.run(["git", "add", "AME_Agent/"], cwd=aura_dir)
    subprocess.run(["git", "commit", "-m", "Update AME Agent"],
                   cwd=aura_dir)
    subprocess.run(["git", "push", "origin", "main"], cwd=aura_dir)
    print("Subido a GitHub")
    print("")
    print("En Termux ejecuta:")
    print("  cd /sdcard/AURA_workspace")
    print("  git pull origin main")
    print("  bash AME_Agent/install.sh")

if __name__ == "__main__":
    print("=== Sincronizar AME Agent al celular ===")
    print("")
    if not sync_via_ssh():
        print("SSH no disponible, usando GitHub...")
        sync_via_github()