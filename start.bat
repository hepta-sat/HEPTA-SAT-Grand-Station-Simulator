@echo off
cd /d "%~dp0"
echo Starting HEPTA_GSApp from:
echo %CD%
echo.

set "BUNDLED_NODE=%~dp0tools\node\win-x64\node.exe"
set "RSSI_ATDB_INTERVAL=5"

if exist "%~dp0.venv\Scripts\python.exe" (
  set "HEPTA_PYTHON=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0.venv-1\Scripts\python.exe" (
  set "HEPTA_PYTHON=%~dp0.venv-1\Scripts\python.exe"
) else (
  set "HEPTA_PYTHON=python"
)

echo receive_data.py will start from the UI connection button.
echo XBee ATDB RSSI polling interval: %RSSI_ATDB_INTERVAL%s.
echo If multiple COM ports exist, set SERIAL_PORT before running this file. Example: set SERIAL_PORT=COM4
echo.

if exist "%BUNDLED_NODE%" (
  "%BUNDLED_NODE%" start-server.js
) else (
  node start-server.js
)
