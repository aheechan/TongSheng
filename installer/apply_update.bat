@echo off
rem TongSheng manual update helper.
rem
rem Usage: copy this whole folder into the TongSheng install directory
rem        (for example D:\TongSheng\TongSheng-update), then run apply_update.bat.
rem        Everything is merged into the parent folder; nothing is deleted.
setlocal EnableExtensions
cd /d "%~dp0"

set "SRC=%~dp0"
set "SRC=%SRC:~0,-1%"
for %%I in ("%~dp0..") do set "DEST=%%~fI"

echo Source : %SRC%
echo Target : %DEST%
echo.

if not exist "%DEST%\runtime\python.exe" (
  echo [ERROR] %DEST% does not look like a TongSheng installation
  echo         ^(missing runtime\python.exe^).
  echo         Copy this folder into the folder that contains runtime\
  echo         and run apply_update.bat again.
  pause
  exit /b 2
)

rem Make sure TongSheng is not running: it holds .pyd/.dll files open.
tasklist /FI "IMAGENAME eq pythonw.exe" | find /I "pythonw.exe" >nul && (
  echo [WARN] pythonw.exe is running. Quit TongSheng first, then re-run.
  pause
  exit /b 3
)

echo Copying program files...
robocopy "%SRC%" "%DEST%" /E /R:1 /W:1 /NFL /NDL /NJH /NJS ^
  /XF "apply_update.bat" ^
  /XD "voice-repository" "logs" "results" "config.yaml" "%SRC%" >nul
if errorlevel 8 (
  echo [ERROR] copy failed with code %ERRORLEVEL%
  pause
  exit /b 4
)

if not exist "%DEST%\voice-repository\Default_Voice\profile.json" (
  echo Restoring the bundled default voice...
  robocopy "%SRC%voice-repository" "%DEST%\voice-repository" /E /R:1 /W:1 /NFL /NDL /NJH /NJS >nul
)

echo.
echo Installed version:
"%DEST%\runtime\python.exe" -c "import sys;sys.path.insert(0,r'%DEST%');import tongsheng;print('  ' + tongsheng.__version__)"
echo.
echo Done. Start TongSheng from the desktop shortcut, then run the Self-test.
pause
endlocal
