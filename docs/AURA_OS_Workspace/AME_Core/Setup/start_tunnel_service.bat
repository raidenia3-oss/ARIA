@echo off
:: Script para iniciar Cloudflare Tunnel como servicio
start "Cloudflare Tunnel" cmd /c python Setup\cloudflared\zero_trust\tunnel_auth.py
echo Cloudflare Tunnel iniciado.
