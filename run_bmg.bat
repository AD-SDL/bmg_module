cd /d "%~dp0"
call ".venv\Scripts\activate.bat"
python src\bmg_rest_node.py --port 3003
pause
