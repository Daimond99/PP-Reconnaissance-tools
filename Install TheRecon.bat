@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 (
  echo.
  echo Install did not finish. Read the message above, fix it, then run this file again.
) else (
  echo.
  echo Install finished. Open TheRecon from the Desktop shortcut or double-click TheRecon.bat.
)
pause
