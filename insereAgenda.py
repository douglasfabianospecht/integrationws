import requests
from datetime import datetime, time as dt_time, timedelta, timezone

# Obtém a data/hora atual com fuso horário UTC
hoje_utc = datetime.now(timezone.utc)
# Cria um objeto datetime para hoje às 17:20 (UTC)
horario_agendado = datetime.combine(hoje_utc, dt_time(11, 10, tzinfo=timezone.utc))
if horario_agendado < hoje_utc:
    # Se o horário já passou, agenda para o próximo dia
    horario_agendado += timedelta(days=1)

# Cria o payload para o endpoint /schedule.
# A API espera uma lista de tarefas.
payload = [
    {
        "function": "tasks.publish_event",
        # Usa apenas isoformat(), pois ele já inclui o offset (ex.: 2025-02-09T17:20:00+00:00)
        "schedule_time": horario_agendado.isoformat(),
        "args": [
            9002,
            "GetBooks&companyid=9001&startdate=2022-08-11&enddate=2022-08-15"
        ],
        "kwargs": {}
    }
]

# URL do endpoint da API (ajuste conforme sua configuração)
url = "http://localhost:9001/schedule/"

response = requests.post(url, json=payload)
print(response.json())
