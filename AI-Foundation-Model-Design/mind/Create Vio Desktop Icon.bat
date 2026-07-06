@echo off
setlocal
set "MIND=%~dp0"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Vio.lnk'); $s.TargetPath='%MIND%Vio.bat'; $s.WorkingDirectory='%MIND%'; $s.IconLocation='shell32.dll,13'; $s.Save()"
echo.
echo Done!  A "Vio" icon is now on your Desktop. Double-click it anytime.
pause
