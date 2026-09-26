#!/usr/bin/env python3
"""
Módulo para conexión SSH a Termux con contraseña automatizada.
Uso: python termux_ssh.py "comando"
"""
import paramiko
import sys
import os

# Configuración
TERMUX_HOST = "192.168.18.21"
TERMUX_PORT = 8022
TERMUX_USER = "u0_a252"
TERMUX_PASS = os.environ.get("TERMUX_SSH_PASS", "")

def run_command(command, timeout=15):
    """Ejecuta un comando en Termux via SSH."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(TERMUX_HOST, TERMUX_PORT, TERMUX_USER, TERMUX_PASS, timeout=10)
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        
        output = stdout.read().decode('utf-8', errors='replace')
        errors = stderr.read().decode('utf-8', errors='replace')
        
        if output:
            print(output, end='')
        if errors:
            print(f"STDERR: {errors}", file=sys.stderr, end='')
        
        return stdout.channel.recv_exit_status()
    except Exception as e:
        print(f"Error SSH: {e}", file=sys.stderr)
        return 1
    finally:
        client.close()

def upload_file(local_path, remote_path):
    """Sube un archivo a Termux via SCP."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(TERMUX_HOST, TERMUX_PORT, TERMUX_USER, TERMUX_PASS, timeout=10)
        sftp = client.open_sftp()
        sftp.put(local_path, remote_path)
        sftp.close()
        print(f"OK: {local_path} -> {remote_path}")
        return True
    except Exception as e:
        print(f"Error SCP: {e}", file=sys.stderr)
        return False
    finally:
        client.close()

def sync_directory(local_dir, remote_dir):
    """Sincroniza un directorio completo."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(TERMUX_HOST, TERMUX_PORT, TERMUX_USER, TERMUX_PASS, timeout=10)
        
        # Obtener HOME real de Termux
        stdin, stdout, stderr = client.exec_command("echo $HOME")
        home_dir = stdout.read().decode('utf-8').strip()
        
        # Normalizar remote_dir: reemplazar ~ por $HOME real
        remote_dir = remote_dir.replace("\\", "/")
        if remote_dir.startswith("~"):
            remote_dir = home_dir + remote_dir[1:]
        
        # Crear directorio remoto
        client.exec_command(f"mkdir -p {remote_dir}")
        print(f"Directorio remoto: {remote_dir}")
        
        count = 0
        for root, dirs, files in os.walk(local_dir):
            for f in files:
                if f.endswith(('.py', '.html', '.js', '.css', '.json', '.sh')):
                    local_path = os.path.join(root, f)
                    rel_path = os.path.relpath(local_path, local_dir).replace("\\", "/")
                    remote_path = f"{remote_dir}/{rel_path}"
                    
                    # Crear directorio remoto
                    parts = remote_path.rsplit("/", 1)
                    remote_file_dir = parts[0] if len(parts) > 1 else remote_dir
                    client.exec_command(f"mkdir -p {remote_file_dir}")
                    
                    # Subir archivo
                    sftp = client.open_sftp()
                    try:
                        sftp.put(local_path, remote_path)
                        count += 1
                        print(f"  [{count}] {rel_path}")
                    except Exception as e:
                        print(f"  Error: {rel_path}: {e}")
                    finally:
                        sftp.close()
        
        print(f"\nTotal: {count} archivos sincronizados")
        return True
    except Exception as e:
        print(f"Error sync: {e}", file=sys.stderr)
        return False
    finally:
        client.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python termux_ssh.py <comando>")
        print("Ejemplo: python termux_ssh.py 'ls -la ~/AME-termux'")
        sys.exit(1)
    
    cmd = " ".join(sys.argv[1:])
    sys.exit(run_command(cmd))