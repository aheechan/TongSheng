@echo off
rem TongSheng launcher.
rem   1) packaged build -> %~dp0runtime\python.exe   (installed copy)
rem   2) development    -> shared PrivateVoice runtime
rem   3) fallback       -> python on PATH
setlocal
cd /d "%~dp0"

if defined TONGSHENG_PYTHON goto :have_py

if exist "%~dp0runtime\python.exe" (
  set "PY=%~dp0runtime\python.exe"
  goto :have_py
)
if exist "..\PrivateVoice\dist\PrivateVoice_Ahee52\runtime\python.exe" (
  set "PY=..\PrivateVoice\dist\PrivateVoice_Ahee52\runtime\python.exe"
  goto :have_py
)
if exist "C:\Local Repositories\PrivateVoice\dist\PrivateVoice_Ahee52\runtime\python.exe" (
  set "PY=C:\Local Repositories\PrivateVoice\dist\PrivateVoice_Ahee52\runtime\python.exe"
  goto :have_py
)
set "PY=python"

:have_py
if not exist "%~dp0tools\dev_run.py" (
  echo [TongSheng] tools\dev_run.py is missing - this copy looks incomplete.
  echo             Reinstall from the setup package.
  pause
  exit /b 2
)

"%PY%" "%~dp0tools\dev_run.py" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [TongSheng] exited with code %RC%.
  echo             Log:   %~dp0logs\app.log
  echo             Crash: %~dp0logs\crash.log
  pause
)
endlocal & exit /b %RC%
