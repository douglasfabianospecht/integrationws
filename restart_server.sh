#!/bin/bash

echo "Reiniciando server.py com 4 workers..."
pkill -f "uvicorn serverWS:app"
sleep 2
uvicorn serverWS:app --workers 4 --host 0.0.0.0 --port 9000 --log-level error &
echo "server.py reiniciado com sucesso!"
