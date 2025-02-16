import os
import logging
from dotenv import load_dotenv
from datetime import datetime
from typing import List
import importlib
import sys
import json
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from redis import Redis
from rq_scheduler import Scheduler as RQScheduler
from rq.job import Job

# ---------------------------------------------------------------
# Carregamento e configuração de variáveis de ambiente (dotenv)
# ---------------------------------------------------------------
BASE_DIR = (
    os.path.dirname(os.path.abspath(sys.executable))
    if getattr(sys, 'frozen', False)
    else os.path.dirname(os.path.abspath(__file__))
)

dotenv_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path)  # Carrega as variáveis definidas no .env
load_dotenv()  # Chama novamente para garantir caso existam variáveis extras

# ---------------------------------------------------------------
# Configuração de logging
# ---------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "ERROR").upper()
numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
logging.basicConfig(
    level=numeric_level,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.info(f"LOG_LEVEL={LOG_LEVEL}")

# ---------------------------------------------------------------
# Conexão com Redis e criação do RQ Scheduler
# ---------------------------------------------------------------
REDIS_URL = "redis://redis:6379"
sync_redis_conn = Redis.from_url(REDIS_URL, decode_responses=True)
rq_scheduler = RQScheduler(connection=sync_redis_conn)

# ---------------------------------------------------------------
# Criação da aplicação FastAPI
# ---------------------------------------------------------------
app = FastAPI()

# ---------------------------------------------------------------
# Modelo Pydantic para receber dados de agendamento
# ---------------------------------------------------------------
class ScheduleTask(BaseModel):
    function: str = Field(..., description="Nome da função Ex: 'tasks.publish_event'")
    schedule_time: datetime = Field(..., description="Data e hora (UTC) para executar")
    args: List = Field(default_factory=list)
    kwargs: dict = Field(default_factory=dict)

# ---------------------------------------------------------------
# Rota: POST /schedule
# ---------------------------------------------------------------
@app.post("/schedule")
async def schedule_tasks(tasks: List[ScheduleTask], username: str = Depends(lambda: "admin")):
    jobs_info = []
    for task in tasks:
        try:
            module_name, function_name = task.function.rsplit('.', 1)
            mod = importlib.import_module(module_name)
            func = getattr(mod, function_name)
            job = rq_scheduler.enqueue_at(task.schedule_time, func, *task.args, **task.kwargs)
            jobs_info.append({"job_id": job.get_id(), "schedule_time": task.schedule_time})
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Erro ao agendar tarefa: {str(e)}")
    return {"message": "Tarefas agendadas com sucesso", "jobs": jobs_info}

# ---------------------------------------------------------------
# Rota: DELETE /schedule/{job_id}
# ---------------------------------------------------------------
@app.delete("/schedule/{job_id}")
async def remove_task(job_id: str, username: str = Depends(lambda: "admin")):
    try:
        job = Job.fetch(job_id, connection=sync_redis_conn)
        rq_scheduler.cancel(job)
        return {"message": "Tarefa removida com sucesso", "job_id": job_id}
    except Exception:
        raise HTTPException(status_code=404, detail="Job não encontrado")

# ---------------------------------------------------------------
# Rota: DELETE /schedule/date/{date_str}
# ---------------------------------------------------------------
@app.delete("/schedule/date/{date_str}")
async def remove_tasks_by_date(date_str: str, username: str = Depends(lambda: "admin")):
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de data inválido. Use YYYY-MM-DD.")

    removed_jobs = []
    for job in rq_scheduler.get_jobs():
        if job.scheduled_at.date() == target_date:
            removed_jobs.append(job.get_id())
            rq_scheduler.cancel(job)

    return {"message": "Tarefas removidas", "removed_jobs": removed_jobs}

# ---------------------------------------------------------------
# Rota: POST /message (Envio de mensagens não agendadas)
# ---------------------------------------------------------------
class NonScheduledMessage(BaseModel):
    channel: str = Field(..., description="Nome do canal Redis para publicação")
    cliente_id: int = Field(..., description="ID do cliente que receberá a mensagem")
    action_params: str = Field(..., description="Parâmetros da ação que será executada")

@app.post("/message")
async def create_message(msg: NonScheduledMessage, username: str = Depends(lambda: "admin")):
    """
    Recebe uma mensagem para ser publicada diretamente em um canal Redis no mesmo formato das mensagens agendadas.
    """
    event = {
        "cliente_id": msg.cliente_id,
        "action_params": msg.action_params
    }

    message = json.dumps(event)  # Converte para JSON antes de publicar
    sync_redis_conn.publish(msg.channel, message)
    
    return {"status": "ok", "channel": msg.channel, "content": event}
