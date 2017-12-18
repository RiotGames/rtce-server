:: Usage: scripts\generate_python.cmd
::
:: Create the generated python files
python generate_python.py scripts\templates\routes.template --ignoreGetEvent > server\generated_routes.py
python generate_python.py scripts\templates\rpc_client.template > tests\rpc_client.py
