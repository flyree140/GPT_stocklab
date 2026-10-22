#!/bin/sh
cd "$(dirname "$0")" || exit 1
printf 'Open http://localhost:8000/ (Ctrl+C to stop)
'
python3 -m http.server 8000
