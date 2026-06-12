@echo off
cd /d "%~dp0"
echo Starting HEPTA_GSApp from:
echo %CD%
echo.

set "BUNDLED_NODE=%~dp0tools\node\win-x64\node.exe"

if exist "%BUNDLED_NODE%" (
  "%BUNDLED_NODE%" start-server.js
) else (
  node start-server.js
)
