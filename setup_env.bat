@echo off
echo [1/3] Creating Virtual Environment...
python -m venv .venv
echo [2/3] Setting Execution Policy...
powershell -Command "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser"
echo [3/3] Installing Dependencies...
call .venv\Scripts\activate
pip install -r requirements.txt
echo Setup Complete!
pause