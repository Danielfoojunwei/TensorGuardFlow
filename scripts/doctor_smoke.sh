#!/bin/bash
#
# TensorGuardFlow System Doctor - Smoke Test
#
# End-to-end validation script that reproduces user-visible failures.
# Runs all critical paths and reports PASS/FAIL for each step.
#
# Usage:
#   ./scripts/doctor_smoke.sh              # Run against local (localhost:8000)
#   ./scripts/doctor_smoke.sh http://host  # Run against custom host
#
# Exit codes:
#   0 - All checks passed
#   1 - One or more checks failed
#

set -euo pipefail

# Configuration
API_BASE="${1:-http://localhost:8000}"
API_V1="${API_BASE}/api/v1"
TIMEOUT=10
PASS_COUNT=0
FAIL_COUNT=0
TEST_SUFFIX="$(date +%s)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test credentials
TEST_ORG="DoctorTestOrg_${TEST_SUFFIX}"
TEST_EMAIL="doctor_${TEST_SUFFIX}@test.com"
TEST_PASSWORD="SecurePassword123!"
TEST_FLEET="DoctorFleet_${TEST_SUFFIX}"

# State
AUTH_TOKEN=""
FLEET_ID=""
FLEET_API_KEY=""

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASS_COUNT++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    echo -e "${RED}       Error: $2${NC}"
    ((FAIL_COUNT++))
}

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

log_section() {
    echo ""
    echo "=============================================="
    echo "$1"
    echo "=============================================="
}

# Check if a command exists
require_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}[ERROR]${NC} Required command '$1' not found. Please install it."
        exit 1
    fi
}

# HTTP request helper with error handling
http_request() {
    local method="$1"
    local url="$2"
    local data="${3:-}"
    local headers="${4:-}"
    local auth_header=""

    if [[ -n "$AUTH_TOKEN" ]]; then
        auth_header="-H \"Authorization: Bearer ${AUTH_TOKEN}\""
    fi

    local curl_cmd="curl -s -w '\n%{http_code}' --max-time ${TIMEOUT}"

    if [[ -n "$headers" ]]; then
        curl_cmd="$curl_cmd $headers"
    fi

    if [[ -n "$auth_header" ]]; then
        curl_cmd="$curl_cmd $auth_header"
    fi

    case "$method" in
        GET)
            eval "$curl_cmd \"$url\""
            ;;
        POST)
            if [[ -n "$data" ]]; then
                eval "$curl_cmd -X POST -H 'Content-Type: application/json' -d '$data' \"$url\""
            else
                eval "$curl_cmd -X POST \"$url\""
            fi
            ;;
        DELETE)
            eval "$curl_cmd -X DELETE \"$url\""
            ;;
    esac
}

# Parse HTTP response (body and status code)
parse_response() {
    local response="$1"
    local last_line
    last_line=$(echo "$response" | tail -n1)
    local body
    body=$(echo "$response" | sed '$d')
    echo "$body"
    echo "$last_line"
}

#############################################################################
# TEST FUNCTIONS
#############################################################################

test_backend_reachable() {
    log_section "PHASE 1: Backend Reachability"

    local response
    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" "${API_BASE}/" 2>&1) || true
    local status_code
    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" =~ ^[0-9]+$ ]] && [[ "$status_code" -lt 500 ]]; then
        log_pass "Backend is reachable at ${API_BASE}"
    else
        log_fail "Backend not reachable at ${API_BASE}" "Status: ${status_code:-connection failed}"
        return 1
    fi
}

test_health_endpoint() {
    log_info "Testing health endpoints..."

    # Test /health
    local response
    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" "${API_BASE}/health" 2>&1) || true
    local body
    body=$(echo "$response" | sed '$d')
    local status_code
    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" == "200" ]]; then
        log_pass "/health returns 200"

        # Check if database is healthy
        if echo "$body" | grep -q '"database"'; then
            if echo "$body" | grep -q '"healthy"'; then
                log_pass "/health reports database healthy"
            else
                log_fail "/health reports database unhealthy" "$body"
            fi
        fi
    else
        log_fail "/health endpoint failed" "Status: $status_code, Body: $body"
    fi

    # Test /ready
    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" "${API_BASE}/ready" 2>&1) || true
    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" == "200" ]]; then
        log_pass "/ready returns 200"
    else
        log_fail "/ready endpoint failed" "Status: $status_code"
    fi

    # Test /live
    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" "${API_BASE}/live" 2>&1) || true
    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" == "200" ]]; then
        log_pass "/live returns 200"
    else
        log_fail "/live endpoint failed" "Status: $status_code"
    fi
}

test_onboarding() {
    log_section "PHASE 2: Admin Onboarding"

    local response
    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" \
        -X POST \
        "${API_V1}/onboarding/init?name=${TEST_ORG}&admin_email=${TEST_EMAIL}&admin_pass=${TEST_PASSWORD}" \
        2>&1) || true

    local body
    body=$(echo "$response" | sed '$d')
    local status_code
    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" == "200" ]]; then
        log_pass "Onboarding completed successfully"
        log_info "Created org: ${TEST_ORG}, user: ${TEST_EMAIL}"
    elif [[ "$status_code" == "400" ]] && echo "$body" | grep -q "already registered"; then
        log_info "User already exists (continuing with existing user)"
        log_pass "Onboarding endpoint works (user exists)"
    else
        log_fail "Onboarding failed" "Status: $status_code, Body: $body"
        return 1
    fi
}

test_login() {
    log_section "PHASE 3: Login Flow"

    local response
    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"${TEST_EMAIL}\", \"password\": \"${TEST_PASSWORD}\"}" \
        "${API_V1}/auth/token" \
        2>&1) || true

    local body
    body=$(echo "$response" | sed '$d')
    local status_code
    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" == "200" ]]; then
        AUTH_TOKEN=$(echo "$body" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
        if [[ -n "$AUTH_TOKEN" ]]; then
            log_pass "Login successful, obtained access token"
        else
            log_fail "Login response missing access_token" "$body"
            return 1
        fi
    else
        log_fail "Login failed" "Status: $status_code, Body: $body"
        return 1
    fi

    # Test /auth/me with token
    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        "${API_V1}/auth/me" \
        2>&1) || true

    body=$(echo "$response" | sed '$d')
    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" == "200" ]]; then
        log_pass "/auth/me returns current user"
    else
        log_fail "/auth/me failed with valid token" "Status: $status_code, Body: $body"
    fi
}

test_fleet_creation() {
    log_section "PHASE 4: Fleet Creation"

    if [[ -z "$AUTH_TOKEN" ]]; then
        log_fail "Cannot test fleet creation" "No auth token available"
        return 1
    fi

    local response
    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" \
        -X POST \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        "${API_V1}/fleets?name=${TEST_FLEET}" \
        2>&1) || true

    local body
    body=$(echo "$response" | sed '$d')
    local status_code
    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" == "200" ]]; then
        FLEET_ID=$(echo "$body" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
        FLEET_API_KEY=$(echo "$body" | grep -o '"api_key":"[^"]*"' | cut -d'"' -f4)

        if [[ -n "$FLEET_ID" ]] && [[ -n "$FLEET_API_KEY" ]]; then
            log_pass "Fleet created successfully"
            log_info "Fleet ID: ${FLEET_ID}"
            log_info "API Key: ${FLEET_API_KEY:0:20}... (truncated)"
        else
            log_fail "Fleet response missing id or api_key" "$body"
            return 1
        fi
    else
        log_fail "Fleet creation failed" "Status: $status_code, Body: $body"
        return 1
    fi

    # Test listing fleets
    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        "${API_V1}/fleets" \
        2>&1) || true

    body=$(echo "$response" | sed '$d')
    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" == "200" ]]; then
        log_pass "Fleet listing works"
    else
        log_fail "Fleet listing failed" "Status: $status_code, Body: $body"
    fi
}

test_telemetry_ingest() {
    log_section "PHASE 5: Telemetry Ingestion"

    if [[ -z "$FLEET_API_KEY" ]]; then
        log_fail "Cannot test telemetry ingest" "No fleet API key available"
        return 1
    fi

    local batch_id="doctor_batch_${TEST_SUFFIX}"
    local device_id="doctor_device_${TEST_SUFFIX}"
    local timestamp_ns=$(($(date +%s) * 1000000000))

    local payload='{
        "batch_id": "'"${batch_id}"'",
        "device_info": {
            "device_id": "'"${device_id}"'",
            "agent_version": "1.0.0-doctor",
            "runtime_version": "python3.11"
        },
        "messages": [
            {
                "topic": "telemetry.stage",
                "timestamp_ns": '"${timestamp_ns}"',
                "payload": {
                    "device_id": "'"${device_id}"'",
                    "stage": "capture",
                    "status": "ok",
                    "latency_ms": 42.5
                },
                "priority": 0
            },
            {
                "topic": "telemetry.system",
                "timestamp_ns": '"${timestamp_ns}"',
                "payload": {
                    "device_id": "'"${device_id}"'",
                    "cpu_pct": 45.2,
                    "mem_pct": 62.1
                },
                "priority": 0
            }
        ]
    }'

    local response
    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" \
        -X POST \
        -H "Authorization: Fleet ${FLEET_API_KEY}" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "${API_V1}/telemetry/ingest" \
        2>&1) || true

    local body
    body=$(echo "$response" | sed '$d')
    local status_code
    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" == "200" ]]; then
        local accepted
        accepted=$(echo "$body" | grep -o '"accepted":[0-9]*' | cut -d':' -f2)
        if [[ "$accepted" -gt 0 ]]; then
            log_pass "Telemetry ingest successful (accepted: $accepted)"
        else
            log_fail "Telemetry ingest accepted 0 messages" "$body"
        fi
    else
        log_fail "Telemetry ingest failed" "Status: $status_code, Body: $body"
        return 1
    fi
}

test_dashboard_stats() {
    log_section "PHASE 6: Dashboard Stats"

    if [[ -z "$AUTH_TOKEN" ]]; then
        log_fail "Cannot test dashboard" "No auth token available"
        return 1
    fi

    # Test pipeline telemetry
    local response
    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        "${API_V1}/telemetry/pipeline" \
        2>&1) || true

    local body
    body=$(echo "$response" | sed '$d')
    local status_code
    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" == "200" ]]; then
        log_pass "/telemetry/pipeline returns data"
    else
        log_fail "/telemetry/pipeline failed" "Status: $status_code, Body: $body"
    fi

    # Test devices endpoint
    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        "${API_V1}/telemetry/devices" \
        2>&1) || true

    body=$(echo "$response" | sed '$d')
    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" == "200" ]]; then
        log_pass "/telemetry/devices returns data"
    else
        log_fail "/telemetry/devices failed" "Status: $status_code, Body: $body"
    fi
}

test_key_rotation() {
    log_section "PHASE 7: Key Rotation"

    if [[ -z "$AUTH_TOKEN" ]] || [[ -z "$FLEET_ID" ]] || [[ -z "$FLEET_API_KEY" ]]; then
        log_fail "Cannot test key rotation" "Missing auth token, fleet ID, or API key"
        return 1
    fi

    local old_key="$FLEET_API_KEY"

    # Rotate the key
    local response
    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" \
        -X POST \
        -H "Authorization: Bearer ${AUTH_TOKEN}" \
        "${API_V1}/fleets/${FLEET_ID}/rotate-key" \
        2>&1) || true

    local body
    body=$(echo "$response" | sed '$d')
    local status_code
    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" == "200" ]]; then
        local new_key
        new_key=$(echo "$body" | grep -o '"api_key":"[^"]*"' | cut -d'"' -f4)

        if [[ -n "$new_key" ]] && [[ "$new_key" != "$old_key" ]]; then
            log_pass "Key rotation successful"
            FLEET_API_KEY="$new_key"
        else
            log_fail "Key rotation did not return new key" "$body"
            return 1
        fi
    else
        log_fail "Key rotation failed" "Status: $status_code, Body: $body"
        return 1
    fi

    # Verify old key fails
    local timestamp_ns=$(($(date +%s) * 1000000000))
    local payload='{
        "batch_id": "old_key_test",
        "device_info": {"device_id": "test"},
        "messages": []
    }'

    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" \
        -X POST \
        -H "Authorization: Fleet ${old_key}" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "${API_V1}/telemetry/ingest" \
        2>&1) || true

    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" == "401" ]]; then
        log_pass "Old key correctly rejected after rotation"
    else
        log_fail "Old key still works after rotation" "Status: $status_code"
    fi

    # Verify new key works
    response=$(curl -s -w '\n%{http_code}' --max-time "$TIMEOUT" \
        -X POST \
        -H "Authorization: Fleet ${FLEET_API_KEY}" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "${API_V1}/telemetry/ingest" \
        2>&1) || true

    status_code=$(echo "$response" | tail -n1)

    if [[ "$status_code" == "200" ]]; then
        log_pass "New key works after rotation"
    else
        log_fail "New key fails after rotation" "Status: $status_code"
    fi
}

#############################################################################
# MAIN
#############################################################################

main() {
    echo "=============================================="
    echo "  TensorGuardFlow System Doctor - Smoke Test"
    echo "=============================================="
    echo ""
    echo "Target: ${API_BASE}"
    echo "Test ID: ${TEST_SUFFIX}"
    echo ""

    # Check requirements
    require_command curl
    require_command grep

    # Run tests
    test_backend_reachable || true
    test_health_endpoint || true
    test_onboarding || true
    test_login || true
    test_fleet_creation || true
    test_telemetry_ingest || true
    test_dashboard_stats || true
    test_key_rotation || true

    # Summary
    log_section "SUMMARY"
    echo ""
    echo -e "  ${GREEN}Passed: ${PASS_COUNT}${NC}"
    echo -e "  ${RED}Failed: ${FAIL_COUNT}${NC}"
    echo ""

    if [[ $FAIL_COUNT -gt 0 ]]; then
        echo -e "${RED}Some checks failed. Review the output above for details.${NC}"
        exit 1
    else
        echo -e "${GREEN}All checks passed!${NC}"
        exit 0
    fi
}

main "$@"
