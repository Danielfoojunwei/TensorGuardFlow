#!/bin/bash
# Edge Agent Launcher
# Starts uploader thread and ROS 2 node

# 1. Config
# Note: Telemetry endpoint is at /api/v1/telemetry (not /enablement)
API_URL="${TG_API_URL:-http://localhost:8000/api/v1/telemetry}"
FLEET_ID="${TG_FLEET_ID:-dev-fleet}"
API_KEY="${TG_FLEET_API_KEY:-dev_key}"
DB_PATH="${TG_SPOOL_DB_PATH:-/var/lib/tensorguard/spool.db}"

echo "Starting TensorGuard Edge Agent..."
echo "  API URL: $API_URL"
echo "  Fleet ID: $FLEET_ID"

# Ensure spool directory exists
mkdir -p "$(dirname "$DB_PATH")"

# 2. Run Python Agent
# Start Uploader (Background)
python -m tensorguard.edge_agent.main \
  --db-path "$DB_PATH" \
  --url "$API_URL" \
  --fleet-id "$FLEET_ID" \
  --api-key "$API_KEY" &
UPLOADER_PID=$!

# Start ROS Node (Foreground) if available
if python -c "import tensorguard.edge_agent.ros2_node" 2>/dev/null; then
    python -m tensorguard.edge_agent.ros2_node
    NODE_EXIT=$?
else
    echo "ROS 2 node not available, running uploader only..."
    # Wait for uploader
    wait $UPLOADER_PID
    NODE_EXIT=$?
fi

kill $UPLOADER_PID 2>/dev/null
exit $NODE_EXIT
