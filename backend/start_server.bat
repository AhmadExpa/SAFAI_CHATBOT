@echo off
echo Setting UTF-8 encoding environment variables...
chcp 65001
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set LC_ALL=en_US.UTF-8
set LANG=en_US.UTF-8
set PYTHONLEGACYWINDOWSSTDIO=utf-8
set PYTHONHASHSEED=0

echo Starting server with UTF-8 encoding...
python run_server.py
