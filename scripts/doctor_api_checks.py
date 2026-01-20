#!/usr/bin/env python3
"""
TensorGuardFlow System Doctor - API Contract Checks

Validates all critical API endpoints for:
- Route existence (no 404s)
- Authentication requirements
- Response schema correctness
- Error response format

Usage:
    python scripts/doctor_api_checks.py              # Run against localhost:8000
    python scripts/doctor_api_checks.py --host URL   # Run against custom host

Exit codes:
    0 - All checks passed
    1 - One or more checks failed
"""

import argparse
import json
import sys
import time
import secrets
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode


@dataclass
class TestResult:
    """Result of a single API test."""
    name: str
    passed: bool
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class TestContext:
    """Shared context across tests."""
    base_url: str
    auth_token: Optional[str] = None
    fleet_id: Optional[str] = None
    fleet_api_key: Optional[str] = None
    org_id: Optional[str] = None
    test_suffix: str = field(default_factory=lambda: str(int(time.time())))


class APIChecker:
    """API contract checker."""

    def __init__(self, base_url: str):
        self.ctx = TestContext(base_url=base_url.rstrip('/'))
        self.results: List[TestResult] = []

    def http_request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        auth: str = "none",  # "none", "bearer", "fleet"
        timeout: int = 10,
    ) -> tuple[int, Dict[str, Any], str]:
        """
        Make an HTTP request and return (status_code, json_body, raw_body).
        """
        url = f"{self.ctx.base_url}{path}"
        req_headers = {"Content-Type": "application/json"}

        if headers:
            req_headers.update(headers)

        if auth == "bearer" and self.ctx.auth_token:
            req_headers["Authorization"] = f"Bearer {self.ctx.auth_token}"
        elif auth == "fleet" and self.ctx.fleet_api_key:
            req_headers["Authorization"] = f"Fleet {self.ctx.fleet_api_key}"

        body = json.dumps(data).encode() if data else None

        req = Request(url, data=body, headers=req_headers, method=method)

        try:
            with urlopen(req, timeout=timeout) as response:
                raw = response.read().decode()
                try:
                    return response.status, json.loads(raw), raw
                except json.JSONDecodeError:
                    return response.status, {}, raw
        except HTTPError as e:
            raw = e.read().decode() if e.fp else ""
            try:
                return e.code, json.loads(raw), raw
            except json.JSONDecodeError:
                return e.code, {"error": raw}, raw
        except URLError as e:
            return 0, {"error": str(e.reason)}, str(e.reason)
        except Exception as e:
            return 0, {"error": str(e)}, str(e)

    def add_result(self, name: str, passed: bool, message: str, details: Optional[Dict] = None):
        """Add a test result."""
        result = TestResult(name=name, passed=passed, message=message, details=details)
        self.results.append(result)

        # Print result immediately
        status = "\033[32m[PASS]\033[0m" if passed else "\033[31m[FAIL]\033[0m"
        print(f"{status} {name}: {message}")
        if details and not passed:
            print(f"       Details: {json.dumps(details, indent=2)[:500]}")

    # ==========================================================================
    # PUBLIC ENDPOINT TESTS
    # ==========================================================================

    def test_health_endpoints(self):
        """Test health check endpoints don't require auth."""
        print("\n=== Health Endpoints (No Auth Required) ===")

        endpoints = [
            ("GET", "/health", "Main health check"),
            ("GET", "/ready", "Readiness probe"),
            ("GET", "/live", "Liveness probe"),
            ("GET", "/api/v1/health", "API v1 health alias"),
        ]

        for method, path, desc in endpoints:
            status, body, _ = self.http_request(method, path, auth="none")

            if status == 200:
                self.add_result(desc, True, f"{path} returns 200")
            else:
                self.add_result(desc, False, f"{path} returned {status}", {"body": body})

    def test_docs_endpoint(self):
        """Test OpenAPI docs are accessible."""
        print("\n=== Documentation Endpoints ===")

        status, _, _ = self.http_request("GET", "/docs")
        if status == 200:
            self.add_result("OpenAPI Docs", True, "/docs accessible")
        else:
            self.add_result("OpenAPI Docs", False, f"/docs returned {status}")

    # ==========================================================================
    # AUTHENTICATION TESTS
    # ==========================================================================

    def test_auth_required_endpoints(self):
        """Test that protected endpoints require authentication."""
        print("\n=== Auth Required Endpoints (Should Return 401 Without Token) ===")

        endpoints = [
            ("GET", "/api/v1/fleets"),
            ("GET", "/api/v1/fleets/extended"),
            ("GET", "/api/v1/jobs"),
            ("GET", "/api/v1/telemetry/pipeline"),
            ("GET", "/api/v1/telemetry/devices"),
            ("GET", "/api/v1/auth/me"),
            ("GET", "/api/v1/users/me"),
        ]

        for method, path in endpoints:
            status, body, _ = self.http_request(method, path, auth="none")

            if status == 401:
                self.add_result(f"Auth required: {path}", True, "Returns 401 without token")
            elif status == 404:
                self.add_result(f"Auth required: {path}", False, "Route not found (404)", {"body": body})
            else:
                self.add_result(f"Auth required: {path}", False, f"Expected 401, got {status}", {"body": body})

    def test_onboarding_and_login(self):
        """Test onboarding and login flow."""
        print("\n=== Onboarding & Login Flow ===")

        test_org = f"DocCheckOrg_{self.ctx.test_suffix}"
        test_email = f"doccheck_{self.ctx.test_suffix}@test.com"
        test_password = "SecurePassword123!"

        # Onboarding
        path = f"/api/v1/onboarding/init?name={test_org}&admin_email={test_email}&admin_pass={test_password}"
        status, body, _ = self.http_request("POST", path)

        if status == 200:
            self.ctx.org_id = body.get("id")
            self.add_result("Onboarding", True, "Created new organization")
        elif status == 400 and "already registered" in str(body):
            self.add_result("Onboarding", True, "User already exists (expected)")
        else:
            self.add_result("Onboarding", False, f"Failed with status {status}", {"body": body})

        # Login
        status, body, _ = self.http_request(
            "POST",
            "/api/v1/auth/token",
            data={"username": test_email, "password": test_password}
        )

        if status == 200 and "access_token" in body:
            self.ctx.auth_token = body["access_token"]
            self.add_result("Login", True, "Obtained access token")
        else:
            self.add_result("Login", False, f"Failed with status {status}", {"body": body})

        # Verify token works
        if self.ctx.auth_token:
            status, body, _ = self.http_request("GET", "/api/v1/auth/me", auth="bearer")
            if status == 200:
                self.add_result("Token Verification", True, "/auth/me works with token")
            else:
                self.add_result("Token Verification", False, f"Token rejected: {status}", {"body": body})

    # ==========================================================================
    # FLEET ENDPOINT TESTS
    # ==========================================================================

    def test_fleet_endpoints(self):
        """Test fleet management endpoints."""
        print("\n=== Fleet Management Endpoints ===")

        if not self.ctx.auth_token:
            self.add_result("Fleet Tests", False, "Skipped - no auth token")
            return

        # Create fleet
        fleet_name = f"DocCheckFleet_{self.ctx.test_suffix}"
        status, body, _ = self.http_request(
            "POST",
            f"/api/v1/fleets?name={fleet_name}",
            auth="bearer"
        )

        if status == 200 and "id" in body and "api_key" in body:
            self.ctx.fleet_id = body["id"]
            self.ctx.fleet_api_key = body["api_key"]
            self.add_result("Create Fleet", True, f"Created fleet {self.ctx.fleet_id[:8]}...")
        else:
            self.add_result("Create Fleet", False, f"Status {status}", {"body": body})
            return

        # List fleets
        status, body, _ = self.http_request("GET", "/api/v1/fleets", auth="bearer")
        if status == 200:
            self.add_result("List Fleets", True, f"Found {len(body) if isinstance(body, list) else 0} fleets")
        else:
            self.add_result("List Fleets", False, f"Status {status}", {"body": body})

        # Extended fleets
        status, body, _ = self.http_request("GET", "/api/v1/fleets/extended", auth="bearer")
        if status == 200:
            self.add_result("Extended Fleets", True, "Endpoint works")
        else:
            self.add_result("Extended Fleets", False, f"Status {status}", {"body": body})

    # ==========================================================================
    # TELEMETRY ENDPOINT TESTS
    # ==========================================================================

    def test_telemetry_ingest(self):
        """Test telemetry ingestion with Fleet auth."""
        print("\n=== Telemetry Ingestion (Fleet Auth) ===")

        if not self.ctx.fleet_api_key:
            self.add_result("Telemetry Ingest", False, "Skipped - no fleet API key")
            return

        batch = {
            "batch_id": f"doccheck_{self.ctx.test_suffix}",
            "device_info": {
                "device_id": f"device_{self.ctx.test_suffix}",
                "agent_version": "1.0.0-doccheck"
            },
            "messages": [
                {
                    "topic": "telemetry.stage",
                    "timestamp_ns": int(time.time() * 1e9),
                    "payload": {
                        "device_id": f"device_{self.ctx.test_suffix}",
                        "stage": "capture",
                        "status": "ok",
                        "latency_ms": 50.0
                    },
                    "priority": 0
                }
            ]
        }

        status, body, _ = self.http_request(
            "POST",
            "/api/v1/telemetry/ingest",
            data=batch,
            auth="fleet"
        )

        if status == 200:
            accepted = body.get("accepted", 0)
            self.add_result("Telemetry Ingest", True, f"Accepted {accepted} messages")
        else:
            self.add_result("Telemetry Ingest", False, f"Status {status}", {"body": body})

        # Test invalid fleet key
        old_key = self.ctx.fleet_api_key
        self.ctx.fleet_api_key = "invalid_key"
        status, _, _ = self.http_request(
            "POST",
            "/api/v1/telemetry/ingest",
            data=batch,
            auth="fleet"
        )
        self.ctx.fleet_api_key = old_key

        if status == 401:
            self.add_result("Invalid Fleet Key", True, "Correctly rejected")
        else:
            self.add_result("Invalid Fleet Key", False, f"Expected 401, got {status}")

    def test_telemetry_query_endpoints(self):
        """Test telemetry query endpoints."""
        print("\n=== Telemetry Query Endpoints (Bearer Auth) ===")

        if not self.ctx.auth_token:
            self.add_result("Telemetry Query", False, "Skipped - no auth token")
            return

        endpoints = [
            "/api/v1/telemetry/pipeline",
            "/api/v1/telemetry/edge",
            "/api/v1/telemetry/system",
            "/api/v1/telemetry/devices",
            "/api/v1/telemetry/forensics",
        ]

        for path in endpoints:
            status, body, _ = self.http_request("GET", path, auth="bearer")
            name = path.split("/")[-1]

            if status == 200:
                self.add_result(f"Query {name}", True, "Returns data")
            elif status == 404:
                self.add_result(f"Query {name}", False, "Route not found (404)")
            else:
                self.add_result(f"Query {name}", False, f"Status {status}", {"body": body})

    # ==========================================================================
    # KEY ROTATION TEST
    # ==========================================================================

    def test_key_rotation(self):
        """Test fleet key rotation."""
        print("\n=== Key Rotation ===")

        if not self.ctx.auth_token or not self.ctx.fleet_id:
            self.add_result("Key Rotation", False, "Skipped - no auth token or fleet")
            return

        old_key = self.ctx.fleet_api_key

        status, body, _ = self.http_request(
            "POST",
            f"/api/v1/fleets/{self.ctx.fleet_id}/rotate-key",
            auth="bearer"
        )

        if status == 200 and "api_key" in body:
            new_key = body["api_key"]
            if new_key != old_key:
                self.ctx.fleet_api_key = new_key
                self.add_result("Key Rotation", True, "New key issued")

                # Verify old key fails
                temp_key = self.ctx.fleet_api_key
                self.ctx.fleet_api_key = old_key
                status, _, _ = self.http_request(
                    "POST",
                    "/api/v1/telemetry/ingest",
                    data={"batch_id": "test", "device_info": {"device_id": "test"}, "messages": []},
                    auth="fleet"
                )
                self.ctx.fleet_api_key = temp_key

                if status == 401:
                    self.add_result("Old Key Revoked", True, "Old key correctly rejected")
                else:
                    self.add_result("Old Key Revoked", False, f"Old key still works: {status}")
            else:
                self.add_result("Key Rotation", False, "New key same as old")
        else:
            self.add_result("Key Rotation", False, f"Status {status}", {"body": body})

    # ==========================================================================
    # FRONTEND CONTRACT TESTS
    # ==========================================================================

    def test_frontend_contract(self):
        """Test endpoints that frontend depends on."""
        print("\n=== Frontend API Contract ===")

        if not self.ctx.auth_token:
            self.add_result("Frontend Contract", False, "Skipped - no auth token")
            return

        # These are the critical endpoints the frontend calls
        endpoints = [
            ("GET", "/api/v1/fleets/extended", "Fleet listing"),
            ("GET", "/api/v1/telemetry/pipeline", "Dashboard telemetry"),
            ("GET", "/api/v1/enablement/stats", "Enablement stats"),
            ("GET", "/api/v1/identity/inventory", "Identity inventory"),
            ("GET", "/api/v1/fedmoe/experts", "FedMoE experts"),
            ("GET", "/api/v1/vla/models", "VLA models"),
            ("GET", "/api/v1/kms/keys", "KMS keys"),
            ("GET", "/api/v1/peft/profiles", "PEFT profiles"),
        ]

        for method, path, desc in endpoints:
            status, body, _ = self.http_request(method, path, auth="bearer")

            if status == 200:
                self.add_result(f"FE: {desc}", True, f"{path} accessible")
            elif status == 404:
                self.add_result(f"FE: {desc}", False, f"{path} not found (404)")
            elif status == 500:
                self.add_result(f"FE: {desc}", False, f"{path} server error", {"body": body})
            else:
                self.add_result(f"FE: {desc}", False, f"{path} returned {status}", {"body": body})

    # ==========================================================================
    # ERROR RESPONSE FORMAT
    # ==========================================================================

    def test_error_response_format(self):
        """Test that error responses follow consistent format."""
        print("\n=== Error Response Format ===")

        # 401 error format
        status, body, _ = self.http_request("GET", "/api/v1/fleets", auth="none")
        if status == 401:
            if "detail" in body or "error" in body:
                self.add_result("401 Error Format", True, "Has detail/error field")
            else:
                self.add_result("401 Error Format", False, "Missing detail/error", {"body": body})

        # 404 error format
        status, body, _ = self.http_request("GET", "/api/v1/nonexistent", auth="bearer")
        if status == 404:
            self.add_result("404 Error Format", True, "Returns 404 for unknown route")
        elif status == 401:
            self.add_result("404 Error Format", True, "Auth checked before route (acceptable)")
        else:
            self.add_result("404 Error Format", False, f"Unexpected status {status}")

    # ==========================================================================
    # MAIN
    # ==========================================================================

    def run_all_tests(self):
        """Run all API contract tests."""
        print("=" * 60)
        print("  TensorGuardFlow System Doctor - API Contract Checks")
        print("=" * 60)
        print(f"\nTarget: {self.ctx.base_url}")
        print(f"Test ID: {self.ctx.test_suffix}\n")

        self.test_health_endpoints()
        self.test_docs_endpoint()
        self.test_auth_required_endpoints()
        self.test_onboarding_and_login()
        self.test_fleet_endpoints()
        self.test_telemetry_ingest()
        self.test_telemetry_query_endpoints()
        self.test_key_rotation()
        self.test_frontend_contract()
        self.test_error_response_format()

        # Summary
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)

        print("\n" + "=" * 60)
        print("  SUMMARY")
        print("=" * 60)
        print(f"\n  \033[32mPassed: {passed}\033[0m")
        print(f"  \033[31mFailed: {failed}\033[0m\n")

        if failed > 0:
            print("\033[31mSome checks failed. Review the output above.\033[0m\n")
            return 1
        else:
            print("\033[32mAll checks passed!\033[0m\n")
            return 0


def main():
    parser = argparse.ArgumentParser(description="TensorGuardFlow API Contract Checker")
    parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)"
    )
    args = parser.parse_args()

    checker = APIChecker(args.host)
    sys.exit(checker.run_all_tests())


if __name__ == "__main__":
    main()
