@echo off
setlocal
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0storm_tracker_gui.py" %*
) else (
    py -3.12 "%~dp0storm_tracker_gui.py" %*
)
if errorlevel 1 pause
