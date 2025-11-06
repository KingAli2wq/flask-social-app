@echo off
if "%SOCIAL_SERVER_PORT%"=="" set SOCIAL_SERVER_PORT=5000
echo Starting social server on port %SOCIAL_SERVER_PORT%...
python run_server.py
