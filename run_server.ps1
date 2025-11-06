# Run the social server using the project Python. Prefers running run_server.py
# which will use waitress if available. If you need to force the dev server,
# set the environment variable FORCE_DEV=1 before running this script.
if (-not $env:SOCIAL_SERVER_PORT) {
	$env:SOCIAL_SERVER_PORT = "5000"
}
Write-Output "Starting social server on port $env:SOCIAL_SERVER_PORT..."
python run_server.py
