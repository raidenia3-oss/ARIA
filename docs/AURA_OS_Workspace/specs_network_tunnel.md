# 📜 **SPECIFICATIONS: TERMUX NETWORK TUNNEL & DIAGNOSTICS**
## **Reverse SSH Tunneling & Network Health Monitoring for AURA Mobile Nodes**
**Version:** 1.0.0
**Date:** 02/06/2026
**Status:** Proposal & Specifications
**Author:** System Architect

---

## 🎯 **Objective**
Design a **reverse SSH tunneling** architecture managed from Python that ensures persistent connectivity between the AURA server (PC) and mobile devices (Termux). This system will:
1. **Establish a secure reverse SSH tunnel** from the mobile device to the AURA server, allowing communication even if the mobile device's IP changes.
2. **Enable network diagnostics** on the mobile device, allowing AURA to execute basic network health checks (e.g., `ping`, `traceroute`, `ifconfig`).
3. **Ensure automatic reconnection** if the tunnel drops.
4. **Secure the SSH port** with authentication and encryption.

---

## 🔧 **Architecture Overview**

### **1. System Components**
| **Component**               | **Description**                                                                                     |
|-----------------------------|-------------------------------------------------------------------------------------------------|
| **AURA Server (PC)**        | Central server that manages SSH tunnels and diagnostics.                                          |
| **Termux SSH Client**       | Lightweight SSH client running on the mobile device.                                               |
| **Reverse SSH Tunnel**      | Secure tunnel from the mobile device to the AURA server.                                           |
| **Network Diagnostics**     | Commands executed on the mobile device to check network health.                                    |
| **Python Tunnel Manager**   | Python script managing tunnel setup, reconnection, and diagnostics.                                |

---

## 🔄 **Reverse SSH Tunnel Design**

### **1. Tunnel Configuration**
- **Direction:** Mobile device (client) → AURA server (gateway).
- **Purpose:** Allow AURA to initiate connections to the mobile device even if the mobile device's IP changes.
- **Ports:**
  - **SSH Port (Server):** `2222` (custom port to avoid conflicts with default SSH).
  - **Local Port Forwarding:** Forward a local port (e.g., `8080`) on the AURA server to a remote port (e.g., `80`) on the mobile device.

#### **Example Tunnel Command (Mobile Device)**
```bash
ssh -R 8080:localhost:22 -N -f -i ~/.ssh/id_rsa user@aura-server.example.com -p 2222
```
- `-R`: Reverse tunneling (remote port forwarding).
- `8080:localhost:22`: Forward remote port `8080` to local port `22` (SSH) on the AURA server.
- `-N`: Do not execute remote commands.
- `-f`: Run in the background.
- `-i`: Use a specific SSH key for authentication.

---

### **2. Python Tunnel Manager**
A Python script (`tunnel_manager.py`) will manage the SSH tunnel and diagnostics on the mobile device.

#### **Key Features:**
1. **Automatic Tunnel Setup:**
   - Detect if a tunnel is active.
   - Start a new tunnel if none is active.
   - Use SSH keys for authentication (no password prompts).

2. **Reconnection Logic:**
   - Monitor tunnel health using `ssh -O check` (check if tunnel is active).
   - Reconnect automatically if the tunnel drops.

3. **Network Diagnostics:**
   - Execute commands like `ping`, `traceroute`, `ifconfig`, and `netstat` on the mobile device.
   - Return results to the AURA server for analysis.

4. **Security:**
   - Use SSH keys (RSA/ECDSA) for authentication.
   - Restrict SSH access to the AURA server's IP.
   - Disable root login and password authentication.

---

## 📋 **Tunnel Manager Implementation**

### **1. Code Structure**
```python
#!/usr/bin/env python3
"""
tunnel_manager.py - Manages reverse SSH tunnel and network diagnostics for AURA mobile nodes.
"""

import os
import sys
import subprocess
import time
import json
import logging
from typing import Dict, Optional, List

class TunnelManager:
    def __init__(self, config: Dict):
        self.config = config
        self.ssh_key_path = config.get("ssh_key_path", "~/.ssh/id_rsa")
        self.server_ip = config.get("server_ip", "aura-server.example.com")
        self.server_port = config.get("server_port", 2222)
        self.local_port = config.get("local_port", 8080)
        self.remote_port = config.get("remote_port", 22)
        self.tunnel_command = self._build_tunnel_command()
        self.diagnostics_commands = {
            "ping": ["ping", "-c", "4", "google.com"],
            "traceroute": ["traceroute", "google.com"],
            "ifconfig": ["ifconfig"],
            "netstat": ["netstat", "-tuln"]
        }
        self.logger = logging.getLogger("TunnelManager")
        self.logger.setLevel(logging.INFO)
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging for the tunnel manager."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _build_tunnel_command(self) -> List[str]:
        """Build the SSH tunnel command."""
        return [
            "ssh",
            "-R", f"{self.local_port}:localhost:{self.remote_port}",
            "-N", "-f",
            "-i", os.path.expanduser(self.ssh_key_path),
            f"user@{self.server_ip}",
            "-p", str(self.server_port)
        ]

    def is_tunnel_active(self) -> bool:
        """Check if the SSH tunnel is active."""
        try:
            result = subprocess.run(
                ["ssh", "-O", "check", f"user@{self.server_ip}", "-p", str(self.server_port)],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Error checking tunnel: {str(e)}")
            return False

    def start_tunnel(self) -> bool:
        """Start the reverse SSH tunnel."""
        try:
            self.logger.info(f"Starting tunnel with command: {' '.join(self.tunnel_command)}")
            subprocess.Popen(self.tunnel_command)
            time.sleep(2)  # Wait for tunnel to establish
            return self.is_tunnel_active()
        except Exception as e:
            self.logger.error(f"Error starting tunnel: {str(e)}")
            return False

    def stop_tunnel(self) -> bool:
        """Stop the reverse SSH tunnel."""
        try:
            subprocess.run(
                ["ssh", "-O", "exit", f"user@{self.server_ip}", "-p", str(self.server_port)],
                capture_output=True
            )
            return True
        except Exception as e:
            self.logger.error(f"Error stopping tunnel: {str(e)}")
            return False

    def run_diagnostics(self, command_name: str) -> Dict:
        """Run a network diagnostic command on the mobile device."""
        if command_name not in self.diagnostics_commands:
            return {"status": "error", "error": f"Unknown command: {command_name}"}

        command = self.diagnostics_commands[command_name]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10
            )
            return {
                "status": "success",
                "command": command_name,
                "output": result.stdout,
                "error": result.stderr if result.stderr else None,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": f"Command timed out: {' '.join(command)}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def monitor_tunnel(self, interval: int = 60):
        """Monitor the tunnel and reconnect if it drops."""
        self.logger.info("Starting tunnel monitor...")
        while True:
            if not self.is_tunnel_active():
                self.logger.warning("Tunnel is not active. Attempting to reconnect...")
                if not self.start_tunnel():
                    self.logger.error("Failed to reconnect tunnel. Retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                else:
                    self.logger.info("Tunnel reconnected successfully.")
            time.sleep(interval)

def main():
    """Main entry point for the tunnel manager."""
    config = {
        "ssh_key_path": "~/.ssh/id_rsa",
        "server_ip": "aura-server.example.com",
        "server_port": 2222,
        "local_port": 8080,
        "remote_port": 22
    }

    manager = TunnelManager(config)

    # Start the tunnel
    if not manager.is_tunnel_active():
        if not manager.start_tunnel():
            sys.exit(1)

    # Start monitoring the tunnel
    manager.monitor_tunnel()

    # Example: Run diagnostics (uncomment to use)
    # diagnostics_result = manager.run_diagnostics("ping")
    # print(json.dumps(diagnostics_result, indent=2))

if __name__ == "__main__":
    main()
```

---

## 📋 **Network Diagnostics**

### **1. Supported Commands**
| **Command**       | **Description**                                                                                     | **Example Output**                                                                                     |
|-------------------|-------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| `ping`            | Check connectivity to a host (e.g., `google.com`).                                               | `64 bytes from 142.250.190.46: icmp_seq=1 ttl=117 time=12.3 ms`                                       |
| `traceroute`     | Trace the route to a host.                                                                       | `1  192.168.1.1  0.5 ms  0.3 ms  0.4 ms`                                                               |
| `ifconfig`        | Show network interface configuration.                                                           | `wlan0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500`                                          |
| `netstat`         | Show network connections and listening ports.                                                    | `tcp  0  0 192.168.1.10:54320  142.250.190.46:443  ESTABLISHED`                                        |

---

### **2. Example Diagnostic Output**
```json
{
  "status": "success",
  "command": "ping",
  "output": "PING google.com (142.250.190.46) 56(84) bytes of data.\n64 bytes from fra15s01-in-f14.1e100.net (142.250.190.46): icmp_seq=1 ttl=117 time=12.3 ms",
  "error": null,
  "returncode": 0
}
```

---

## 🔒 **Security Measures**

### **1. SSH Configuration**
- **Custom Port:** Use a non-standard SSH port (e.g., `2222`) to reduce exposure.
- **Key-Based Authentication:** Disable password authentication and use SSH keys.
- **Firewall Rules:** Restrict SSH access to the AURA server's IP only.
- **Disable Root Login:** Ensure SSH is configured to disallow root login.

#### **Example SSH Config (`/etc/ssh/sshd_config`)**
```
Port 2222
Protocol 2
PermitRootLogin no
PasswordAuthentication no
AllowUsers user@aura-server.example.com
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
```

### **2. Encryption**
- **SSH Encryption:** All traffic is encrypted by default.
- **Key Exchange:** Use ECDSA or RSA keys with a minimum length of 2048 bits.

---

## 🔄 **Automatic Reconnection Logic**

### **1. Tunnel Health Monitoring**
- **Check Tunnel Status:** Use `ssh -O check` to verify if the tunnel is active.
- **Reconnect if Down:** If the tunnel is inactive, attempt to reconnect automatically.
- **Retry Delay:** Wait 5 seconds before retrying if a reconnection fails.

### **2. Example Reconnection Flow**
1. **Check Tunnel Status:**
   ```bash
   ssh -O check user@aura-server.example.com -p 2222
   ```
2. **If Tunnel is Down:**
   - Start a new tunnel.
   - Wait 2 seconds for the tunnel to establish.
   - Verify the tunnel is active.
3. **If Tunnel is Up:**
   - Continue monitoring.

---

## 📋 **Deployment Process**

### **1. Prerequisites**
- **SSH Server:** AURA server must have an SSH server running with the custom port (`2222`).
- **SSH Key Pair:** Generate an SSH key pair on the mobile device and add the public key to the AURA server's `~/.ssh/authorized_keys`.
- **Termux Environment:** Python and SSH client must be installed on the mobile device.
  ```bash
  pkg install python openssh
  ```

### **2. Steps to Deploy**
1. **Generate SSH Key Pair (Mobile Device):**
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/id_rsa -N ""
   ```
2. **Add Public Key to AURA Server:**
   ```bash
   cat ~/.ssh/id_rsa.pub | ssh user@aura-server.example.com "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
   ```
3. **Transfer Tunnel Manager Script:**
   ```bash
   scp tunnel_manager.py user@mobile-device-ip:/data/data/com.termux/files/home/
   ```
4. **Start the Tunnel Manager:**
   ```bash
   termux-exec python tunnel_manager.py
   ```
5. **Autostart (Optional):**
   - Add the tunnel manager to Termux autostart by editing `~/.bashrc`:
     ```bash
     echo "python /data/data/com.termux/files/home/tunnel_manager.py &" >> ~/.bashrc
     ```

---

## 📌 **Testing & Validation**

### **1. Test Cases**
| **Test Case**                          | **Expected Result**                                                                                     |
|----------------------------------------|---------------------------------------------------------------------------------------------------|
| Tunnel starts successfully               | Tunnel is active and forwarding ports correctly.                                                     |
| Tunnel drops and reconnects            | Tunnel manager detects the drop and reconnects automatically.                                         |
| Network diagnostics execute successfully | Commands like `ping`, `traceroute`, etc., return valid output.                                        |
| SSH key authentication succeeds         | Tunnel starts without password prompts.                                                              |
| Invalid SSH key or password             | Tunnel fails to start and logs an error.                                                           |
| Firewall blocks SSH port               | Tunnel fails to start and logs a connection error.                                                  |

### **2. Validation Steps**
1. **Deploy the Tunnel Manager:** Transfer and run the script on a test device.
2. **Test Tunnel Setup:** Verify that the tunnel starts and forwards ports correctly.
3. **Simulate Tunnel Drop:** Kill the SSH process and verify that the tunnel manager reconnects.
4. **Run Diagnostics:** Execute network diagnostic commands and verify the output.
5. **Security Check:** Ensure SSH is configured securely (custom port, key-based auth, no root login).

---

## 📝 **Non-Goals**
| **ID**  | **Description**                                                                                     |
|---------|-------------------------------------------------------------------------------------------------|
| NG-001  | Support for non-SSH tunneling methods (e.g., VPN).                                                 |
| NG-002  | Advanced network diagnostics (e.g., packet capture, deep packet inspection).                      |
| NG-003  | Integration with non-Termux Android environments.                                                   |
| NG-004  | Support for multiple simultaneous tunnels.                                                        |

---

## 🎯 **Conclusion**
The **Termux Network Tunnel & Diagnostics** specification outlines a secure and persistent reverse SSH tunneling architecture for AURA mobile nodes. This system will:
1. **Establish a secure reverse SSH tunnel** from the mobile device to the AURA server.
2. **Enable automatic reconnection** if the tunnel drops.
3. **Allow network diagnostics** to be executed on the mobile device.
4. **Ensure secure SSH configuration** with key-based authentication and restricted access.

This design ensures persistent connectivity and network health monitoring, even if the mobile device's IP changes or the network conditions fluctuate.

**Next Steps:**
- Validate the specification with the Architect.
- Proceed to implementation once approved.

---
**Ready for Architect Validation!**