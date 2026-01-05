#!/bin/bash
# net_probe.sh: Periodically ping other nodes to test connectivity.

NODE_ID="${NODE_ID:-node-a}"
PROBE_INTERVAL_SEC="${PROBE_INTERVAL_SEC:-15}"
WG_SUBNET="${WG_SUBNET:-10.10.0.0/24}"

# Map node to WG IP (must match Terraform/controller)
declare -A NODE_IPS=(
    ["node-a"]="10.10.0.2"
    ["node-b"]="10.10.0.3"
    ["node-c"]="10.10.0.4"
)

# List of peers to ping
declare -a PEERS=("node-a" "node-b" "node-c")

echo "[$NODE_ID] Network probe starting (interval=${PROBE_INTERVAL_SEC}s)"

while true; do
    for peer in "${PEERS[@]}"; do
        if [ "$peer" != "$NODE_ID" ]; then
            peer_ip="${NODE_IPS[$peer]}"
            
            # Try ping (1 packet, 2 second timeout)
            if ping -c 1 -W 2 "$peer_ip" >/dev/null 2>&1; then
                echo "[$NODE_ID] PING $peer OK ($peer_ip)"
            else
                echo "[$NODE_ID] PING $peer FAIL (no route to $peer_ip)"
            fi
        fi
    done
    
    sleep "$PROBE_INTERVAL_SEC"
done
