@echo off
rem TongSheng launcher (LIVE / REC real-time voice translator)
rem Uses TONGSHENG_PYTHON when set, otherwise the shared PrivateVoice runtime,
rem otherwise whatever "python" is on PATH.
setlocal
cd /d "%~dp0"

if defined TONGSHENG_PYTHON goto :have_py
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
"%PY%" "tools\dev_run.py" %*
if errorlevel 1 pause
endlocal
