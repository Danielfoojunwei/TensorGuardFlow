#!/usr/bin/env python3
"""
TensorGuard Platform Doctor

Diagnostic tool for checking platform health and configuration.

Usage:
    python -m tensorguard.platform.doctor --db
    python -m tensorguard.platform.doctor --all
    python -m tensorguard.platform.doctor --migrate
"""

import argparse
import logging
import os
import sys
from typing import Any, Dict, List

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


def check_database() -> Dict[str, Any]:
    """Check database connectivity and migration status."""
    from .database import check_db_health
    from .db_migration import check_migrations, get_current_revision

    results: Dict[str, Any] = {
        "name": "Database",
        "status": "unknown",
        "checks": [],
    }

    # Connection check
    try:
        health = check_db_health()
        if health["status"] == "healthy":
            results["checks"].append(("Connection", "OK", "Database is reachable"))
        else:
            results["checks"].append(("Connection", "FAIL", health.get("error", "Unknown error")))
            results["status"] = "unhealthy"
            return results
    except Exception as e:
        results["checks"].append(("Connection", "FAIL", str(e)))
        results["status"] = "unhealthy"
        return results

    # Migration check
    try:
        migration_status = check_migrations()
        if migration_status["is_current"]:
            results["checks"].append((
                "Migrations",
                "OK",
                f"At revision {migration_status['current_revision']}"
            ))
        else:
            results["checks"].append((
                "Migrations",
                "WARN",
                f"{migration_status['pending_count']} pending: {migration_status['pending_revisions']}"
            ))
    except Exception as e:
        results["checks"].append(("Migrations", "FAIL", str(e)))

    # Pool status
    try:
        if "pool_size" in health:
            results["checks"].append((
                "Connection Pool",
                "OK",
                f"Size: {health.get('pool_size')}, "
                f"In: {health.get('checked_in')}, Out: {health.get('checked_out')}"
            ))
    except Exception:
        pass

    # Determine overall status
    statuses = [c[1] for c in results["checks"]]
    if "FAIL" in statuses:
        results["status"] = "unhealthy"
    elif "WARN" in statuses:
        results["status"] = "degraded"
    else:
        results["status"] = "healthy"

    return results


def check_configuration() -> Dict[str, Any]:
    """Check environment configuration."""
    results: Dict[str, Any] = {
        "name": "Configuration",
        "status": "unknown",
        "checks": [],
    }

    # Required environment variables
    required_vars = [
        ("TG_SECRET_KEY", "JWT signing key", True),
        ("DATABASE_URL", "Database connection", True),
    ]

    optional_vars = [
        ("TG_VAULT_MASTER_KEY", "Vault encryption key", False),
        ("TG_OTEL_ENDPOINT", "OpenTelemetry endpoint", False),
    ]

    environment = os.getenv("TG_ENVIRONMENT", "development")
    is_production = environment == "production"

    results["checks"].append((
        "Environment",
        "OK" if is_production else "INFO",
        f"TG_ENVIRONMENT={environment}"
    ))

    for var, description, required_in_prod in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if "KEY" in var or "SECRET" in var or "PASSWORD" in var:
                display = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "****"
            else:
                display = value[:50] + "..." if len(value) > 50 else value
            results["checks"].append((var, "OK", f"Set ({display})"))
        elif required_in_prod and is_production:
            results["checks"].append((var, "FAIL", f"REQUIRED in production: {description}"))
        else:
            results["checks"].append((var, "WARN", f"Not set: {description}"))

    for var, description, _ in optional_vars:
        value = os.getenv(var)
        if value:
            results["checks"].append((var, "OK", "Set"))
        else:
            results["checks"].append((var, "INFO", f"Not set (optional): {description}"))

    # Demo mode check
    demo_mode = os.getenv("TG_DEMO_MODE", "false").lower() == "true"
    if demo_mode and is_production:
        results["checks"].append(("TG_DEMO_MODE", "FAIL", "Demo mode enabled in production!"))
    elif demo_mode:
        results["checks"].append(("TG_DEMO_MODE", "WARN", "Demo mode enabled (dev only)"))
    else:
        results["checks"].append(("TG_DEMO_MODE", "OK", "Disabled"))

    # Determine overall status
    statuses = [c[1] for c in results["checks"]]
    if "FAIL" in statuses:
        results["status"] = "unhealthy"
    elif "WARN" in statuses:
        results["status"] = "degraded"
    else:
        results["status"] = "healthy"

    return results


def check_security() -> Dict[str, Any]:
    """Check security configuration."""
    results: Dict[str, Any] = {
        "name": "Security",
        "status": "unknown",
        "checks": [],
    }

    # Check secret key length
    secret_key = os.getenv("TG_SECRET_KEY", "")
    if len(secret_key) >= 32:
        results["checks"].append(("Secret Key Length", "OK", f"{len(secret_key)} characters"))
    elif len(secret_key) > 0:
        results["checks"].append(("Secret Key Length", "WARN", f"{len(secret_key)} chars (recommend 32+)"))
    else:
        results["checks"].append(("Secret Key Length", "FAIL", "Not set"))

    # Check vault encryption
    vault_key = os.getenv("TG_VAULT_MASTER_KEY", "")
    unencrypted = os.getenv("TG_VAULT_UNENCRYPTED", "false").lower() == "true"
    if vault_key and len(vault_key) >= 32:
        results["checks"].append(("Vault Encryption", "OK", "Enabled (AES-256-GCM)"))
    elif unencrypted:
        results["checks"].append(("Vault Encryption", "WARN", "Explicitly disabled"))
    else:
        results["checks"].append(("Vault Encryption", "WARN", "Not configured (keys stored in plaintext)"))

    # Check key rotation
    current_key = os.getenv("TG_SECRET_KEY_CURRENT")
    previous_key = os.getenv("TG_SECRET_KEY_PREVIOUS")
    if current_key and previous_key:
        results["checks"].append(("Key Rotation", "OK", "Enabled (current + previous)"))
    elif current_key:
        results["checks"].append(("Key Rotation", "INFO", "Single key (no rotation)"))
    else:
        results["checks"].append(("Key Rotation", "INFO", "Using TG_SECRET_KEY"))

    # Determine overall status
    statuses = [c[1] for c in results["checks"]]
    if "FAIL" in statuses:
        results["status"] = "unhealthy"
    elif "WARN" in statuses:
        results["status"] = "degraded"
    else:
        results["status"] = "healthy"

    return results


def check_vault() -> Dict[str, Any]:
    """Check vault configuration and accessibility."""
    from pathlib import Path

    results: Dict[str, Any] = {
        "name": "Key Vault",
        "status": "unknown",
        "checks": [],
    }

    vault_path = Path(os.getenv("TG_VAULT_PATH", "keys"))

    # Check vault directory exists
    if vault_path.exists():
        results["checks"].append(("Directory", "OK", str(vault_path.absolute())))
    else:
        try:
            vault_path.mkdir(parents=True, exist_ok=True)
            results["checks"].append(("Directory", "OK", f"Created: {vault_path.absolute()}"))
        except Exception as e:
            results["checks"].append(("Directory", "FAIL", f"Cannot create: {e}"))

    # Check write permissions
    try:
        test_file = vault_path / ".doctor_test"
        test_file.write_text("test")
        test_file.unlink()
        results["checks"].append(("Write Permission", "OK", "Vault is writable"))
    except Exception as e:
        results["checks"].append(("Write Permission", "FAIL", str(e)))

    # Check encryption configuration
    master_key = os.getenv("TG_VAULT_MASTER_KEY")
    unencrypted = os.getenv("TG_VAULT_UNENCRYPTED", "false").lower() == "true"
    environment = os.getenv("TG_ENVIRONMENT", "development")

    if master_key:
        if len(master_key) >= 32:
            results["checks"].append(("Encryption", "OK", "AES-256-GCM enabled"))
        else:
            results["checks"].append(("Encryption", "WARN", f"Key too short ({len(master_key)} chars, need 32+)"))
    elif unencrypted:
        results["checks"].append(("Encryption", "WARN", "Disabled via TG_VAULT_UNENCRYPTED=true"))
    elif environment == "production":
        results["checks"].append(("Encryption", "FAIL", "Master key required in production"))
    else:
        results["checks"].append(("Encryption", "INFO", "Not configured (plaintext in dev)"))

    # Count existing keys
    try:
        key_files = list(vault_path.glob("**/*.key")) + list(vault_path.glob("**/*.bin"))
        meta_files = list(vault_path.glob("**/*.meta.json"))
        results["checks"].append(("Stored Keys", "OK", f"{len(key_files)} key files, {len(meta_files)} metadata"))
    except Exception as e:
        results["checks"].append(("Stored Keys", "WARN", str(e)))

    # Determine overall status
    statuses = [c[1] for c in results["checks"]]
    if "FAIL" in statuses:
        results["status"] = "unhealthy"
    elif "WARN" in statuses:
        results["status"] = "degraded"
    else:
        results["status"] = "healthy"

    return results


def check_dependencies() -> Dict[str, Any]:
    """Check required and optional dependencies."""
    results: Dict[str, Any] = {
        "name": "Dependencies",
        "status": "unknown",
        "checks": [],
    }

    # Required dependencies
    required_deps = [
        ("fastapi", "Web framework"),
        ("sqlmodel", "Database ORM"),
        ("cryptography", "Cryptographic operations"),
        ("alembic", "Database migrations"),
        ("jose", "JWT handling"),
    ]

    optional_deps = [
        ("flwr", "Federated Learning"),
        ("tenseal", "Homomorphic encryption"),
        ("liboqs", "Post-quantum cryptography"),
        ("josepy", "ACME/certificate management"),
    ]

    for module, description in required_deps:
        try:
            __import__(module)
            results["checks"].append((module, "OK", description))
        except ImportError:
            results["checks"].append((module, "FAIL", f"REQUIRED: {description}"))

    for module, description in optional_deps:
        try:
            __import__(module)
            results["checks"].append((module, "OK", f"Optional: {description}"))
        except ImportError:
            results["checks"].append((module, "INFO", f"Not installed: {description}"))

    # Determine overall status
    statuses = [c[1] for c in results["checks"]]
    if "FAIL" in statuses:
        results["status"] = "unhealthy"
    else:
        results["status"] = "healthy"

    return results


def print_results(results: List[Dict[str, Any]]) -> bool:
    """
    Print diagnostic results.

    Returns:
        True if all checks passed, False otherwise
    """
    all_healthy = True
    status_icons = {
        "OK": "\033[92m✓\033[0m",
        "WARN": "\033[93m!\033[0m",
        "FAIL": "\033[91m✗\033[0m",
        "INFO": "\033[94mi\033[0m",
    }

    for section in results:
        status_color = {
            "healthy": "\033[92m",
            "degraded": "\033[93m",
            "unhealthy": "\033[91m",
        }.get(section["status"], "")
        reset = "\033[0m"

        print(f"\n{section['name']} [{status_color}{section['status'].upper()}{reset}]")
        print("-" * 50)

        for check_name, status, message in section["checks"]:
            icon = status_icons.get(status, "?")
            print(f"  {icon} {check_name}: {message}")

        if section["status"] in ("unhealthy", "degraded"):
            all_healthy = False

    return all_healthy


def run_migrations_command() -> bool:
    """Run database migrations."""
    from .db_migration import run_migrations

    print("Running database migrations...")
    success, message = run_migrations()
    if success:
        print(f"\033[92m✓\033[0m {message}")
    else:
        print(f"\033[91m✗\033[0m {message}")
    return success


def main():
    parser = argparse.ArgumentParser(
        description="TensorGuard Platform Doctor - Diagnostic tool"
    )
    parser.add_argument("--db", action="store_true", help="Check database only")
    parser.add_argument("--config", action="store_true", help="Check configuration only")
    parser.add_argument("--security", action="store_true", help="Check security only")
    parser.add_argument("--vault", action="store_true", help="Check vault only")
    parser.add_argument("--deps", action="store_true", help="Check dependencies only")
    parser.add_argument("--all", action="store_true", help="Run all checks (default)")
    parser.add_argument("--migrate", action="store_true", help="Run database migrations")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    print("TensorGuard Platform Doctor")
    print("=" * 50)

    if args.migrate:
        success = run_migrations_command()
        sys.exit(0 if success else 1)

    # Determine which checks to run
    run_all = args.all or not (args.db or args.config or args.security or args.vault or args.deps)

    results = []

    if run_all or args.config:
        results.append(check_configuration())

    if run_all or args.security:
        results.append(check_security())

    if run_all or args.vault:
        results.append(check_vault())

    if run_all or args.deps:
        results.append(check_dependencies())

    if run_all or args.db:
        results.append(check_database())

    if args.json:
        import json
        print(json.dumps(results, indent=2))
    else:
        all_healthy = print_results(results)
        print()
        if all_healthy:
            print("\033[92m✓ All checks passed\033[0m")
        else:
            print("\033[93m! Some checks need attention\033[0m")
        sys.exit(0 if all_healthy else 1)


if __name__ == "__main__":
    main()
