@echo off
echo Starting ValuableHelper Telegram Bot...

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo Virtual environment not found. Please run 'python -m venv .venv' and install dependencies.
    pause
    exit /b
)

python main.py
pause