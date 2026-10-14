@echo off
cd /d "%~dp0"
if exist "dist\REmmanager.exe" (
  start "" "dist\REmmanager.exe" %*
) else (
  echo Build first: powershell -File tools\build_winui.ps1
  pause
)
