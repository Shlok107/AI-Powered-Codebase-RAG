[CmdletBinding()]
param(
  [ValidateSet('all', 'backend', 'backend-unit', 'backend-integration', 'frontend', 'backend-coverage', 'frontend-coverage')]
  [string]$Scope = 'all'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $repoRoot 'backend'
$frontendPath = Join-Path $repoRoot 'frontend'
$pythonCommand = if ($env:CODEBASE_RAG_PYTHON) { $env:CODEBASE_RAG_PYTHON } else { 'python' }

function Invoke-BackendTests([string[]]$pytestArgs) {
  Push-Location $backendPath
  try {
    & $pythonCommand -m pytest @pytestArgs
    if ($LASTEXITCODE -ne 0) { throw "Backend pytest exited with code $LASTEXITCODE" }
  }
  finally {
    Pop-Location
  }
}

function Invoke-FrontendTests([switch]$Build, [switch]$Coverage) {
  Push-Location $frontendPath
  try {
    if ($Build) {
      & npm run build
    } elseif ($Coverage) {
      & npm run test:coverage
    } else {
      & npm test
    }
    if ($LASTEXITCODE -ne 0) { throw "Frontend command exited with code $LASTEXITCODE" }
  }
  finally {
    Pop-Location
  }
}

if ($Scope -in @('all', 'backend', 'backend-integration', 'backend-coverage') -and -not $env:TEST_DATABASE_URL) {
  throw 'This scope requires TEST_DATABASE_URL pointing to a dedicated PostgreSQL database with pgvector. The test harness rejects databases whose name does not contain "test".'
}

switch ($Scope) {
  'all' {
    Invoke-BackendTests @()
    Invoke-FrontendTests -Coverage
    Invoke-FrontendTests -Build
  }
  'backend' { Invoke-BackendTests @() }
  'backend-unit' { Invoke-BackendTests @('-m', 'unit') }
  'backend-integration' { Invoke-BackendTests @('-m', 'integration and database') }
  'backend-coverage' { Invoke-BackendTests @('--cov=app', '--cov-report=term-missing', '--cov-report=xml:coverage.xml') }
  'frontend' { Invoke-FrontendTests }
  'frontend-coverage' { Invoke-FrontendTests -Coverage }
}
