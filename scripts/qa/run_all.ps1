# TensorGuardFlow QA Harness - Full Release Readiness Test Suite (Windows)
# Version: 2.3.0
#
# This script runs all QA checks and generates a comprehensive release readiness report.
# Usage: .\scripts\qa\run_all.ps1 [-SkipDocker] [-Quick]
#
# Exit codes:
#   0 - All checks passed, release is GO
#   1 - Critical failures, release is NO-GO

param(
    [switch]$SkipDocker,
    [switch]$Quick
)

$ErrorActionPreference = "Continue"

# ==============================================================================
# CONFIGURATION
# ==============================================================================
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Get-Item "$ScriptDir\..\..").FullName
$Version = (Select-String -Path "$ProjectRoot\pyproject.toml" -Pattern 'version = "(.+)"' | ForEach-Object { $_.Matches.Groups[1].Value } | Select-Object -First 1)
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$GitCommit = try { (git -C $ProjectRoot rev-parse --short HEAD) } catch { "unknown" }
$ArtifactsDir = "$ProjectRoot\artifacts\qa\$Version\$Timestamp"

# Results tracking
$Results = @{}
$CriticalFailures = 0
$NonCriticalFailures = 0

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "==============================================================================" -ForegroundColor Cyan
    Write-Host " $Message" -ForegroundColor Cyan
    Write-Host "==============================================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $Message" -ForegroundColor White
}

function Write-Pass {
    param([string]$TestName)
    Write-Host "[PASS] $TestName" -ForegroundColor Green
    $script:Results[$TestName] = "PASS"
}

function Write-Fail {
    param(
        [string]$TestName,
        [string]$Severity = "CRITICAL"
    )
    Write-Host "[FAIL] $TestName ($Severity)" -ForegroundColor Red
    $script:Results[$TestName] = "FAIL"
    if ($Severity -eq "CRITICAL") {
        $script:CriticalFailures++
    } else {
        $script:NonCriticalFailures++
    }
}

function Write-Skip {
    param([string]$TestName)
    Write-Host "[SKIP] $TestName" -ForegroundColor Yellow
    $script:Results[$TestName] = "SKIP"
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

# ==============================================================================
# SETUP
# ==============================================================================
Write-Header "TensorGuardFlow QA Harness v$Version"
Write-Step "Git Commit: $GitCommit"
Write-Step "Timestamp: $Timestamp"
Write-Step "Artifacts: $ArtifactsDir"
Write-Step "Quick Mode: $Quick"
Write-Step "Skip Docker: $SkipDocker"

# Create artifacts directory structure
Ensure-Directory "$ArtifactsDir\backend"
Ensure-Directory "$ArtifactsDir\frontend"
Ensure-Directory "$ArtifactsDir\security"
Ensure-Directory "$ArtifactsDir\performance"
Ensure-Directory "$ArtifactsDir\installation"
Ensure-Directory "$ArtifactsDir\logs"

Set-Location $ProjectRoot

# Write run metadata
$PythonVersion = try { (python --version 2>&1) -replace "Python ", "" } catch { "not installed" }
$NodeVersion = try { node --version } catch { "not installed" }

$Metadata = @{
    version = $Version
    git_commit = $GitCommit
    timestamp = $Timestamp
    quick_mode = $Quick.IsPresent
    skip_docker = $SkipDocker.IsPresent
    platform = "Windows"
    platform_version = [System.Environment]::OSVersion.VersionString
    python_version = $PythonVersion
    node_version = $NodeVersion
} | ConvertTo-Json

$Metadata | Out-File "$ArtifactsDir\run_metadata.json" -Encoding UTF8

# ==============================================================================
# PHASE 1: BUILD VERIFICATION
# ==============================================================================
Write-Header "PHASE 1: Build Verification"

# 1.1 Python package installation check
Write-Step "Checking Python package installation..."
try {
    $pipResult = pip install -e ".[dev]" 2>&1
    $pipResult | Out-File "$ArtifactsDir\logs\pip_install.log" -Encoding UTF8
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "Python Package Installation"
    } else {
        Write-Fail "Python Package Installation"
    }
} catch {
    Write-Fail "Python Package Installation"
}

# 1.2 Core imports check
Write-Step "Verifying core imports..."
$env:PYTHONPATH = "src"
$importCheck = python -c @"
from tensorguard.platform.main import app
from tensorguard.platform.database import engine
from tensorguard.platform.worker import WorkerDaemon
print('Core imports successful')
"@ 2>&1
$importCheck | Out-File "$ArtifactsDir\logs\import_check.log" -Encoding UTF8
if ($LASTEXITCODE -eq 0) {
    Write-Pass "Core Python Imports"
} else {
    Write-Fail "Core Python Imports"
}

# 1.3 Frontend build check
Write-Step "Checking frontend build..."
if (Test-Path "$ProjectRoot\frontend") {
    Push-Location "$ProjectRoot\frontend"
    try {
        npm install 2>&1 | Out-File "$ArtifactsDir\logs\npm_install.log" -Encoding UTF8
        npm run build 2>&1 | Out-File "$ArtifactsDir\logs\npm_build.log" -Encoding UTF8
        if ($LASTEXITCODE -eq 0) {
            Write-Pass "Frontend Build"
        } else {
            Write-Fail "Frontend Build" "CRITICAL"
        }
    } catch {
        Write-Fail "Frontend Build" "CRITICAL"
    }
    Pop-Location
} else {
    Write-Skip "Frontend Build (no frontend directory)"
}

# ==============================================================================
# PHASE 2: BACKEND TESTS
# ==============================================================================
Write-Header "PHASE 2: Backend Tests"

$env:PYTHONPATH = "src"

# 2.1 Unit tests
Write-Step "Running backend unit tests..."
$unitTestResult = python -m pytest tests/unit/ -v --tb=short --junitxml="$ArtifactsDir\backend\junit_unit.xml" --cov=src/tensorguard --cov-report=xml:"$ArtifactsDir\backend\coverage_unit.xml" 2>&1
$unitTestResult | Out-File "$ArtifactsDir\logs\pytest_unit.log" -Encoding UTF8
if ($LASTEXITCODE -eq 0) {
    Write-Pass "Backend Unit Tests"
} else {
    Write-Fail "Backend Unit Tests"
}

# 2.2 Integration tests
Write-Step "Running backend integration tests..."
$integrationResult = python -m pytest tests/integration/ -v --tb=short --junitxml="$ArtifactsDir\backend\junit_integration.xml" 2>&1
$integrationResult | Out-File "$ArtifactsDir\logs\pytest_integration.log" -Encoding UTF8
if ($LASTEXITCODE -eq 0) {
    Write-Pass "Backend Integration Tests"
} else {
    Write-Fail "Backend Integration Tests"
}

# 2.3 Security tests
Write-Step "Running security tests..."
$securityResult = python -m pytest tests/security/ -v --tb=short --junitxml="$ArtifactsDir\backend\junit_security.xml" 2>&1
$securityResult | Out-File "$ArtifactsDir\logs\pytest_security.log" -Encoding UTF8
if ($LASTEXITCODE -eq 0) {
    Write-Pass "Backend Security Tests"
} else {
    Write-Fail "Backend Security Tests"
}

# 2.4 E2E smoke tests (backend)
if (-not $Quick) {
    Write-Step "Running E2E tests..."
    $e2eResult = python -m pytest tests/e2e/ -v --tb=short --junitxml="$ArtifactsDir\backend\junit_e2e.xml" 2>&1
    $e2eResult | Out-File "$ArtifactsDir\logs\pytest_e2e.log" -Encoding UTF8
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "Backend E2E Tests"
    } else {
        Write-Fail "Backend E2E Tests"
    }

    # Stability run
    Write-Step "Running E2E stability check (2nd run)..."
    $e2eStabilityResult = python -m pytest tests/e2e/ -v --tb=short --junitxml="$ArtifactsDir\backend\junit_e2e_stability.xml" 2>&1
    $e2eStabilityResult | Out-File "$ArtifactsDir\logs\pytest_e2e_stability.log" -Encoding UTF8
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "Backend E2E Stability Run"
    } else {
        Write-Fail "Backend E2E Stability Run (Flaky)"
    }
} else {
    Write-Skip "Backend E2E Tests (quick mode)"
}

# ==============================================================================
# PHASE 3: FRONTEND TESTS
# ==============================================================================
Write-Header "PHASE 3: Frontend Tests"

Push-Location "$ProjectRoot\frontend"

# 3.1 TypeScript check
Write-Step "Running TypeScript check..."
try {
    $tscResult = npx vue-tsc --noEmit 2>&1
    $tscResult | Out-File "$ArtifactsDir\frontend\typescript_check.log" -Encoding UTF8
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "Frontend TypeScript"
    } else {
        Write-Fail "Frontend TypeScript" "NON-CRITICAL"
    }
} catch {
    Write-Skip "Frontend TypeScript (vue-tsc not available)"
}

# 3.2 Vitest tests (if configured)
Write-Step "Running Vitest tests..."
if ((Test-Path "vitest.config.ts") -or (Test-Path "vitest.config.js")) {
    try {
        $vitestResult = npm run test 2>&1
        $vitestResult | Out-File "$ArtifactsDir\frontend\vitest.log" -Encoding UTF8
        if ($LASTEXITCODE -eq 0) {
            Write-Pass "Frontend Vitest Tests"
        } else {
            Write-Fail "Frontend Vitest Tests" "CRITICAL"
        }
    } catch {
        Write-Fail "Frontend Vitest Tests" "CRITICAL"
    }
} else {
    Write-Skip "Frontend Vitest Tests (not configured)"
}

Pop-Location

# ==============================================================================
# PHASE 4: CODE QUALITY GATES
# ==============================================================================
Write-Header "PHASE 4: Code Quality Gates"

# 4.1 Ruff lint
Write-Step "Running Ruff linter..."
try {
    $ruffResult = ruff check src/ --output-format json 2>&1
    $ruffResult | Out-File "$ArtifactsDir\backend\ruff_report.json" -Encoding UTF8
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "Python Lint (Ruff)"
    } else {
        Write-Fail "Python Lint (Ruff)" "NON-CRITICAL"
    }
} catch {
    Write-Skip "Python Lint (Ruff not available)"
}

# 4.2 Mypy typecheck
Write-Step "Running Mypy type checker..."
try {
    $mypyResult = mypy src/ --ignore-missing-imports 2>&1
    $mypyResult | Out-File "$ArtifactsDir\backend\mypy_report.log" -Encoding UTF8
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "Python Typecheck (Mypy)"
    } else {
        Write-Fail "Python Typecheck (Mypy)" "NON-CRITICAL"
    }
} catch {
    Write-Skip "Python Typecheck (Mypy not available)"
}

# ==============================================================================
# PHASE 5: SECURITY SCANS
# ==============================================================================
Write-Header "PHASE 5: Security Scans"

# 5.1 pip-audit
Write-Step "Running pip-audit..."
try {
    pip install pip-audit -q 2>&1 | Out-Null
    $pipAuditResult = pip-audit --format json 2>&1
    $pipAuditResult | Out-File "$ArtifactsDir\security\pip_audit.json" -Encoding UTF8
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "Python Dependency Audit"
    } else {
        Write-Fail "Python Dependency Audit" "NON-CRITICAL"
    }
} catch {
    Write-Skip "Python Dependency Audit (pip-audit not available)"
}

# 5.2 npm audit
Write-Step "Running npm audit..."
Push-Location "$ProjectRoot\frontend"
try {
    $npmAuditResult = npm audit --json 2>&1
    $npmAuditResult | Out-File "$ArtifactsDir\security\npm_audit.json" -Encoding UTF8
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "Frontend Dependency Audit"
    } else {
        Write-Fail "Frontend Dependency Audit" "NON-CRITICAL"
    }
} catch {
    Write-Skip "Frontend Dependency Audit"
}
Pop-Location

# ==============================================================================
# PHASE 6 & 7: PERFORMANCE & INSTALLATION (Skipped on Windows by default)
# ==============================================================================
Write-Header "PHASE 6 & 7: Performance & Installation Tests"

if (-not $Quick -and -not $SkipDocker) {
    Write-Step "Running performance smoke tests..."
    if (Test-Path "$ScriptDir\perf_smoke.py") {
        $env:PYTHONPATH = "src"
        $perfResult = python "$ScriptDir\perf_smoke.py" --output "$ArtifactsDir\performance\perf_smoke_results.json" 2>&1
        $perfResult | Out-File "$ArtifactsDir\logs\perf_smoke.log" -Encoding UTF8
        if ($LASTEXITCODE -eq 0) {
            Write-Pass "Performance Smoke Tests"
        } else {
            Write-Fail "Performance Smoke Tests" "NON-CRITICAL"
        }
    } else {
        Write-Skip "Performance Smoke Tests (script not found)"
    }
} else {
    Write-Skip "Performance Smoke Tests (quick mode or docker skipped)"
}

# ==============================================================================
# GENERATE SUMMARY
# ==============================================================================
Write-Header "QA HARNESS COMPLETE"

# Generate summary JSON
$Summary = @{
    version = $Version
    git_commit = $GitCommit
    timestamp = $Timestamp
    critical_failures = $CriticalFailures
    non_critical_failures = $NonCriticalFailures
    go_decision = ($CriticalFailures -eq 0)
    results = $Results
} | ConvertTo-Json -Depth 3

$Summary | Out-File "$ArtifactsDir\summary.json" -Encoding UTF8

# Print results
Write-Host ""
Write-Host "Results Summary:" -ForegroundColor Cyan
Write-Host "================"
foreach ($key in $Results.Keys) {
    $color = switch ($Results[$key]) {
        "PASS" { "Green" }
        "FAIL" { "Red" }
        "SKIP" { "Yellow" }
        default { "White" }
    }
    Write-Host ("  {0,-40} {1}" -f $key, $Results[$key]) -ForegroundColor $color
}
Write-Host ""
Write-Host "Critical Failures: $CriticalFailures" -ForegroundColor $(if ($CriticalFailures -gt 0) { "Red" } else { "Green" })
Write-Host "Non-Critical Failures: $NonCriticalFailures" -ForegroundColor $(if ($NonCriticalFailures -gt 0) { "Yellow" } else { "Green" })
Write-Host ""
Write-Host "Artifacts saved to: $ArtifactsDir"
Write-Host ""

# Exit with appropriate code
if ($CriticalFailures -gt 0) {
    Write-Host "==============================================================================" -ForegroundColor Red
    Write-Host " RELEASE DECISION: NO-GO ($CriticalFailures critical failures)" -ForegroundColor Red
    Write-Host "==============================================================================" -ForegroundColor Red
    exit 1
} else {
    Write-Host "==============================================================================" -ForegroundColor Green
    Write-Host " RELEASE DECISION: GO (All critical checks passed)" -ForegroundColor Green
    Write-Host "==============================================================================" -ForegroundColor Green
    exit 0
}
