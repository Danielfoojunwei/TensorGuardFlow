#!/bin/bash
#
# TensorGuard Edge Agent Diagnostic Script
#
# Performs quick health checks on edge devices without requiring Python.
# For more comprehensive diagnostics, use: python -m tensorguard.agent.diagnose
#
# Usage:
#   ./scripts/edge_diagnose.sh
#   ./scripts/edge_diagnose.sh --verbose
#   ./scripts/edge_diagnose.sh --json
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CONTROL_PLANE_URL="${TG_CONTROL_PLANE_URL:-http://localhost:8000}"
FLEET_API_KEY="${TG_FLEET_API_KEY:-}"
FLEET_ID="${TG_FLEET_ID:-}"
DATA_DIR="${TG_DATA_DIR:-./storage}"
VERBOSE=false
JSON_OUTPUT=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        -h|--help)
            echo "TensorGuard Edge Agent Diagnostic Script"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -v, --verbose    Show detailed output"
            echo "  --json           Output as JSON"
            echo "  -h, --help       Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Counters
OK_COUNT=0
WARN_COUNT=0
ERROR_COUNT=0
CHECKS=()

# Helper functions
log_check() {
    local status="$1"
    local name="$2"
    local message="$3"

    if [ "$JSON_OUTPUT" = true ]; then
        CHECKS+=("{\"name\":\"$name\",\"status\":\"$status\",\"message\":\"$message\"}")
    else
        case "$status" in
            ok)
                echo -e "  [${GREEN}✓${NC}] $name: $message"
                ;;
            warning)
                echo -e "  [${YELLOW}⚠${NC}] $name: $message"
                ;;
            error)
                echo -e "  [${RED}✗${NC}] $name: $message"
                ;;
            skipped)
                echo -e "  [○] $name: $message"
                ;;
        esac
    fi

    case "$status" in
        ok) ((OK_COUNT++)) || true ;;
        warning) ((WARN_COUNT++)) || true ;;
        error) ((ERROR_COUNT++)) || true ;;
    esac
}

# Check: Environment variables
check_environment() {
    if [ "$VERBOSE" = true ]; then
        echo "Checking environment..."
    fi

    if [ -z "$FLEET_API_KEY" ]; then
        log_check "error" "env_api_key" "TG_FLEET_API_KEY not set"
    else
        log_check "ok" "env_api_key" "TG_FLEET_API_KEY is set"
    fi

    if [ -z "$FLEET_ID" ]; then
        log_check "error" "env_fleet_id" "TG_FLEET_ID not set"
    else
        log_check "ok" "env_fleet_id" "TG_FLEET_ID is set ($FLEET_ID)"
    fi
}

# Check: Control plane connectivity
check_connectivity() {
    if [ "$VERBOSE" = true ]; then
        echo "Checking control plane connectivity..."
    fi

    # Extract host and port from URL
    local host=$(echo "$CONTROL_PLANE_URL" | sed -E 's|https?://||' | cut -d: -f1 | cut -d/ -f1)
    local port=$(echo "$CONTROL_PLANE_URL" | sed -E 's|https?://[^:]+:?||' | cut -d/ -f1)

    if [ -z "$port" ]; then
        if [[ "$CONTROL_PLANE_URL" == https://* ]]; then
            port=443
        else
            port=80
        fi
    fi

    # TCP connectivity check
    if command -v nc &> /dev/null; then
        if nc -z -w 5 "$host" "$port" 2>/dev/null; then
            log_check "ok" "tcp_connect" "TCP connection to $host:$port successful"
        else
            log_check "error" "tcp_connect" "Cannot connect to $host:$port"
            return
        fi
    elif command -v timeout &> /dev/null; then
        if timeout 5 bash -c "echo >/dev/tcp/$host/$port" 2>/dev/null; then
            log_check "ok" "tcp_connect" "TCP connection to $host:$port successful"
        else
            log_check "error" "tcp_connect" "Cannot connect to $host:$port"
            return
        fi
    else
        log_check "skipped" "tcp_connect" "nc/timeout not available"
    fi

    # HTTP health check
    if command -v curl &> /dev/null; then
        local http_code
        http_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$CONTROL_PLANE_URL/health" 2>/dev/null || echo "000")

        if [ "$http_code" = "200" ]; then
            log_check "ok" "health_endpoint" "Health endpoint responding (HTTP $http_code)"
        elif [ "$http_code" = "000" ]; then
            log_check "error" "health_endpoint" "Cannot reach health endpoint"
        else
            log_check "warning" "health_endpoint" "Health endpoint returned HTTP $http_code"
        fi
    elif command -v wget &> /dev/null; then
        if wget -q --spider --timeout=5 "$CONTROL_PLANE_URL/health" 2>/dev/null; then
            log_check "ok" "health_endpoint" "Health endpoint responding"
        else
            log_check "warning" "health_endpoint" "Health endpoint not responding"
        fi
    else
        log_check "skipped" "health_endpoint" "curl/wget not available"
    fi
}

# Check: DNS resolution
check_dns() {
    if [ "$VERBOSE" = true ]; then
        echo "Checking DNS resolution..."
    fi

    local host=$(echo "$CONTROL_PLANE_URL" | sed -E 's|https?://||' | cut -d: -f1 | cut -d/ -f1)

    # Skip localhost
    if [ "$host" = "localhost" ] || [ "$host" = "127.0.0.1" ]; then
        log_check "skipped" "dns" "Localhost - DNS check skipped"
        return
    fi

    if command -v nslookup &> /dev/null; then
        if nslookup "$host" &>/dev/null; then
            log_check "ok" "dns" "DNS resolution for $host successful"
        else
            log_check "error" "dns" "DNS resolution for $host failed"
        fi
    elif command -v host &> /dev/null; then
        if host "$host" &>/dev/null; then
            log_check "ok" "dns" "DNS resolution for $host successful"
        else
            log_check "error" "dns" "DNS resolution for $host failed"
        fi
    else
        log_check "skipped" "dns" "nslookup/host not available"
    fi
}

# Check: File system
check_filesystem() {
    if [ "$VERBOSE" = true ]; then
        echo "Checking file system..."
    fi

    # Check data directory
    if [ -d "$DATA_DIR" ]; then
        if [ -w "$DATA_DIR" ]; then
            log_check "ok" "data_dir" "Data directory writable ($DATA_DIR)"
        else
            log_check "error" "data_dir" "Data directory not writable ($DATA_DIR)"
        fi
    else
        # Try to create it
        if mkdir -p "$DATA_DIR" 2>/dev/null; then
            log_check "ok" "data_dir" "Data directory created ($DATA_DIR)"
        else
            log_check "error" "data_dir" "Cannot create data directory ($DATA_DIR)"
        fi
    fi

    # Check disk space
    if command -v df &> /dev/null; then
        local available_kb
        available_kb=$(df -k "$DATA_DIR" 2>/dev/null | tail -1 | awk '{print $4}')
        if [ -n "$available_kb" ]; then
            local available_gb=$((available_kb / 1024 / 1024))
            if [ "$available_gb" -lt 1 ]; then
                log_check "warning" "disk_space" "Low disk space: ${available_gb}GB available"
            else
                log_check "ok" "disk_space" "Disk space OK: ${available_gb}GB available"
            fi
        fi
    else
        log_check "skipped" "disk_space" "df not available"
    fi
}

# Check: Python environment
check_python() {
    if [ "$VERBOSE" = true ]; then
        echo "Checking Python environment..."
    fi

    if command -v python3 &> /dev/null; then
        local py_version
        py_version=$(python3 --version 2>&1 | cut -d' ' -f2)
        log_check "ok" "python" "Python $py_version available"

        # Check if tensorguard is importable
        if python3 -c "import tensorguard" 2>/dev/null; then
            log_check "ok" "tensorguard_module" "tensorguard module importable"
        else
            log_check "warning" "tensorguard_module" "tensorguard module not importable"
        fi
    else
        log_check "warning" "python" "Python 3 not found"
    fi
}

# Check: System resources
check_resources() {
    if [ "$VERBOSE" = true ]; then
        echo "Checking system resources..."
    fi

    # Memory
    if command -v free &> /dev/null; then
        local available_mb
        available_mb=$(free -m 2>/dev/null | awk '/^Mem:/ {print $7}')
        if [ -n "$available_mb" ]; then
            if [ "$available_mb" -lt 512 ]; then
                log_check "warning" "memory" "Low memory: ${available_mb}MB available"
            else
                log_check "ok" "memory" "Memory OK: ${available_mb}MB available"
            fi
        fi
    else
        log_check "skipped" "memory" "free command not available"
    fi

    # CPU load
    if command -v uptime &> /dev/null; then
        local load
        load=$(uptime | awk -F'load average:' '{print $2}' | cut -d, -f1 | xargs)
        if [ -n "$load" ]; then
            # Compare to 4.0 (rough threshold)
            if awk "BEGIN {exit !($load > 4.0)}"; then
                log_check "warning" "cpu_load" "High CPU load: $load"
            else
                log_check "ok" "cpu_load" "CPU load OK: $load"
            fi
        fi
    else
        log_check "skipped" "cpu_load" "uptime not available"
    fi
}

# Main
main() {
    if [ "$JSON_OUTPUT" = false ]; then
        echo ""
        echo "=== TensorGuard Edge Agent Diagnostics ==="
        echo ""
    fi

    check_environment
    check_dns
    check_connectivity
    check_filesystem
    check_python
    check_resources

    # Determine overall status
    local overall="healthy"
    if [ "$ERROR_COUNT" -gt 0 ]; then
        overall="unhealthy"
    elif [ "$WARN_COUNT" -gt 0 ]; then
        overall="degraded"
    fi

    if [ "$JSON_OUTPUT" = true ]; then
        # Build JSON output
        local checks_json
        checks_json=$(printf '%s\n' "${CHECKS[@]}" | paste -sd, -)
        echo "{"
        echo "  \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
        echo "  \"overall_status\": \"$overall\","
        echo "  \"summary\": {"
        echo "    \"ok\": $OK_COUNT,"
        echo "    \"warning\": $WARN_COUNT,"
        echo "    \"error\": $ERROR_COUNT"
        echo "  },"
        echo "  \"checks\": [$checks_json],"
        echo "  \"environment\": {"
        echo "    \"hostname\": \"$(hostname)\","
        echo "    \"control_plane_url\": \"$CONTROL_PLANE_URL\","
        echo "    \"fleet_id\": \"$FLEET_ID\""
        echo "  }"
        echo "}"
    else
        echo ""
        echo "=== Summary ==="

        case "$overall" in
            healthy)
                echo -e "Status: ${GREEN}HEALTHY${NC}"
                ;;
            degraded)
                echo -e "Status: ${YELLOW}DEGRADED${NC}"
                ;;
            unhealthy)
                echo -e "Status: ${RED}UNHEALTHY${NC}"
                ;;
        esac

        echo "  OK: $OK_COUNT, Warnings: $WARN_COUNT, Errors: $ERROR_COUNT"
        echo ""
    fi

    # Exit code
    if [ "$overall" = "unhealthy" ]; then
        exit 1
    else
        exit 0
    fi
}

main
