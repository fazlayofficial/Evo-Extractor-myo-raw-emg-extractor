@echo off
call .venv\Scripts\activate
pyinstaller --onefile --windowed --name "Evo_Extractor" --icon=logo.png --add-data "logo.png;." --add-data "powered_by.png;." app.py
echo Build Complete. Check the 'dist' folder.
pause