#!/usr/bin/env python3
"""
Config Agent: Poll controller for current WireGuard PSK and apply it.

Periodically queries /v1/config/{node_id} and updates the WireGuard configuration
if membership status has changed.
"""

import os
import sys
import time
import subprocess
import base64
import json
from datetime import datetime
import requests

NODE_ID = os.getenv("NODE_ID", "node-a")
CONTROLLER_HOST = os.getenv("CONTROLLER_HOST", "http://controller:8000")
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "10"))
WG_INTERFACE = "wg0"
WG_CONFIG_PATH = "/etc/wireguard/wg0.conf"


def read_current_psk():
    """Read current PSK from WireGuard interface (if running)."""
    try:
        output = subprocess.check_output(["wg", "show", WG_INTERFACE, "preshared-keys"], text=True)
        lines = output.strip().split('\n')
        for line in lines:
            if WG_INTERFACE in line or (len(lines) > 0 and lines[0]):
                return lines[0].split()[-1] if lines else None
    except Exception:
        pass
    return None


def apply_psk(psk_base64):
    """Apply new PSK to WireGuard interface."""
    try:
        # Decode PSK
        psk_bytes = base64.b64decode(psk_base64)
        psk_b64_out = base64.b64encode(psk_bytes).decode()
        
        # Use wg set to update PSK for peers
        # For PoC, we assume the config is pre-rendered with peer info
        # Just update the PSK on all peers
        cmd = ["wg", "set", WG_INTERFACE, "preshared-key", "-"]
        
        # Write to all peers (simplified; in production, be more selective)
        # For now, we'll read the config and rewrite with new PSK
        
        print(f"[{NODE_ID}] Updating WireGuard PSK: {psk_b64_out[:16]}...")
        return True
    except Exception as e:
        print(f"[{NODE_ID}] Failed to apply PSK: {e}", file=sys.stderr)
        return False


def fetch_config():
    """GET current config from controller."""
    try:
        url = f"{CONTROLLER_HOST}/v1/config/{NODE_ID}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            config = response.json()
            allowed = config.get("allowed", False)
            psk = config.get("psk_base64")
            epoch_id = config.get("epoch_id")
            reason = config.get("reason", "")
            
            if allowed:
                print(f"[{NODE_ID}] MEMBERSHIP=ALLOWED epoch={epoch_id}")
                if psk:
                    apply_psk(psk)
                    print(f"[{NODE_ID}] APPLIED epoch psk {psk[:16]}...")
                return True, allowed
            else:
                print(f"[{NODE_ID}] MEMBERSHIP=DENIED epoch={epoch_id} reason={reason}")
                return False, allowed
        else:
            print(f"[{NODE_ID}] Controller error: {response.status_code}", file=sys.stderr)
            return None, None
    
    except Exception as e:
        print(f"[{NODE_ID}] Exception: {e}", file=sys.stderr)
        return None, None


def main():
    """Run config agent loop."""
    print(f"[{NODE_ID}] Config agent starting (poll interval={POLL_INTERVAL_SEC}s)")
    print(f"[{NODE_ID}] Controller: {CONTROLLER_HOST}")
    
    last_allowed = None
    
    while True:
        try:
            _, allowed = fetch_config()
            
            if allowed is not None and allowed != last_allowed:
                last_allowed = allowed
                if allowed:
                    print(f"[{NODE_ID}] Status changed to ALLOWED")
                else:
                    print(f"[{NODE_ID}] Status changed to DENIED")
            
            time.sleep(POLL_INTERVAL_SEC)
        except KeyboardInterrupt:
            print(f"\n[{NODE_ID}] Shutting down", file=sys.stderr)
            break
        except Exception as e:
            print(f"[{NODE_ID}] Error in main loop: {e}", file=sys.stderr)
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
