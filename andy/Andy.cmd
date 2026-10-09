@echo off
rem Starts Andy without a console window. Run andy\install-andy.ps1 once first.
cd /d "%~dp0.."
start "" "%LOCALAPPDATA%\Andy\venv\Scripts\pythonw.exe" -m andy
