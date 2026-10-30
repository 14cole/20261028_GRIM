@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
where py.exe >nul 2>&1
if errorlevel 1 goto use_python
py.exe -3 -m venv ".venv"
if errorlevel 1 goto failed
goto install
:use_python
where python.exe >nul 2>&1
if errorlevel 1 goto missing_python
python.exe -m venv ".venv"
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -c "import platform,struct,sys; assert sys.version_info >= (3,11), 'Python 3.11 or later is required'; assert struct.calcsize('P') == 8 and platform.machine().lower() in ('amd64','x86_64'), 'Use 64-bit x64 Python for the supplied Windows DLLs'"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "requirements.txt"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "import numpy,scipy,matplotlib,PySide6,psutil,PIL,imageio_ffmpeg,mpmath,pythoncom; import GRIM_Backend.ui.app"
if errorlevel 1 goto failed
echo Setup complete. Open Launch_GRIM.bat to start the application.
pause
exit /b 0
:missing_python
echo Install 64-bit x64 Python 3.11 or later, then run this script again.
pause
exit /b 1
:failed
echo Setup failed. Review the error above. No application files were replaced.
pause
exit /b 1
