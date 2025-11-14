cd /d "%~dp0"
call ".venv\Scripts\activate.bat"
python src\bmg_rest_node.py --node_url http://suestorm.cels.anl.gov:3003
pause
