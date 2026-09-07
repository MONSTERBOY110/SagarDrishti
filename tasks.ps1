# SagarDrishti task runner (Windows / PowerShell).
# Docker is not the Phase 1 runtime (ADR-0004), so this file is the
# one-command entry point for the whole stack.
#
#   ./tasks.ps1 setup     install Python + Node dependencies
#   ./tasks.ps1 fetch     download real sample data (the only network step)
#   ./tasks.ps1 api       run the FastAPI data plane on :8000
#   ./tasks.ps1 web       run the Next.js client on :3000
#   ./tasks.ps1 test      run the data-plane test suite
#   ./tasks.ps1 offline   run the API with the network path disabled
#   ./tasks.ps1 build     production build of the web client
#   ./tasks.ps1 serve     serve the production build on :3000 (frees the port)
#
# New here? Read docs/START-HERE.md first.

param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'fetch', 'api', 'web', 'test', 'offline', 'build', 'serve')]
    [string]$Task = 'test'
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$py = Join-Path $root '.venv\Scripts\python.exe'

function Assert-Venv {
    if (-not (Test-Path $py)) {
        throw "No venv at $py. Run: ./tasks.ps1 setup"
    }
}

switch ($Task) {
    'setup' {
        if (-not (Test-Path $py)) { py -3.11 -m venv (Join-Path $root '.venv') }
        & $py -m pip install --upgrade pip
        & $py -m pip install -r (Join-Path $root 'services\api\requirements-dev.txt')
        pnpm install
        Write-Output 'setup complete'
    }
    'fetch' {
        Assert-Venv
        & $py (Join-Path $root 'tools\fetch_sample.py')
        & $py (Join-Path $root 'tools\preprocess.py')
    }
    'api' {
        Assert-Venv
        Push-Location (Join-Path $root 'services\api')
        try { & $py -m uvicorn app.main:app --reload --port 8000 } finally { Pop-Location }
    }
    'offline' {
        Assert-Venv
        $env:OFFLINE = '1'
        Push-Location (Join-Path $root 'services\api')
        try { & $py -m uvicorn app.main:app --port 8000 } finally { Pop-Location }
    }
    'web' { pnpm web:dev }
    'build' { pnpm web:build }
    'serve' {
        # next start refuses to bind if a previous server is still holding the
        # port, and killing the shell does not always kill the node child.
        Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue |
            ForEach-Object {
                Write-Output "freeing port 3000 (pid $($_.OwningProcess))"
                Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
            }
        Start-Sleep -Seconds 1
        pnpm --filter @sagardrishti/web exec next start -p 3000
    }
    'test' {
        Assert-Venv
        Push-Location (Join-Path $root 'services\api')
        try { & $py -m pytest -q } finally { Pop-Location }
    }
}
