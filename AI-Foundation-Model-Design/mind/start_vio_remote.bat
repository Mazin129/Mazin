@echo off
rem  start_vio_remote.bat  —  start Vio for secure remote access over Tailscale.
rem  It sets the host-allowlist + HTTPS flags Vio needs so it will accept your
rem  tailnet hostname instead of returning "{}" (a 403). Close the window to stop Vio.
rem
rem  ONE-TIME SETUP:
rem    1. Edit the TAILNET line below to your real tailnet hostname
rem       (run  tailscale serve --bg 8100  once and copy the https://NAME.ts.net host).
rem    2. First run will ask you to create a login token; it is saved to
rem       vio_token.txt (git-ignored, never committed) and reused after that.
rem    3. In a SEPARATE window run:  tailscale serve --bg 8100
rem       (only needed once per PC boot — it keeps running in the background).

cd /d "%~dp0"

rem ── your tailnet hostname (no https://, no slash, no port) ──────────────────
set "TAILNET=mazin.tailf89bb1.ts.net"

rem ── login token: read from vio_token.txt, or create it on first run ─────────
if not exist "vio_token.txt" (
  echo No login token yet. Type a long random code to protect Vio, then press Enter.
  set /p NEWTOK=Token:
  > "vio_token.txt" echo %NEWTOK%
  echo Saved to vio_token.txt  ^(keep it secret; it is not committed to git^).
)
set /p VIO_TOKEN=<vio_token.txt

rem ── security flags so Vio accepts the tailnet hostname over HTTPS ───────────
set "VIO_ALLOWED_HOSTS=%TAILNET%"
set "VIO_HTTPS=1"

echo.
echo Starting Vio for remote access.
echo   Local test : http://localhost:8100
echo   On phone   : https://%TAILNET%/   (Tailscale ON, log in with your token)
echo Close this window to stop Vio.
echo.
python web.py
pause
