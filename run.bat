@echo off
rem 同声 TongSheng launcher
rem Uses TONGSHENG_PYTHON when set, otherwise the shared PrivateVoice runtime,
rem otherwise whatever "python" is on PATH.
setlocal
cd /d "%~dp0"

if defined TONGSHENG_PYTHON (
  set "PY=%TONGSHENG_PYTHON%"
) else if exist "..\PrivateVoice\dist\PrivateVoice_Ahee52\runtime\python.exe" (
  set "PY=..\PrivateVoice\dist\PrivateVoice_Ahee52\runtime\python.exe"
) else if exist "C:\Local Repositories\PrivateVoice\dist\PrivateVoice_Ahee52\runtime\python.exe" (
  set "PY=C:\Local Repositories\PrivateVoice\dist\PrivateVoice_Ahee52\runtime\python.exe"
) else (
  set "PY=python"
)

"%PY%" "tools\dev_run.py" %*
if errorlevel 1 pause
endlocal
