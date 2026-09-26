#!/usr/bin/env python3
"""
conexion_puente.py — Auto-connection manager for phone-to-PC via Tailscale.
Checks if the PC is online, falls back to local mode, and optionally
sends a Wake-on-LAN magic packet to turn the PC on remotely.

Requirements:
    pip install wakeonlan ping3

Usage (phone, e.g. Termux):
    python conexion_puente.py --pc-ip 192.168.1.100 --mac AA:BB:CC:DD:EE:FF
    python conexion_puente.py --pc-ip 100.XX.XX.XX --mac AA:BB:CC:DD:EE:FF --wake
    python conexion_puente.py --pc-ip 192.168.1.100 --wake --local-only
"""

import argparse
import sys
import time

import ping3
import wakeonlan


def check_pc_online(ip, timeout=2):
    """Check if the PC responds to ping. Returns True if online."""
    try:
        response = ping3.ping(ip, timeout=timeout)
        return response is not None and response > 0
    except Exception:
        return False


def wake_pc(mac_address, broadcast_ip="192.168.1.255", port=9):
    """Send a Wake-on-LAN magic packet to the PC."""
    try:
        wakeonlan.send_magic_packet(mac_address, ip_address=broadcast_ip, port=port)
        return True
    except Exception as e:
        print(f"[ERROR] WoL failed: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Phone-to-PC auto-connection manager with WoL support."
    )
    parser.add_argument(
        "--pc-ip",
        required=True,
        help="IP address of the PC (Tailscale or local network).",
    )
    parser.add_argument(
        "--mac",
        default=None,
        help="MAC address of the PC for Wake-on-LAN (e.g. AA:BB:CC:DD:EE:FF).",
    )
    parser.add_argument(
        "--wake",
        action="store_true",
        help="Send Wake-on-LAN magic packet when PC is offline.",
    )
    parser.add_argument(
        "--broadcast",
        default="192.168.1.255",
        help="Broadcast IP for WoL (default: 192.168.1.255).",
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=5,
        help="Seconds between ping checks (default: 5).",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Skip WoL and only fall back to local mode when PC is offline.",
    )
    parser.add_argument(
        "--oneshot",
        action="store_true",
        help="Check once and exit instead of looping.",
    )
    args = parser.parse_args()

    if args.wake and not args.mac:
        print(
            "[ERROR] --wake requires --mac with the PC's MAC address.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[INFO] Checking PC at {args.pc_ip}...")

    if args.oneshot:
        if check_pc_online(args.pc_ip):
            print("[OK] PC is ONLINE. Proceeding with remote connection.")
            sys.exit(0)
        else:
            print("[WARN] PC is OFFLINE.")
            if args.wake and args.mac:
                print(f"[WoL] Sending magic packet to {args.mac}...")
                if wake_pc(args.mac, args.broadcast):
                    print("[WoL] Packet sent. Waiting 10s for PC to boot...")
                    time.sleep(10)
                    if check_pc_online(args.pc_ip):
                        print("[OK] PC is now ONLINE via WoL!")
                        sys.exit(0)
                    print("[WARN] PC did not respond after WoL.")
            print("[FALLBACK] Switching to LOCAL mode.")
            sys.exit(0)

    # Continuous loop
    while True:
        if check_pc_online(args.pc_ip):
            print("[OK] PC is ONLINE. Connection ready.")
            break

        print("[WARN] PC is OFFLINE.")
        if args.wake and args.mac and not args.local_only:
            print(f"[WoL] Sending magic packet to {args.mac}...")
            wake_pc(args.mac, args.broadcast)
            print("[WoL] Waiting 15s for PC to boot...")
            time.sleep(15)
            if check_pc_online(args.pc_ip):
                print("[OK] PC is now ONLINE via WoL!")
                break
            print("[WARN] PC still offline after WoL, retrying next cycle...")
        else:
            print("[FALLBACK] Switching to LOCAL mode automatically.")
            break

        time.sleep(args.check_interval)


if __name__ == "__main__":
    main()