@echo off
cd /d "%~dp0"
echo Open http://localhost:8000/ in your browser.
echo Keep this window open. Press Ctrl+C to stop.
python -m http.server 8000
pause
