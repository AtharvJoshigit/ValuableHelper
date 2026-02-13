#!/bin/bash
echo "Starting ValuableHelper Telegram Bot..."

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "Virtual environment not found. Please run 'python3 -m venv .venv' and install dependencies."
    exit 1
fi

python main.py