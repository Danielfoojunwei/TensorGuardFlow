#!/usr/bin/env python3
"""
TensorGuard Version Information CLI.

Provides the single source of truth for version information,
reading from package metadata (pyproject.toml).

Usage:
    python -m tensorguard.platform.version
    python -m tensorguard.platform.version --json
    python -m tensorguard.platform.version --check
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional


def get_version() -> str:
    """
    Get the package version from metadata.

    Uses importlib.metadata which reads from installed package
    (pyproject.toml -> package metadata).
    """
    try:
        from importlib.metadata import version
        return version("tensorguard")
    except Exception:
        # Fallback for development/edge cases
        try:
            from tensorguard import __version__
            return __version__
        except Exception:
            return "unknown"


def get_build_info() -> Dict[str, Any]:
    """
    Get comprehensive build and version information.

    Returns dict with:
    - version: Package version
    - environment: TG_ENVIRONMENT value
    - python_version: Python interpreter version
    - build_time: If set via TG_BUILD_TIME
    - git_commit: If set via TG_GIT_COMMIT
    """
    import platform

    info = {
        "version": get_version(),
        "environment": os.getenv("TG_ENVIRONMENT", "development"),
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
    }

    # Optional build metadata (set during CI/Docker build)
    build_time = os.getenv("TG_BUILD_TIME")
    if build_time:
        info["build_time"] = build_time

    git_commit = os.getenv("TG_GIT_COMMIT")
    if git_commit:
        info["git_commit"] = git_commit[:8]  # Short SHA

    git_branch = os.getenv("TG_GIT_BRANCH")
    if git_branch:
        info["git_branch"] = git_branch

    # Demo mode flag
    demo_mode = os.getenv("TG_DEMO_MODE", "false").lower() == "true"
    if demo_mode:
        info["demo_mode"] = True

    return info


def check_version_consistency() -> Dict[str, Any]:
    """
    Check version consistency across different sources.

    Returns check results with any discrepancies.
    """
    results = {
        "consistent": True,
        "sources": {},
        "discrepancies": [],
    }

    # Source 1: importlib.metadata
    try:
        from importlib.metadata import version
        pkg_version = version("tensorguard")
        results["sources"]["package_metadata"] = pkg_version
    except Exception as e:
        results["sources"]["package_metadata"] = f"error: {e}"
        results["consistent"] = False

    # Source 2: __version__ in __init__
    try:
        from tensorguard import __version__
        results["sources"]["__init__"] = __version__
    except Exception as e:
        results["sources"]["__init__"] = f"error: {e}"
        results["consistent"] = False

    # Check consistency
    versions = [v for v in results["sources"].values() if not str(v).startswith("error")]
    if len(set(versions)) > 1:
        results["consistent"] = False
        results["discrepancies"].append(f"Version mismatch: {versions}")

    return results


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="TensorGuard Version Information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tensorguard.platform.version           Print version
  python -m tensorguard.platform.version --json    Print full info as JSON
  python -m tensorguard.platform.version --check   Check version consistency
        """
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--check", action="store_true", help="Check version consistency")
    parser.add_argument("--full", action="store_true", help="Show full build info")

    args = parser.parse_args()

    if args.check:
        results = check_version_consistency()
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"Version Consistency Check")
            print(f"{'='*40}")
            for source, ver in results["sources"].items():
                print(f"  {source}: {ver}")
            print()
            if results["consistent"]:
                print("✓ All version sources are consistent")
            else:
                print("✗ Version inconsistencies detected:")
                for d in results["discrepancies"]:
                    print(f"  - {d}")
        sys.exit(0 if results["consistent"] else 1)

    if args.full or args.json:
        info = get_build_info()
        if args.json:
            print(json.dumps(info, indent=2))
        else:
            print(f"TensorGuard v{info['version']}")
            print(f"{'='*40}")
            for key, value in info.items():
                if key != "version":
                    print(f"  {key}: {value}")
    else:
        print(get_version())


if __name__ == "__main__":
    main()
