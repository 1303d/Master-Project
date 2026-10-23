@echo off
rem Share the UI with teammates: a password-protected server (UI_PASSWORD in .env) on port 8770 plus a
rem Cloudflare quick tunnel. The https link is printed below and changes every run; close this window to stop sharing.
cd /d C:\master
findstr /b "UI_PASSWORD=" .env >nul || (echo UI_PASSWORD is missing in .env - refusing to share without a password & exit /b 1)
start "Skill UI server (shared)" /min "C:\Users\dhanu\AppData\Local\Programs\Python\Python311\python.exe" app\server.py --port 8770
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --no-autoupdate --url http://127.0.0.1:8770
