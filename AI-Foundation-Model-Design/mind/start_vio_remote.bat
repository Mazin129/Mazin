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

setlocal enabledelayedexpansion
cd /d "%~dp0"

rem ── your tailnet hostname (no https://, no slash, no port) ──────────────────
set "TAILNET=mazin.tailf89bb1.ts.net"

rem ── login token: read from vio_token.txt, or create it on first run ─────────
rem  delayed expansion (!NEWTOK!) is required so the value is read AFTER you type
rem  it; %NEWTOK% inside this block would expand too early and save a blank token.
rem  <nul set /p writes the token with NO trailing newline so it matches exactly.
if not exist "vio_token.txt" (
  echo No login token yet. Type a long code to protect Vio, then press Enter.
  set /p "NEWTOK=Token: "
  <nul set /p "=!NEWTOK!" > "vio_token.txt"
  echo Saved to vio_token.txt  ^(keep it secret; it is not committed to git^).
)
set /p "VIO_TOKEN=" < "vio_token.txt"

rem ── security flags so Vio accepts the tailnet hostname over HTTPS ───────────
set "VIO_ALLOWED_HOSTS=%TAILNET%"
set "VIO_HTTPS=1"

rem ── reasoning model: pick one that FITS this PC's GPU so it actually finishes.
rem  An 8B model on a 2 GB card runs on the CPU and times out (Vio then falls back
rem  to raw matches). A 3B model fits and is fast. First run:  ollama pull llama3.2:3b
rem  Leave blank to let Vio auto-pick the best installed model.
rem  qwen2.5:3b fits a 2 GB GPU and is stronger than llama3.2:3b for network/security.
rem  Switch to qwen2.5:7b (smarter, CPU, slower) live from the /dashboard brain menu.
set "VIO_LLM_MODEL=qwen2.5:3b"

rem ── OPTIONAL: break the local model-quality ceiling with a HOSTED big model.
rem  Uncomment and fill in to point Vio at any OpenAI-compatible endpoint (OpenRouter,
rem  Together, Groq, a rented vLLM/GPU, …). Fast AND smart, but it COSTS money per use
rem  and your prompts leave this PC — so it's off by default. Keep the key secret.
rem  set "VIO_LLM_API=openai"
rem  set "VIO_LLM_URL=https://openrouter.ai/api/v1"
rem  set "VIO_LLM_KEY=sk-your-key-here"
rem  set "VIO_LLM_MODEL=meta-llama/llama-3.1-70b-instruct"

rem ── internet research: let Vio search the web, read pages, and learn from them.
rem  Read-only over the public web, with SSRF protection. To restrict which sites it
rem  may read, set VIO_NET_ALLOW=example.com,docs.site (blank = any public site).
rem  Set VIO_ALLOW_NET=0 to turn web research off entirely.
set "VIO_ALLOW_NET=1"

echo.
echo Starting Vio for remote access.
echo   Local test : http://localhost:8100
echo   On phone   : https://%TAILNET%/   (Tailscale ON, log in with your token)
echo Close this window to stop Vio.
echo.
python web.py
pause
