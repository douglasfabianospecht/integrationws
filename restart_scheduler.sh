#!/bin/bash

echo "Reiniciando scheduler_api.py com 4 workers..."
pkill -f "uvicorn scheduler_api:app"
sleep 2
uvicorn scheduler_api:app --workers 4 --host 0.0.0.0 --port 9001 --log-level debug --reload &
echo "scheduler_api.py reiniciado com sucesso!"