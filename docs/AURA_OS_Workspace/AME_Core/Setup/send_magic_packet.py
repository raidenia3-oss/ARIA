#!/usr/bin/env python3
"""
Script para enviar un Magic Packet Wake-on-LAN.
"""

import socket
import argparse

def send_magic_packet(mac_address, ip_address, port=9):
    """
    Envía un Magic Packet a la dirección MAC especificada.
    """
    # Convertir la dirección MAC a bytes
    mac_bytes = bytes.fromhex(mac_address.replace(':', ''))

    # Crear el Magic Packet (6 bytes de FF seguidos de la MAC)
    magic_packet = b'\xff' * 6 + mac_bytes * 16

    # Crear socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Enviar el Magic Packet
    sock.sendto(magic_packet, (ip_address, port))
    print(f"✅ Magic Packet enviado a {ip_address}:{port} para MAC {mac_address}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Enviar Magic Packet Wake-on-LAN.')
    parser.add_argument('--mac', required=True, help='Dirección MAC del dispositivo (ej: 00:11:22:33:44:55)')
    parser.add_argument('--ip', required=True, help='Dirección IP del dispositivo (ej: 192.168.1.100)')
    args = parser.parse_args()

    send_magic_packet(args.mac, args.ip)