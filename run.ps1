# PM Workbench launcher (Windows). First run installs deps; every run starts the server.
Set-Location $PSScriptRoot
$py = if ($env:PYTHON) { $env:PYTHON } else { "python" }
& $py -c "import fastapi, uvicorn, openpyxl, requests, multipart" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "Installing dependencies..."; & $py -m pip install --user -q -r requirements.txt }
if ($args -contains "--demo") {  # fictional demo data, no Jira / Claude needed
  $env:PMWB_DATA = Join-Path $PSScriptRoot "demo/data"
  if (-not (Test-Path demo/data/workbench.db)) { & $py scripts/seed_demo.py }
} elseif (-not (Test-Path data/config.json)) { New-Item -ItemType Directory -Force data | Out-Null; Copy-Item config.example.json data/config.json; Write-Host "Created data/config.json - finish setup in Settings." }
$port = if ($env:PORT) { $env:PORT } else { "8765" }
Write-Host "PM Workbench -> http://127.0.0.1:$port"
& $py -m uvicorn app.main:app --host 127.0.0.1 --port $port
