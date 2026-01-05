#!/bin/bash
# entrypoint.sh: Start node services (benchmark emitter, config agent, network probe)

set -e

NODE_ID="${NODE_ID:-node-a}"
CONTROLLER_HOST="${CONTROLLER_HOST:-http://controller:8000}"

echo "[$NODE_ID] Node starting..."
echo "[$NODE_ID] NODE_ID=$NODE_ID"
echo "[$NODE_ID] CONTROLLER_HOST=$CONTROLLER_HOST"
echo "[$NODE_ID] SCORE_MEAN=$SCORE_MEAN"

# Wait for controller to be ready
echo "[$NODE_ID] Waiting for controller..."
for i in {1..30}; do
    if curl -s "$CONTROLLER_HOST/health" > /dev/null 2>&1; then
        echo "[$NODE_ID] Controller is ready"
        break
    fi
    echo "[$NODE_ID] Waiting for controller... ($i/30)"
    sleep 1
done

# Start benchmark emitter in background
echo "[$NODE_ID] Starting benchmark emitter..."
python3 /app/scripts/benchmark_emitter.py &
EMITTER_PID=$!

# Start config agent in background
echo "[$NODE_ID] Starting config agent..."
python3 /app/scripts/config_agent.py &
CONFIG_PID=$!

# Start network probe in background
echo "[$NODE_ID] Starting network probe..."
bash /app/scripts/net_probe.sh &
PROBE_PID=$!

# Wait for any process to exit (should not happen unless error)
wait -n
EXIT_CODE=$?
echo "[$NODE_ID] A background process exited with code $EXIT_CODE"

# Kill remaining processes
kill $EMITTER_PID $CONFIG_PID $PROBE_PID 2>/dev/null || true

exit $EXIT_CODE
