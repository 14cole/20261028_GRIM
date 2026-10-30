@echo off
setlocal
cd /d "%~dp0"
set "GRIM_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%GRIM_PYTHON%" goto missing_environment
"%GRIM_PYTHON%" -c "import GRIM_Backend.ui.app"
if errorlevel 1 goto missing_environment
if /I "%~1"=="--check" exit /b 0
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0GRIM_Backend\run_gui.py"
exit /b 0
:missing_environment
echo The GRIM environment is missing or incomplete. Run Setup_GRIM.bat first.
if /I "%~1"=="--check" exit /b 1
pause
exit /b 1
