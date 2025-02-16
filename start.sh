#!/bin/bash

echo "Iniciando server.py com 4 workers..."
uvicorn serverWS:app --workers 4 --host 0.0.0.0 --port 9000 --log-level error --reload &

echo "Iniciando scheduler_api.py com 2 workers..."
uvicorn scheduler_api:app --host 0.0.0.0 --port 9001 --workers 2 --log-level error --reload &  

echo "Iniciando qt.py..."
python /usr/src/app/qt.py --log-level error &  

# Mantém o container rodando
wait
