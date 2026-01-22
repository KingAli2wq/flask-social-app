Param()

$ErrorActionPreference = 'Stop'

# Run the script from the repository root.
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

# Activate the Python virtual environment located at .venv.
$venvActivate = Join-Path $repoRoot '.venv\Scripts\Activate.ps1'
if (-not (Test-Path $venvActivate)) {
    throw "Missing virtual environment activation script at $venvActivate"
}
. $venvActivate

# Install Alembic in the virtual environment if it is not already available.
if (-not (Get-Command alembic -ErrorAction SilentlyContinue)) {
    Write-Host 'Installing Alembic...' -ForegroundColor Cyan
    python -m pip install alembic | Out-Null
}

$alembicIni = Join-Path $repoRoot 'alembic.ini'
$alembicDir = Join-Path $repoRoot 'alembic'
$versionsDir = Join-Path $alembicDir 'versions'

# Ensure DATABASE_URL is present for Alembic configuration.
$databaseUrl = $env:DATABASE_URL
if (-not $databaseUrl) {
    throw 'DATABASE_URL environment variable is not set.'
}

# Create or update alembic.ini with a standard configuration.
if (-not (Test-Path $alembicIni)) {
    Write-Host 'Creating alembic.ini with default configuration.' -ForegroundColor Cyan
    $iniContent = @"
[alembic]
script_location = alembic
sqlalchemy.url = $databaseUrl

target_metadata = None

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers = console
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers = console
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s %(asctime)s [%(name)s] %(message)s
datefmt = %Y-%m-%d %H:%M:%S
"@
    Set-Content -Path $alembicIni -Value $iniContent -Encoding UTF8
}
else {
    # Update sqlalchemy.url to the current DATABASE_URL if the file already exists.
    $content = Get-Content $alembicIni
    $updated = $false
    $content = $content | ForEach-Object {
        if ($_ -match '^\s*sqlalchemy\.url\s*=') {
            $updated = $true
            "sqlalchemy.url = $databaseUrl"
        }
        else {
            $_
        }
    }
    if (-not $updated) {
        $content += "sqlalchemy.url = $databaseUrl"
    }
    Set-Content -Path $alembicIni -Value $content -Encoding UTF8
}

# Ensure the Alembic versions directory exists.
if (-not (Test-Path $versionsDir)) {
    New-Item -ItemType Directory -Path $versionsDir | Out-Null
}

# Run the database migrations using Alembic.
# Note: this repo can have multiple Alembic heads; use `heads` to upgrade all branches.
alembic upgrade heads
