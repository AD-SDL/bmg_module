cd /d "%~dp0"
call ".venv\Scripts\activate.bat"
python src\bmg_rest_node.py --node_url http://suestorm.cels.anl.gov:3003 --node_definition "C:\\Users\\RPL\\source\\repos\\bmg_module\\definitions\\bmg_billy.node.yaml"
pause
