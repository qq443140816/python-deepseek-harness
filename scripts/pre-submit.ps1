# One-shot pre-submit gate (AGENTS.md section 4).
# Usage: powershell -ExecutionPolicy Bypass -File scripts/pre-submit.ps1
$ErrorActionPreference = "Stop"
$root = Join-Path $PSScriptRoot ".."
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

function Step($name, $script) {
    Write-Host ""
    Write-Host "=== $name ===" -ForegroundColor Cyan
    & $script
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] $name" -ForegroundColor Red
        exit 1
    }
    Write-Host "[PASS] $name" -ForegroundColor Green
}

Set-Location $root

Step "black format" { & $py -m black --check src/ tests/ }
Step "isort imports" { & $py -m isort --check-only src/ tests/ }
Step "flake8 pep8" { & $py -m flake8 src/ tests/ }
Step "mypy strict" { & $py -m mypy src/ }
Step "unit tests" { & $py -m pytest tests/unit/ -q }
Step "integration tests" { & $py -m pytest tests/integration/ -q }
Step "behavior eval" { & $py -m pytest tests/eval/ -q }
Step "coverage>=80 (full suite)" { & $py -m pytest tests/ --cov=src/pdsh --cov-fail-under=80 -q }
Step "bandit security" { & $py -m bandit -r src/ -q }

Write-Host ""
Write-Host "All gates passed." -ForegroundColor Green
