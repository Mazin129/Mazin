@echo off
rem  install_autostart.bat  —  make Vio start automatically (hidden) at every login.
rem  Double-click this once. From then on Vio is always running at http://localhost:8100.
setlocal
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS=%STARTUP%\Vio.vbs"

rem  write a tiny launcher into the Windows Startup folder (runs Vio with no window)
>"%VBS%"  echo Set W = CreateObject("WScript.Shell")
>>"%VBS%" echo W.CurrentDirectory = "%HERE%"
>>"%VBS%" echo W.Run "pythonw web.py --service", 0, False

echo(
echo   Vio will now start automatically (hidden) every time you log in.
echo   Folder: %HERE%
echo(
echo   Starting Vio now...
wscript "%VBS%"
echo   Waiting a few seconds for it to come up...
timeout /t 4 >nul
start "" http://localhost:8100
echo(
echo   Done.  Vio is running at  http://localhost:8100
echo(
echo   To stop it now:            stop_vio.bat
echo   To turn off auto-start:    uninstall_autostart.bat
echo(
pause
