import os
import sys
import subprocess
import time
import logging
from dotenv import load_dotenv
from rq_scheduler import Scheduler
from redis import Redis
from multiprocessing import Process

# -----------------------------------------
# Carrega .env (se existir) para o ambiente
# -----------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path)  # Carrega variáveis do .env

# -----------------------------------------
# Lê LOG_LEVEL do ambiente (padrão = ERROR)
# -----------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "ERROR").upper()
numeric_level = getattr(logging, LOG_LEVEL, logging.ERROR)

# -----------------------------------------
# Configura logging principal
# -----------------------------------------
logging.basicConfig(
    level=numeric_level,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# -----------------------------------------
# Ajusta logging específico do RQ (scheduler, worker) p/ mesmo nível
# -----------------------------------------
logging.getLogger("rq.scheduler").setLevel(numeric_level)
logging.getLogger("rq.worker").setLevel(numeric_level)
logging.getLogger("rq").setLevel(numeric_level)

# Conexão Redis
REDIS_URL = "redis://redis:6379"
redis_conn = Redis.from_url(REDIS_URL, decode_responses=False)

# Scheduler RQ
scheduler = Scheduler(connection=redis_conn)

def start_scheduler():
    """Inicia o RQ Scheduler em loop contínuo."""
    logging.info("🚀 RQ Scheduler iniciado...")
    while True:
        # Processa os jobs agendados imediatamente disponíveis
        scheduler.run(burst=False)
        time.sleep(5)

def start_worker():
    """Inicia o RQ Worker e reinicia se falhar."""
    while True:
        logging.info("🛠️  Iniciando RQ Worker...")
        # Inicia o worker via 'rq worker --url <REDIS_URL>'
        process = subprocess.Popen(
            ["rq", "worker", "--url", REDIS_URL],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Lê stdout linha a linha para logar
        for line in iter(process.stdout.readline, ''):
            logging.info(f"[RQ Worker] {line.strip()}")

        # Se o processo parou, considera que falhou e reinicia
        if process.poll() is not None:
            logging.error("❌ RQ Worker falhou! Reiniciando...")
            time.sleep(2)

if __name__ == "__main__":
    # Cria processos para Worker e Scheduler
    worker_process = Process(target=start_worker)
    scheduler_process = Process(target=start_scheduler)

    # Inicia ambos
    worker_process.start()
    scheduler_process.start()

    # Aguarda finalização
    worker_process.join()
    scheduler_process.join()
