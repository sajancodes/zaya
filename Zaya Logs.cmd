@echo off
chcp 65001 >nul
title Zaya runtime logs
cd /d "%~dp0"
".venv\Scripts\python.exe" -X utf8 -u "tools\view_zaya_logs.py"
if errorlevel 1 pause
