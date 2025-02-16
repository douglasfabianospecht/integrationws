#!/bin/bash

echo "Reiniciando qt.py..."
pkill -f "python /usr/src/app/qt.py"
sleep 2
python /usr/src/app/qt.py &
echo "qt.py reiniciado com sucesso!"
