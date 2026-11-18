# Build and launch the complete local product from one PowerShell command.
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) { throw "Python 3 is required. Install it from python.org, then run this script again." }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "Node.js with npm is required to build the dashboard." }

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & $pythonCommand.Source -m venv (Join-Path $projectRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create the project's Python environment." }
}
& $venvPython -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Could not install the backend requirements." }

if (-not (Test-Path (Join-Path $projectRoot "frontend\node_modules"))) {
    Push-Location (Join-Path $projectRoot "frontend")
    try { npm install; if ($LASTEXITCODE -ne 0) { throw "Could not install dashboard requirements." } }
    finally { Pop-Location }
}
Push-Location (Join-Path $projectRoot "frontend")
try { npm run build; if ($LASTEXITCODE -ne 0) { throw "The dashboard build failed." } }
finally { Pop-Location }

# Use a dedicated local port so another project on port 8000 is left untouched.
$port = 8010
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
try { $listener.Start() }
catch { throw "Port $port is already in use. Close the other local app or change `$port in this script." }
finally { $listener.Stop() }

$logDirectory = Join-Path $projectRoot ".local"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$stdout = Join-Path $logDirectory "release-server.log"
$stderr = Join-Path $logDirectory "release-server-error.log"
$uvicornArgs = @("-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "127.0.0.1", "--port", "$port")
# Uvicorn reads backend/.env only when explicitly given this option. Keep the
# file optional so a local-only install starts normally without hosted auth.
$backendEnvironment = Join-Path $projectRoot "backend\.env"
if (Test-Path $backendEnvironment) {
    $uvicornArgs += @("--env-file", $backendEnvironment)
}
$server = Start-Process -FilePath $venvPython `
    -ArgumentList $uvicornArgs `
    -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr

$url = "http://127.0.0.1:$port/"
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Seconds 1
    try {
        $health = Invoke-RestMethod -Uri "$url`health" -TimeoutSec 2
        if ($health.status -eq "ok") { $ready = $true; break }
    } catch { }
    if ($server.HasExited) { break }
}
if (-not $ready) {
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    throw "DocuGuard did not become ready. See .local\release-server-error.log for details."
}

$chromeCandidates = @(
    (Join-Path $env:ProgramFiles "Google\Chrome\Application\chrome.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Google\Chrome\Application\chrome.exe")
) | Where-Object { $_ -and (Test-Path $_) }
if ($chromeCandidates) { Start-Process -FilePath $chromeCandidates[0] -ArgumentList $url }
else { Start-Process $url }
Write-Host "DocuGuard is ready at $url"
Write-Host "This local release analyzes repositories on this computer and does not publish source files."
