@echo off
echo Installing dependencies...
python -m pip install -r requirements.txt
echo.
echo Starting Rummy Royale...
python app.py
pause
