@echo off
:loop
echo [Resurrection] ValH is rising...
uv run python main.py --bot
echo [Resurrection] ValH exited with code %ERRORLEVEL%. Restarting in 2 seconds...
timeout /t 2 > nul
goto loop