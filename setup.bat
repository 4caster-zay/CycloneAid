@echo off
setlocal
py -3.12 "%~dp0tools\prepare_test_env.py"
if errorlevel 1 pause
