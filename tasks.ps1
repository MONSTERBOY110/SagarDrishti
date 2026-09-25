# SagarDrishti task runner (Windows / PowerShell).
# Docker is not the Phase 1 runtime (ADR-0004), so this file is the
# one-command entry point for the whole stack.
#
#   ./tasks.ps1 setup     install Python + Node dependencies
#   ./tasks.ps1 fetch     download real sample data (the only network step)
#   ./tasks.ps1 api       run the FastAPI data plane on :8000
#   ./tasks.ps1 agent     run the Samudra Sahayak agent plane on :8010
#   ./tasks.ps1 web       run the Next.js client on :3000
#   ./tasks.ps1 test      run the data-plane test suite
#   ./tasks.ps1 offline   run the API with the network path disabled
#   ./tasks.ps1 build     production build of the web client
#   ./tasks.ps1 serve     serve the production build on :3000 (frees the port)
#   ./tasks.ps1 demo      build AND serve, which is the one to use
#   ./tasks.ps1 docker    build the three containers, run the full browser suite
#                         against them, then prove the data plane needs no network
#
# Use `demo` rather than build-then-serve by hand. `next start` reads the build
# manifest once at boot, so a server left running across a rebuild serves stale
# HTML that points at chunk names no longer on disk. The page then 400s on its
# own assets and renders as an empty shell, which looks exactly like a data
# outage and is not one. This cost real debugging time more than once.
#
# New here? Read docs/START-HERE.md first.

param(
    [Parameter(Position = 0)]
    [ValidateSet('setup', 'fetch', 'api', 'agent', 'web', 'test', 'offline', 'build', 'serve', 'demo', 'e2e', 'docker')]
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

function Free-Port([int]$Port) {
    # The same stale-server trap the header describes, in its second home.
    # A uvicorn started WITHOUT --reload imports app.main once at boot, so a
    # server left running while modules are added keeps serving the older app:
    # a new route answers 404 and reads exactly like a broken endpoint. It is
    # not. Freeing the port before every start makes the running server and the
    # code on disk the same thing by construction.
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            Write-Output "freeing port $Port (pid $($_.OwningProcess))"
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
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
        Free-Port 8000
        Push-Location (Join-Path $root 'services\api')
        try { & $py -m uvicorn app.main:app --reload --port 8000 } finally { Pop-Location }
    }
    'agent' {
        # Samudra Sahayak (TRD M4). A SEPARATE process on purpose: TRD section
        # 6.5 states the property as "kill the agent and every P0 still
        # passes", and the web client probes this port and simply omits the ask
        # panel when nothing answers. Stopping this task is the demonstration.
        Assert-Venv
        Free-Port 8010
        Push-Location (Join-Path $root 'services\agent')
        try { & $py -m uvicorn app.main:app --reload --port 8010 } finally { Pop-Location }
    }
    'offline' {
        Assert-Venv
        Free-Port 8000
        $env:OFFLINE = '1'
        Push-Location (Join-Path $root 'services\api')
        try { & $py -m uvicorn app.main:app --port 8000 } finally { Pop-Location }
    }
    'web' { pnpm web:dev }
    'build' { pnpm web:build }
    'demo' {
        pnpm web:build
        if (-not $?) { throw 'build failed' }
        & $PSCommandPath serve
    }
    'e2e' {
        Assert-Venv
        pnpm web:build
        pnpm exec playwright test
    }
    'docker' {
        # F5, "deployable on INCOIS infrastructure", checked rather than asserted.
        # The native servers hold the same ports, so they go first.
        foreach ($port in 3000, 8000, 8010) { Free-Port $port }
        docker compose up -d --build
        if ($LASTEXITCODE -ne 0) { throw 'docker compose up failed' }
        # Wait on the healthchecks the Dockerfiles declare, not on a sleep.
        $deadline = (Get-Date).AddMinutes(5)
        do {
            Start-Sleep -Seconds 5
            $states = docker compose ps --format '{{.Service}}={{.Health}}'
            $healthy = ($states | Where-Object { $_ -match '=healthy$' }).Count
        } until ($healthy -ge 3 -or (Get-Date) -gt $deadline)
        if ($healthy -lt 3) { docker compose ps; throw 'containers did not become healthy' }

        # The same twelve tests the native build passes, against the containers.
        $env:SAGAR_E2E_EXTERNAL = '1'
        $env:CI = '1'
        pnpm exec playwright test
        if ($LASTEXITCODE -ne 0) { throw 'the browser suite failed against the containers' }

        # And the data plane with NO network at all: it must still answer, and
        # a request to the internet must fail.
        $o = @('-f', 'docker-compose.yml', '-f', 'docker-compose.offline.yml', '--profile', 'airgap')
        docker compose @o up -d api-airgap
        Start-Sleep -Seconds 25
        docker compose @o exec api-airgap python -c "import urllib.request,json; h=json.load(urllib.request.urlopen('http://127.0.0.1:8000/healthz')); assert h['status']=='ok'; s=json.load(urllib.request.urlopen('http://127.0.0.1:8000/scorecard/incois_vam_argo/TEMP?observed=temp')); print('air-gapped scorecard: rmse', s['overall']['rmse'], 'over', s['overall']['n'], 'pairs')
try:
    urllib.request.urlopen('https://example.com', timeout=5); raise SystemExit('the air-gapped container reached the internet')
except OSError: print('egress blocked, as it must be')"
        $ok = $LASTEXITCODE
        docker compose @o rm -sf api-airgap | Out-Null
        if ($ok -ne 0) { throw 'the air-gap check failed' }
        Write-Output 'docker: 12 browser tests passed against the containers; data plane answers with no network'
    }
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
