@echo off
rem 同声 TongSheng launcher
rem Uses TONGSHENG_PYTHON when set, otherwise the shared PrivateVoice runtime,
rem otherwise whatever "python" is on PATH.
setlocal
cd /d "%~dp0"

if defined TONGSHENG_PYTHON (
  set "PY=%TONGSHENG_PYTHON%"
) else if exist "C:\Local Repositories\PrivateVoice\dist\PrivateVoice_Ahee52\runtime\python.exe" (
  set "PY=C:\Local Repositories\PrivateVoice\dist\PrivateVoice_Ahee52\runtime\python.exe"
) else (
  set "PY=python"
)

"%PY%" -c "import sys; sys.path.insert(0, r'%~dp0'); from tongsheng.__main__ import main; raise SystemExit(main())" %*
if errorlevel 1 pause
endlocal
