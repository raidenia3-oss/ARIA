"""
Tunnel management module for AURA remote access.
Supports ngrok and cloudflared tunneling.
"""
import subprocess
import json
import os
import psutil
import time


class TunnelManager:
    def __init__(self, tunnel_type='ngrok', port=5000):
        self.tunnel_type = tunnel_type
        self.port = port
        self.process = None
        self.tunnel_url = None

    def start_ngrok(self):
        """Start ngrok tunnel."""
        try:
            # Install ngrok if not present
            if not self._command_exists('ngrok'):
                print("Installing ngrok...")
                os.system('pip install pyngrok')
            
            from pyngrok import ngrok
            self.process = ngrok.connect(self.port, "http")
            self.tunnel_url = self.process.public_url
            print(f"✅ ngrok tunnel active: {self.tunnel_url}")
            return {"status": "ok", "tunnel": self.tunnel_url, "type": "ngrok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def start_cloudflared(self):
        """Start cloudflared tunnel."""
        try:
            if not self._command_exists('cloudflared'):
                print("cloudflared not installed. Install from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
                return {"status": "error", "message": "cloudflared not installed"}
            
            self.process = subprocess.Popen(
                ['cloudflared', 'tunnel', 'run', '--url', f'http://localhost:{self.port}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(2)
            # Get cloudflared URL from logs (requires CF account setup)
            self.tunnel_url = f"<cloudflared-tunnel-running>"
            print(f"✅ cloudflared tunnel started on port {self.port}")
            return {"status": "ok", "tunnel": self.tunnel_url, "type": "cloudflared"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def stop(self):
        """Stop active tunnel."""
        try:
            if self.tunnel_type == 'ngrok':
                from pyngrok import ngrok
                ngrok.disconnect(self.tunnel_url)
            elif self.process:
                self.process.terminate()
                self.process.wait(timeout=5)
            self.process = None
            self.tunnel_url = None
            print("✅ Tunnel stopped")
            return {"status": "ok", "message": "Tunnel stopped"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def status(self):
        """Check tunnel status."""
        if self.process is None or self.tunnel_url is None:
            return {"status": "off", "tunnel": None}
        
        is_running = self.process.poll() is None if self.process else False
        return {
            "status": "on" if is_running else "off",
            "tunnel": self.tunnel_url,
            "type": self.tunnel_type,
            "running": is_running
        }

    @staticmethod
    def _command_exists(cmd):
        """Check if command exists in PATH."""
        result = subprocess.run(['which' if os.name != 'nt' else 'where', cmd], 
                               capture_output=True)
        return result.returncode == 0
