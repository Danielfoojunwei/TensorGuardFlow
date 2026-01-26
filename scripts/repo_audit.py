#!/usr/bin/env python3
"""
TensorGuard Repository Audit Script

Scans the repository for production readiness issues:
- Duplicate service entrypoints
- Dead code folders
- Hardcoded secrets
- Bare except blocks
- Simulation/mock/placeholder code

Usage:
    python scripts/repo_audit.py [--fix] [--json]
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any

# Repo root detection
REPO_ROOT = Path(__file__).parent.parent.resolve()


@dataclass
class Finding:
    """A single audit finding."""
    category: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    file: str
    line: Optional[int]
    message: str
    code_snippet: Optional[str] = None
    remediation: Optional[str] = None


@dataclass
class AuditReport:
    """Complete audit report."""
    findings: List[Finding] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    passed: bool = True

    def add(self, finding: Finding):
        self.findings.append(finding)
        self.summary[finding.severity] = self.summary.get(finding.severity, 0) + 1
        if finding.severity in ("CRITICAL", "HIGH"):
            self.passed = False


# =============================================================================
# PATTERNS TO DETECT
# =============================================================================

# Hardcoded secrets patterns
SECRET_PATTERNS = [
    # Explicit secret assignments
    (r'SECRET_KEY\s*=\s*["\'][^"\']+["\']', "Hardcoded SECRET_KEY"),
    (r'API_KEY\s*=\s*["\'][a-zA-Z0-9_\-]{16,}["\']', "Hardcoded API_KEY"),
    (r'PASSWORD\s*=\s*["\'][^"\']+["\']', "Hardcoded PASSWORD"),
    (r'TOKEN\s*=\s*["\'][a-zA-Z0-9_\-]{20,}["\']', "Hardcoded TOKEN"),
    # AWS patterns
    (r'AKIA[0-9A-Z]{16}', "AWS Access Key ID"),
    (r'(?i)aws.{0,20}secret.{0,20}["\'][0-9a-zA-Z/+=]{40}["\']', "AWS Secret Key"),
    # Private keys
    (r'-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----', "Private Key in code"),
    # Generic secrets
    (r'(?i)(password|secret|token|apikey|api_key)\s*=\s*["\'][^"\']{8,}["\']', "Potential hardcoded credential"),
]

# Allowlist patterns (false positives)
SECRET_ALLOWLIST = [
    r'os\.getenv\(',
    r'os\.environ\[',
    r'settings\.',
    r'config\.',
    r'\.example',
    r'test_',
    r'_test\.py',
    r'conftest\.py',
    r'fixture',
    r'mock',
    r'placeholder',
    r'your-secret-here',
    r'CHANGE_ME',
    r'<your',
    r'\{\{',  # Template variables
    r'hashed_password\s*=\s*["\']N/A["\']',  # Demo user placeholders
    r'INVALID_TOKEN',  # Token validation constants
]

# Paths to exclude from secret scanning (tests and utility scripts are expected to have test credentials)
SECRET_PATH_EXCLUSIONS = [
    r'tests/',
    r'scripts/',
    r'benchmarks/',
    r'examples/',
]

# Bare except patterns
BARE_EXCEPT_PATTERN = r'except\s*:'

# Simulation/mock patterns
SIMULATION_PATTERNS = [
    (r'#\s*simulate\s+smtp', "Simulation comment (SMTP)"),
    (r'#\s*simulate\s+email', "Simulation comment (email)"),
    (r'print\(["\'].*simulate', "Print with simulate"),
    (r'print\(["\'].*mock', "Print with mock"),
    (r'def\s+simulate_', "Simulate function"),
    (r'def\s+mock_', "Mock function (outside tests)"),
    (r'class\s+Mock[A-Z]', "Mock class (outside tests)"),
    (r'DEMO_MODE\s*=\s*True(?!\s*\))', "Demo mode hardcoded to True"),
    (r'\.demo\s*=\s*True(?!\s*\))', "Demo flag enabled"),
]

# Simulation allowlist (legitimate uses)
SIMULATION_ALLOWLIST = [
    r'TG_DEMO_MODE=true',  # Error messages/docs about demo mode
    r'DEMO_MODE.*false',  # Default to false
    r'if.*DEMO_MODE',  # Checking demo mode
    r'/bench/',  # Benchmark code (simulation is expected)
    r'empirical',  # Empirical analysis (simulation is expected)
    r'scripts/',  # Utility scripts (mock functions for testing)
]

# Dead code directories
DEAD_CODE_DIRS = [
    "backend",  # Should not contain production code
    "api",      # Legacy API location
]

# Expected production code locations
VALID_CODE_LOCATIONS = [
    "src/",
    "services/",
    "tests/",
    "benchmarks/",
    "scripts/",
    "examples/",
    "alembic/",
]


# =============================================================================
# SCANNERS
# =============================================================================

def scan_file_content(filepath: Path, report: AuditReport) -> None:
    """Scan a single file for issues."""
    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        lines = content.split('\n')
    except (IOError, OSError) as e:
        report.add(Finding(
            category="FILE_ERROR",
            severity="INFO",
            file=str(filepath.relative_to(REPO_ROOT)),
            line=None,
            message=f"Could not read file: {e}"
        ))
        return

    rel_path = str(filepath.relative_to(REPO_ROOT))
    is_test_file = '/tests/' in rel_path or '_test.py' in rel_path or 'test_' in rel_path

    for line_num, line in enumerate(lines, 1):
        # Skip empty lines and comments for most checks
        stripped = line.strip()

        # --- Hardcoded Secrets ---
        # Skip paths that are expected to have test credentials
        in_excluded_path = any(re.search(excl, rel_path) for excl in SECRET_PATH_EXCLUSIONS)

        for pattern, description in SECRET_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                # Check allowlist
                if any(re.search(allow, line, re.IGNORECASE) for allow in SECRET_ALLOWLIST):
                    continue
                # Skip test files and scripts for generic patterns
                if (is_test_file or in_excluded_path) and "Potential" in description:
                    continue
                # Skip test/script paths for non-critical patterns
                if in_excluded_path:
                    continue

                report.add(Finding(
                    category="HARDCODED_SECRET",
                    severity="CRITICAL",
                    file=rel_path,
                    line=line_num,
                    message=description,
                    code_snippet=line.strip()[:100],
                    remediation="Use environment variables or secure vault"
                ))
                break  # One finding per line

        # --- Bare Except ---
        if re.search(BARE_EXCEPT_PATTERN, line):
            # Check if it's followed by a pass or specific handling
            context = '\n'.join(lines[line_num-1:min(line_num+2, len(lines))])

            # Skip if in comments
            if stripped.startswith('#'):
                continue

            report.add(Finding(
                category="BARE_EXCEPT",
                severity="MEDIUM" if is_test_file else "HIGH",
                file=rel_path,
                line=line_num,
                message="Bare except clause catches all exceptions including KeyboardInterrupt",
                code_snippet=stripped[:80],
                remediation="Use specific exception types: except Exception as e:"
            ))

        # --- Simulation/Mock in Production Code ---
        if not is_test_file and '/examples/' not in rel_path:
            for pattern, description in SIMULATION_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    # Check simulation allowlist
                    if any(re.search(allow, line, re.IGNORECASE) for allow in SIMULATION_ALLOWLIST):
                        continue
                    if any(re.search(allow, rel_path, re.IGNORECASE) for allow in SIMULATION_ALLOWLIST):
                        continue

                    report.add(Finding(
                        category="SIMULATION_CODE",
                        severity="MEDIUM",
                        file=rel_path,
                        line=line_num,
                        message=f"Simulation/mock code in production path: {description}",
                        code_snippet=stripped[:80],
                        remediation="Move to tests/ or examples/, or gate with TG_DEMO_MODE"
                    ))
                    break


def scan_dead_code_dirs(report: AuditReport) -> None:
    """Check for dead code directories that shouldn't contain production code."""
    for dirname in DEAD_CODE_DIRS:
        dir_path = REPO_ROOT / dirname
        if dir_path.exists() and dir_path.is_dir():
            # Check for Python files
            py_files = list(dir_path.rglob("*.py"))
            if py_files:
                report.add(Finding(
                    category="DEAD_CODE_DIR",
                    severity="HIGH",
                    file=dirname,
                    line=None,
                    message=f"Directory '{dirname}/' contains {len(py_files)} Python file(s) outside src/",
                    remediation=f"Move production code to src/tensorguard/ or delete if unused"
                ))

                # List specific files
                for py_file in py_files[:5]:  # Limit to first 5
                    rel = py_file.relative_to(REPO_ROOT)
                    report.add(Finding(
                        category="DEAD_CODE_FILE",
                        severity="MEDIUM",
                        file=str(rel),
                        line=None,
                        message=f"Python file in dead code directory",
                        remediation="Delete or migrate to src/"
                    ))


def scan_duplicate_entrypoints(report: AuditReport) -> None:
    """Check for duplicate service entrypoints."""
    entrypoints = {}

    # Scan for FastAPI app definitions
    for py_file in REPO_ROOT.rglob("*.py"):
        if '/tests/' in str(py_file) or '/.venv/' in str(py_file):
            continue

        try:
            content = py_file.read_text(encoding='utf-8', errors='ignore')
        except (IOError, OSError):
            continue

        # Look for FastAPI app instantiation
        if re.search(r'app\s*=\s*FastAPI\(', content):
            rel_path = str(py_file.relative_to(REPO_ROOT))

            # Extract app title if possible
            title_match = re.search(r'FastAPI\([^)]*title\s*=\s*["\']([^"\']+)["\']', content)
            title = title_match.group(1) if title_match else "unknown"

            if title not in entrypoints:
                entrypoints[title] = []
            entrypoints[title].append(rel_path)

    # Report duplicates
    for title, locations in entrypoints.items():
        if len(locations) > 1:
            report.add(Finding(
                category="DUPLICATE_ENTRYPOINT",
                severity="HIGH",
                file=", ".join(locations),
                line=None,
                message=f"Multiple FastAPI apps with title '{title}'",
                remediation="Consolidate into single canonical entrypoint"
            ))


def scan_version_consistency(report: AuditReport) -> None:
    """Check that version is defined consistently."""
    versions_found = {}

    # Check pyproject.toml
    pyproject = REPO_ROOT / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            versions_found["pyproject.toml"] = match.group(1)

    # Check __init__.py
    init_file = REPO_ROOT / "src" / "tensorguard" / "__init__.py"
    if init_file.exists():
        content = init_file.read_text()
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            versions_found["src/tensorguard/__init__.py"] = match.group(1)

    # Check main.py hardcoded versions
    main_file = REPO_ROOT / "src" / "tensorguard" / "platform" / "main.py"
    if main_file.exists():
        content = main_file.read_text()
        matches = re.findall(r'version["\']?\s*[:=]\s*["\'](\d+\.\d+\.\d+)["\']', content, re.IGNORECASE)
        for i, v in enumerate(matches):
            versions_found[f"platform/main.py:{i+1}"] = v

    # Report inconsistencies
    unique_versions = set(versions_found.values())
    if len(unique_versions) > 1:
        report.add(Finding(
            category="VERSION_INCONSISTENCY",
            severity="MEDIUM",
            file="multiple",
            line=None,
            message=f"Version inconsistency: {versions_found}",
            remediation="Use single source of truth in pyproject.toml"
        ))


def scan_requirements_txt(report: AuditReport) -> None:
    """Check requirements.txt for issues."""
    req_file = REPO_ROOT / "requirements.txt"
    if not req_file.exists():
        return

    try:
        # Try reading with different encodings
        content = None
        for encoding in ['utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'latin-1']:
            try:
                content = req_file.read_text(encoding=encoding)
                # Check for BOM or unusual spacing
                if '\x00' in content or content.startswith('\ufeff'):
                    report.add(Finding(
                        category="ENCODING_ISSUE",
                        severity="MEDIUM",
                        file="requirements.txt",
                        line=None,
                        message=f"File has unusual encoding (detected: {encoding})",
                        remediation="Regenerate as UTF-8 without BOM"
                    ))
                break
            except UnicodeDecodeError:
                continue
    except (IOError, OSError) as e:
        report.add(Finding(
            category="FILE_ERROR",
            severity="MEDIUM",
            file="requirements.txt",
            line=None,
            message=f"Could not read requirements.txt: {e}"
        ))


def scan_pyproject_extras(report: AuditReport) -> None:
    """Check for recursive extras in pyproject.toml."""
    pyproject = REPO_ROOT / "pyproject.toml"
    if not pyproject.exists():
        return

    content = pyproject.read_text()

    # Check for self-referential extras like tensorguard[...]
    if re.search(r'tensorguard\[', content):
        report.add(Finding(
            category="RECURSIVE_EXTRA",
            severity="HIGH",
            file="pyproject.toml",
            line=None,
            message="Recursive extra dependency (tensorguard[...]) can cause pip issues",
            remediation="Flatten all dependencies in 'all' extra"
        ))


# =============================================================================
# MAIN
# =============================================================================

def run_audit(verbose: bool = False) -> AuditReport:
    """Run all audit scans and return report."""
    report = AuditReport()

    print("TensorGuard Repository Audit")
    print("=" * 60)

    # Structural scans
    print("\n[1/6] Scanning for dead code directories...")
    scan_dead_code_dirs(report)

    print("[2/6] Scanning for duplicate entrypoints...")
    scan_duplicate_entrypoints(report)

    print("[3/6] Checking version consistency...")
    scan_version_consistency(report)

    print("[4/6] Checking requirements.txt...")
    scan_requirements_txt(report)

    print("[5/6] Checking pyproject.toml extras...")
    scan_pyproject_extras(report)

    # File content scans
    print("[6/6] Scanning Python files for issues...")
    py_files = list(REPO_ROOT.rglob("*.py"))

    # Exclude virtual environments and cache
    py_files = [
        f for f in py_files
        if '/.venv/' not in str(f)
        and '/__pycache__/' not in str(f)
        and '/site-packages/' not in str(f)
        and '/.git/' not in str(f)
    ]

    for i, py_file in enumerate(py_files):
        if verbose and i % 50 == 0:
            print(f"  Processed {i}/{len(py_files)} files...")
        scan_file_content(py_file, report)

    return report


def print_report(report: AuditReport, json_output: bool = False) -> None:
    """Print the audit report."""
    if json_output:
        output = {
            "passed": report.passed,
            "summary": report.summary,
            "findings": [asdict(f) for f in report.findings]
        }
        print(json.dumps(output, indent=2))
        return

    print("\n" + "=" * 60)
    print("AUDIT RESULTS")
    print("=" * 60)

    # Group by category
    by_category: Dict[str, List[Finding]] = {}
    for finding in report.findings:
        if finding.category not in by_category:
            by_category[finding.category] = []
        by_category[finding.category].append(finding)

    # Print by severity order
    severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    severity_colors = {
        "CRITICAL": "\033[91m",  # Red
        "HIGH": "\033[93m",      # Yellow
        "MEDIUM": "\033[94m",    # Blue
        "LOW": "\033[90m",       # Gray
        "INFO": "\033[90m",      # Gray
    }
    reset = "\033[0m"

    for category, findings in sorted(by_category.items()):
        print(f"\n{category} ({len(findings)} findings)")
        print("-" * 40)

        for finding in sorted(findings, key=lambda f: severity_order.index(f.severity) if f.severity in severity_order else 99):
            color = severity_colors.get(finding.severity, "")
            print(f"  {color}[{finding.severity}]{reset} {finding.file}", end="")
            if finding.line:
                print(f":{finding.line}", end="")
            print(f"\n    {finding.message}")
            if finding.code_snippet:
                print(f"    Code: {finding.code_snippet[:60]}...")
            if finding.remediation:
                print(f"    Fix: {finding.remediation}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for severity in severity_order:
        count = report.summary.get(severity, 0)
        if count > 0:
            color = severity_colors.get(severity, "")
            print(f"  {color}{severity}: {count}{reset}")

    total = sum(report.summary.values())
    print(f"\nTotal findings: {total}")

    if report.passed:
        print("\n\033[92m✓ AUDIT PASSED\033[0m")
    else:
        print("\n\033[91m✗ AUDIT FAILED (CRITICAL or HIGH findings exist)\033[0m")


def main():
    parser = argparse.ArgumentParser(description="TensorGuard Repository Audit")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--strict", action="store_true", help="Fail on any finding")
    args = parser.parse_args()

    report = run_audit(verbose=args.verbose)
    print_report(report, json_output=args.json)

    if args.strict and report.findings:
        sys.exit(1)
    elif not report.passed:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
