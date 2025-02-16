import requests
import json
from datetime import datetime, timezone, time as dt_time, timedelta

# Obtém a data/hora atual com fuso horário UTC
hoje_utc = datetime.now(timezone.utc)

# Define os dados corretos para envio
payload = {
    "channel": "canal_eventos",  # Nome do canal Redis onde será publicada a mensagem
    "cliente_id": 9002,  # ID do cliente que receberá a mensagem
    "action_params": "GetBooks&companyid=9001&startdate=2022-08-11&enddate=2022-08-15"
}

# URL do endpoint da API para publicação direta
API_URL = "http://localhost:9001/message"

# Envia a requisição POST
response = requests.post(API_URL, json=payload)

# Exibe a resposta
print(f"Status Code: {response.status_code}")
print("Resposta:", response.json())
