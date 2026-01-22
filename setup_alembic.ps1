Param()

$ErrorActionPreference = 'Stop'

# Ensure the script runs from the repository root.
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

# Activate the Python virtual environment.
$venvActivate = Join-Path $repoRoot '.venv\Scripts\Activate.ps1'
if (-not (Test-Path $venvActivate)) {
    throw "Virtual environment activation script not found at $venvActivate"
}
. $venvActivate

# Confirm Alembic is installed before proceeding.
if (-not (Get-Command alembic -ErrorAction SilentlyContinue)) {
    throw "Alembic CLI not found. Install it in the virtual environment first."
}

$alembicIni = Join-Path $repoRoot 'alembic.ini'
$alembicDir = Join-Path $repoRoot 'alembic'
$versionsDir = Join-Path $alembicDir 'versions'

# Initialise Alembic if it has not been set up yet.
if (-not (Test-Path $alembicIni)) {
    alembic init alembic | Out-Null
}

# Make sure the versions directory exists.
if (-not (Test-Path $versionsDir)) {
    New-Item -ItemType Directory -Path $versionsDir | Out-Null
}

# Update the database URL in alembic.ini using the DATABASE_URL environment variable.
$databaseUrl = $env:DATABASE_URL
if (-not $databaseUrl) {
    throw "DATABASE_URL environment variable is not set."
}

$iniContent = Get-Content $alembicIni

if ($iniContent -match '^\s*sqlalchemy\.url\s*=') {
    $iniContent = $iniContent -replace '^\s*sqlalchemy\.url\s*=.*$', "sqlalchemy.url = $databaseUrl"
}
else {
    $iniContent += "sqlalchemy.url = $databaseUrl"
}
Set-Content -Path $alembicIni -Value $iniContent

# Move the migration script into alembic/versions if it is not already there.
$migrationNames = @(
    '20241120_add_bio_media_asset.py',
    '20241120_add_bio_and_media_asset_id.py'
)
foreach ($migrationName in $migrationNames) {
    $sourcePath = Join-Path $repoRoot $migrationName
    if (Test-Path $sourcePath) {
        $destinationPath = Join-Path $versionsDir $migrationName
        if (-not (Test-Path $destinationPath)) {
            Move-Item -Path $sourcePath -Destination $destinationPath
        }
    }
}

# Apply the latest migrations.
# Note: this repo can have multiple Alembic heads; use `heads` to upgrade all branches.
alembic upgrade heads
