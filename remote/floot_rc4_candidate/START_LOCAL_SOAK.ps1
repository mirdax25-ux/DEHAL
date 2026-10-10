# Run in PowerShell from the existing local checkout of Brutala-Hal-.
# Does not modify the canonical main branch or the Floot project.
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python not found. Install Python 3 and retry.' }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'npm not found. Install Node.js and retry.' }
npm install
if ($LASTEXITCODE -ne 0) { throw 'npm install failed; soak NOT started.' }
npm run test:core
if ($LASTEXITCODE -ne 0) { throw 'Baseline failed; soak NOT started.' }
python .\soak_runner.py --command 'node node_modules/vitest/vitest.mjs run helpers/BodulHalCore.spec.tsx helpers/McpGuardTool.spec.tsx --globals' --hours 8 --output soak-results
if ($LASTEXITCODE -ne 0) { throw 'Soak did not PASS; inspect soak-results/summary.json.' }
Write-Host 'Local unit-test soak finished. Inspect soak-results/summary.json; this does not certify live MCP.'
