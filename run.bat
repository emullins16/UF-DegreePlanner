@echo off
echo Setting up environment...

REM Install required Python packages
pip install flask

echo Starting server...
python app.py
pause