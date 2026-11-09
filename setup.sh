#!/bin/bash
set -e  # stop on first error

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Playwright Chromium browser..."
python -m playwright install chromium

echo "✅ Setup complete."