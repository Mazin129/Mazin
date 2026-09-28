@echo off
rem  start_vio_cloudflare.bat  —  reach Vio from anywhere through a Cloudflare Tunnel.
rem
rem  Unlike Tailscale (private to your own devices), a Cloudflare tunnel puts Vio on the
rem  PUBLIC INTERNET. Anyone who gets the link reaches the login page, so this script
rem  will not run without a login token, and Vio refuses every tunnelled request that
rem  has not signed in.
rem
rem  TWO MODES
rem    Quick tunnel (default)  no Cloudflare account needed. You get a random
rem                            https://xxxx.trycloudflare.com address that CHANGES
rem                            every time you start. Good for trying it out.
rem    Named tunnel            a fixed address on your own domain. Set CF_TUNNEL and
rem                            CF_HOSTNAME below (one-time setup at the bottom). Pair it
rem                            with Cloudflare Access for an email check in front of Vio.
rem
rem  ONE-TIME SETUP
rem    winget install --id Cloudflare.cloudflared

setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ── Named tunnel (optional). Leave both blank for a quick tunnel. ─────────────
set "CF_TUNNEL="
set "CF_HOSTNAME="

rem ── cloudflared must be installed ────────────────────────────────────────────
where cloudflared >nul 2>nul
if errorlevel 1 (
  echo.
  echo cloudflared is not installed. Install it once with:
  echo     winget install --id Cloudflare.cloudflared
  echo then close this window, open a new one, and run this script again.
  echo.
  pause
  exit /b 1
)

rem ── login token: read from vio_token.txt, or create it on first run ─────────
rem  Same file as start_vio_remote.bat, so one token works for both.
if not exist "vio_token.txt" (
  echo No login token yet. Type a LONG code to protect Vio, then press Enter.
  echo This is what stands between the internet and your configs — make it long.
  set /p "NEWTOK=Token: "
  <nul set /p "=!NEWTOK!" > "vio_token.txt"
  echo Saved to vio_token.txt  ^(keep it secret; it is not committed to git^).
)
set /p "VIO_TOKEN=" < "vio_token.txt"
if "!VIO_TOKEN!"=="" (
  echo.
  echo vio_token.txt is empty. Delete it and run this script again to set a token.
  pause
  exit /b 1
)

rem ── tell Vio a tunnel is in use: it will demand the token for tunnelled traffic ─
set "VIO_CLOUDFLARE=1"
set "VIO_HTTPS=1"
if "!CF_HOSTNAME!"=="" (
  rem  a quick tunnel's hostname is random, so allow the whole trycloudflare domain
  set "VIO_ALLOWED_HOSTS=.trycloudflare.com"
) else (
  set "VIO_ALLOWED_HOSTS=!CF_HOSTNAME!"
)

rem ── model: leave unset so Vio picks the best INSTALLED model. (Naming one that
rem  isn't installed makes Vio silently pick another — see `python doctor.py`.)
set "VIO_ALLOW_NET=1"

echo.
echo Starting Vio in a second window...
start "Vio" cmd /k python web.py --service
rem  give Vio time to load its library before the tunnel starts sending traffic
timeout /t 8 /nobreak >nul

echo.
if "!CF_TUNNEL!"=="" (
  echo Opening a QUICK tunnel. Look below for a line like:
  echo     https://something-random.trycloudflare.com
  echo That is your address. Open it on your phone and sign in with your token.
  echo It changes every time you run this script.
  echo.
  echo Close this window to stop the tunnel ^(close the "Vio" window to stop Vio^).
  echo.
  cloudflared tunnel --url http://localhost:8100
) else (
  echo Opening named tunnel "!CF_TUNNEL!" at https://!CF_HOSTNAME!/
  echo.
  cloudflared tunnel run "!CF_TUNNEL!"
)
pause
exit /b 0

rem ─────────────────────────────────────────────────────────────────────────────
rem  NAMED TUNNEL — one-time setup (needs a domain on your Cloudflare account)
rem    cloudflared tunnel login
rem    cloudflared tunnel create vio
rem    cloudflared tunnel route dns vio vio.yourdomain.com
rem  Then create %USERPROFILE%\.cloudflared\config.yml containing:
rem      tunnel: vio
rem      credentials-file: C:\Users\<you>\.cloudflared\<tunnel-id>.json
rem      ingress:
rem        - hostname: vio.yourdomain.com
rem          service: http://localhost:8100
rem        - service: http_status:404
rem  and set above:  CF_TUNNEL=vio   CF_HOSTNAME=vio.yourdomain.com
rem
rem  STRONGLY RECOMMENDED for a named tunnel: in the Cloudflare Zero Trust dashboard,
rem  add an Access application for vio.yourdomain.com with an email-OTP policy that
rem  allows only your address. Cloudflare then checks who you are before a request
rem  ever reaches your PC — Vio's token becomes the second lock, not the only one.
rem ─────────────────────────────────────────────────────────────────────────────
