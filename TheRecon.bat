@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo TheRecon is not installed yet. Run "Install TheRecon.bat" first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m src.main
