@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy-rsna.ps1"
if errorlevel 1 (
  echo Deployment needs attention. See the message above.
) else (
  echo Deployment completed.
)
pause
