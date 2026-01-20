#!/usr/bin/env bash
# TensorGuardFlow Diagnostics Collection Script
# Collects system information, logs, and health data for support

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="$PROJECT_ROOT/artifacts/diagnostics/$TIMESTAMP"
BUNDLE_NAME="tgf_diagnostics_$TIMESTAMP.zip"

echo "=============================================="
echo "TensorGuardFlow Diagnostics Collection"
echo "=============================================="
echo "Timestamp: $TIMESTAMP"
echo "Output: $OUTPUT_DIR"
echo ""

mkdir -p "$OUTPUT_DIR"

cd "$PROJECT_ROOT"

# ==============================================================================
# 1. SYSTEM INFORMATION
# ==============================================================================
echo "Collecting system information..."

cat > "$OUTPUT_DIR/system_info.txt" << EOF
TensorGuardFlow Diagnostics Report
Generated: $(date)
==================================

SYSTEM INFORMATION
==================
Hostname: $(hostname 2>/dev/null || echo "unknown")
OS: $(uname -s) $(uname -r)
Architecture: $(uname -m)
User: $(whoami)

PYTHON ENVIRONMENT
==================
$(python3 --version 2>&1 || echo "Python not available")
$(pip --version 2>&1 || echo "Pip not available")

NODE ENVIRONMENT
================
$(node --version 2>&1 || echo "Node not available")
$(npm --version 2>&1 || echo "npm not available")

DOCKER
======
$(docker --version 2>&1 || echo "Docker not available")
$(docker compose version 2>&1 || echo "Docker Compose not available")

TENSORGUARDFLOW VERSION
=======================
$(grep 'version = ' "$PROJECT_ROOT/pyproject.toml" 2>/dev/null | head -1 || echo "unknown")
Git commit: $(git rev-parse --short HEAD 2>/dev/null || echo "not a git repo")
Git branch: $(git branch --show-current 2>/dev/null || echo "unknown")

DISK SPACE
==========
$(df -h "$PROJECT_ROOT" 2>/dev/null || echo "df not available")

MEMORY
======
$(free -h 2>/dev/null || echo "free not available")

ENVIRONMENT VARIABLES (TG_*)
============================
$(env | grep "^TG_" | sed 's/=.*/=***/' 2>/dev/null || echo "none set")
EOF

echo "  Saved system_info.txt"

# ==============================================================================
# 2. CONFIGURATION FILES (sanitized)
# ==============================================================================
echo "Collecting configuration..."

mkdir -p "$OUTPUT_DIR/config"

# Copy config files (without secrets)
if [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
    cp "$PROJECT_ROOT/pyproject.toml" "$OUTPUT_DIR/config/"
fi

if [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
    cp "$PROJECT_ROOT/docker-compose.yml" "$OUTPUT_DIR/config/"
fi

if [ -f "$PROJECT_ROOT/pytest.ini" ]; then
    cp "$PROJECT_ROOT/pytest.ini" "$OUTPUT_DIR/config/"
fi

# Sanitize .env if it exists
if [ -f "$PROJECT_ROOT/.env" ]; then
    sed 's/=.*/=***REDACTED***/' "$PROJECT_ROOT/.env" > "$OUTPUT_DIR/config/env_sanitized.txt"
fi

echo "  Saved config files"

# ==============================================================================
# 3. DOCKER LOGS (if running)
# ==============================================================================
echo "Collecting Docker logs..."

mkdir -p "$OUTPUT_DIR/logs"

if command -v docker &>/dev/null && docker info &>/dev/null; then
    # Get container logs
    for container in $(docker ps --format '{{.Names}}' 2>/dev/null | grep -E 'tensor|tgf' || true); do
        echo "  Collecting logs from: $container"
        docker logs "$container" --tail 500 2>&1 > "$OUTPUT_DIR/logs/docker_${container}.log" || true
    done

    # Container status
    docker ps -a --filter "name=tensor" --filter "name=tgf" > "$OUTPUT_DIR/logs/docker_ps.txt" 2>/dev/null || true

    # Docker inspect
    for container in $(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -E 'tensor|tgf' || true); do
        docker inspect "$container" > "$OUTPUT_DIR/logs/docker_inspect_${container}.json" 2>/dev/null || true
    done
else
    echo "  Docker not available or not running"
fi

echo "  Saved Docker logs"

# ==============================================================================
# 4. APPLICATION LOGS
# ==============================================================================
echo "Collecting application logs..."

# Check common log locations
LOG_DIRS=(
    "$PROJECT_ROOT/logs"
    "$PROJECT_ROOT/artifacts"
    "/var/log/tensorguard"
    "/tmp/tensorguard"
)

for log_dir in "${LOG_DIRS[@]}"; do
    if [ -d "$log_dir" ]; then
        # Copy recent log files (last 24h, max 10MB each)
        find "$log_dir" -name "*.log" -mtime -1 -size -10M -exec cp {} "$OUTPUT_DIR/logs/" \; 2>/dev/null || true
    fi
done

echo "  Saved application logs"

# ==============================================================================
# 5. DATABASE HEALTH (if accessible)
# ==============================================================================
echo "Collecting database health..."

cat > "$OUTPUT_DIR/db_health.txt" << EOF
DATABASE HEALTH CHECK
=====================
Timestamp: $(date)

EOF

# Try to connect and get basic info
if [ -f "$PROJECT_ROOT/tg_platform.db" ]; then
    echo "SQLite database found" >> "$OUTPUT_DIR/db_health.txt"
    echo "Size: $(du -h "$PROJECT_ROOT/tg_platform.db" | cut -f1)" >> "$OUTPUT_DIR/db_health.txt"
    # Don't copy the actual database (security)
else
    echo "No local SQLite database found" >> "$OUTPUT_DIR/db_health.txt"
fi

echo "  Saved db_health.txt"

# ==============================================================================
# 6. HEALTH CHECK RESULTS
# ==============================================================================
echo "Running health checks..."

cat > "$OUTPUT_DIR/health_check.txt" << EOF
HEALTH CHECK RESULTS
====================
Timestamp: $(date)

EOF

# API health check
if curl -sf http://localhost:8000/health > "$OUTPUT_DIR/api_health.json" 2>/dev/null; then
    echo "API Health: OK" >> "$OUTPUT_DIR/health_check.txt"
    cat "$OUTPUT_DIR/api_health.json" >> "$OUTPUT_DIR/health_check.txt"
else
    echo "API Health: NOT REACHABLE" >> "$OUTPUT_DIR/health_check.txt"
fi

echo "" >> "$OUTPUT_DIR/health_check.txt"

# Status endpoints
if curl -sf http://localhost:8000/api/v1/status/health > "$OUTPUT_DIR/status_health.json" 2>/dev/null; then
    echo "Status Health: OK" >> "$OUTPUT_DIR/health_check.txt"
else
    echo "Status Health: NOT REACHABLE (may require auth)" >> "$OUTPUT_DIR/health_check.txt"
fi

echo "  Saved health_check.txt"

# ==============================================================================
# 7. RECENT ERRORS
# ==============================================================================
echo "Collecting recent errors..."

cat > "$OUTPUT_DIR/recent_errors.txt" << EOF
RECENT ERRORS
=============
Timestamp: $(date)

EOF

# Search logs for errors
if [ -d "$OUTPUT_DIR/logs" ]; then
    grep -l -r -i "error\|exception\|failed\|critical" "$OUTPUT_DIR/logs/" 2>/dev/null | while read -r file; do
        echo "=== $file ===" >> "$OUTPUT_DIR/recent_errors.txt"
        grep -i "error\|exception\|failed\|critical" "$file" | tail -50 >> "$OUTPUT_DIR/recent_errors.txt"
        echo "" >> "$OUTPUT_DIR/recent_errors.txt"
    done
fi

echo "  Saved recent_errors.txt"

# ==============================================================================
# 8. CREATE ZIP BUNDLE
# ==============================================================================
echo ""
echo "Creating diagnostics bundle..."

cd "$OUTPUT_DIR/.."
if command -v zip &>/dev/null; then
    zip -r "$BUNDLE_NAME" "$TIMESTAMP" -x "*.zip"
    mv "$BUNDLE_NAME" "$OUTPUT_DIR/"
    echo "Bundle created: $OUTPUT_DIR/$BUNDLE_NAME"
else
    tar -czf "${BUNDLE_NAME%.zip}.tar.gz" "$TIMESTAMP"
    mv "${BUNDLE_NAME%.zip}.tar.gz" "$OUTPUT_DIR/"
    echo "Bundle created: $OUTPUT_DIR/${BUNDLE_NAME%.zip}.tar.gz"
fi

# ==============================================================================
# SUMMARY
# ==============================================================================
echo ""
echo "=============================================="
echo "Diagnostics Collection Complete"
echo "=============================================="
echo ""
echo "Output directory: $OUTPUT_DIR"
echo ""
echo "Contents:"
ls -la "$OUTPUT_DIR"
echo ""
echo "To share with support, send the zip/tar.gz bundle."
echo "NOTE: Configuration files have been sanitized to remove secrets."
