import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Dict
from dotenv import load_dotenv

import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

# -----------------------------------------------------------------------------
# Configuração de logging
# -----------------------------------------------------------------------------
# Garante que o .env seja carregado externamente
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path)
LOG_LEVEL = os.getenv("LOG_LEVEL", "ERROR").upper()
numeric_level = getattr(logging, LOG_LEVEL, None)
if not isinstance(numeric_level, int):
    numeric_level = logging.INFO

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=numeric_level
)

# -----------------------------------------------------------------------------
# IDENTIFICADOR ÚNICO PARA CADA WORKER
# -----------------------------------------------------------------------------
MY_WORKER_ID = os.getenv("WORKER_ID", f"worker-{uuid.uuid4().hex[:8]}")

# -----------------------------------------------------------------------------
# Configuração do Redis
# -----------------------------------------------------------------------------
REDIS_URL = "redis://redis:6379"
CHANNEL = "canal_eventos"
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# -----------------------------------------------------------------------------
# Usuário e Senha válidos para autenticação
# -----------------------------------------------------------------------------
VALID_USERS = {
    "user": "user123"
}

def authenticate(username: str, password: str) -> bool:
    """Valida as credenciais do usuário."""
    return VALID_USERS.get(username) == password

# -----------------------------------------------------------------------------
# Armazena mensagem pendente no Redis
# -----------------------------------------------------------------------------
async def store_pending_message(cliente_id: int, message: dict):
    """
    Insere a mensagem na lista 'pending_messages:{cliente_id}' e
    define um TTL (ex: 24h).
    """
    key = f"pending_messages:{cliente_id}"
    await redis_client.rpush(key, json.dumps(message))
    await redis_client.expire(key, 86400)  # 24 horas
    logging.info(f"[REDIS] Mensagem armazenada para cliente {cliente_id}: {message}")

# -----------------------------------------------------------------------------
# Função para armazenar mensagem se cliente estiver OFFLINE
# -----------------------------------------------------------------------------
async def store_message_if_offline(cliente_id: int, message: dict):
    """
    Usa um lock simples (setnx) para evitar duplicações.
    Assim, só um worker insere a mensagem pendente se o cliente estiver offline.
    """
    lock_key = f"pending_lock:{cliente_id}"
    was_set = await redis_client.setnx(lock_key, "1")
    if was_set:
        # Conseguiu o lock => armazena a mensagem
        await store_pending_message(cliente_id, message)
        # Expira o lock em poucos segundos
        await redis_client.expire(lock_key, 2)
    else:
        # Outro worker já armazenou
        logging.debug(f"[STORE_OFFLINE] Lock já ocupado para {cliente_id}, não armazenando duplicado.")

# -----------------------------------------------------------------------------
# Gerenciador de conexões WebSocket
# -----------------------------------------------------------------------------
class ConnectionManager:
    """
    Armazena conexões WebSocket locais em 'active_connections'.
    Usa Redis 'active_clients' para saber se o cliente está conectado em qualquer worker.
    """
    def __init__(self, redis_client):
        self.active_connections: Dict[int, WebSocket] = {}
        self.redis_client = redis_client

    async def connect(self, cliente_id: int, websocket: WebSocket):
        """Registra a conexão do cliente neste worker; fecha se já existir duplicada."""
        if cliente_id in self.active_connections:
            logging.warning(f"[WEBSOCKET] Cliente {cliente_id} já conectado neste worker. Fechando conexão anterior...")
            await self.disconnect(cliente_id)

        self.active_connections[cliente_id] = websocket
        await self.redis_client.sadd("active_clients", cliente_id)
        logging.info(f"[WEBSOCKET] Cliente {cliente_id} registrado no worker {MY_WORKER_ID}.")

    async def disconnect(self, cliente_id: int):
        """Remove a conexão do cliente deste worker e atualiza 'active_clients' no Redis."""
        ws = self.active_connections.get(cliente_id)
        if ws:
            try:
                if ws.client_state not in (WebSocketState.DISCONNECTED, WebSocketState.CLOSED):
                    await ws.close()
            except Exception as e:
                logging.error(f"[WEBSOCKET] Erro ao fechar conexão do cliente {cliente_id}: {e}")

            self.active_connections.pop(cliente_id, None)
            await self.redis_client.srem("active_clients", cliente_id)
            logging.info(f"[WEBSOCKET] Cliente {cliente_id} desconectado e removido.")

    async def send_message(self, cliente_id: int, message: dict):
        """
        Se o cliente estiver conectado neste worker, envia via WebSocket.
        Caso contrário, armazena pendente (se ele estiver realmente offline).
        """
        connection = self.active_connections.get(cliente_id)
        if connection:
            try:
                logging.info(f"[WEBSOCKET] Enviando mensagem para cliente {cliente_id} no worker {MY_WORKER_ID}: {message}")
                await connection.send_json(message)
                logging.info(f"[WEBSOCKET] Mensagem enviada para {cliente_id}")
            except Exception as e:
                logging.error(f"[WEBSOCKET] Erro ao enviar mensagem para {cliente_id}: {e}")
        else:
            # Não está conectado aqui => vamos conferir se está offline
            logging.warning(f"[WEBSOCKET] Cliente {cliente_id} não está conectado neste worker {MY_WORKER_ID}.")
            await store_message_if_offline(cliente_id, message)

    async def send_pending_messages(self, cliente_id: int, websocket: WebSocket):
        """
        Lê a lista 'pending_messages:{cliente_id}' no Redis e envia tudo ao cliente.
        """
        key = f"pending_messages:{cliente_id}"
        while True:
            message = await self.redis_client.lpop(key)
            if message is None:
                logging.debug(f"[PENDENTES] Fim das mensagens pendentes para cliente {cliente_id}.")
                break

            logging.debug(f"[PENDENTES] Lido do Redis para {cliente_id}: {message}")
            try:
                data = json.loads(message)
                await websocket.send_json(data)
                logging.info(f"[WEBSOCKET] Mensagem pendente enviada para {cliente_id}: {data}")
            except Exception as e:
                logging.error(f"[PENDENTES] Erro ao enviar pendente para {cliente_id}: {e}")
                # Opcional: reempilhar a mensagem
                break

    async def cleanup_inactive_connections(self):
        """
        Remove conexões que o Starlette já marcou como fechadas (client_state == 3).
        """
        disconnected_clients = [
            cid for cid, ws in self.active_connections.items()
            if ws.client_state == 3
        ]
        for cid in disconnected_clients:
            logging.info(f"[WEBSOCKET] Removendo cliente desconectado {cid}")
            self.active_connections.pop(cid, None)
            await self.redis_client.srem("active_clients", cid)

    async def send_keepalive(self):
        """
        Envia pings periódicos. Se falhar, faz 'disconnect', liberando o Redis.
        """
        for cliente_id, ws in list(self.active_connections.items()):
            try:
                await ws.send_text("ping")
                logging.debug(f"[KEEPALIVE] Ping enviado para cliente {cliente_id}")
            except Exception as e:
                logging.error(f"[KEEPALIVE] Erro ao enviar ping para {cliente_id}: {e}")
                await self.disconnect(cliente_id)

# -----------------------------------------------------------------------------
# Instância do FastAPI e Manager
# -----------------------------------------------------------------------------
app = FastAPI()
connection_manager = ConnectionManager(redis_client)

# -----------------------------------------------------------------------------
# Rota simples para ver clientes
# -----------------------------------------------------------------------------
@app.get("/connected_clients")
async def get_connected_clients():
    """Retorna a lista de clientes conectados (em qualquer worker)."""
    clients = await redis_client.smembers("active_clients")
    return {"connected_clients": list(clients)}

# -----------------------------------------------------------------------------
# WebSocket
# -----------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Recebe conexão WS, autentica e envia pendências."""
    await websocket.accept()
    try:
        init_message = await asyncio.wait_for(websocket.receive_text(), timeout=5)
    except asyncio.TimeoutError:
        await websocket.send_text("Erro: Nenhuma mensagem recebida em tempo hábil.")
        await websocket.close()
        return

    if not init_message:
        await websocket.send_text("Erro: Dados não fornecidos.")
        await websocket.close()
        return

    try:
        data = json.loads(init_message)
    except Exception:
        await websocket.send_text("Erro: JSON inválido.")
        await websocket.close()
        return

    if not data or not data.get("cliente_id") or not data.get("username") or not data.get("password"):
        await websocket.send_text("Erro: Dados de autenticação incompletos.")
        await websocket.close()
        return

    cliente_id = data["cliente_id"]
    username = data["username"]
    password = data["password"]

    if not isinstance(cliente_id, int):
        await websocket.send_text("Erro: Cliente ID inválido.")
        await websocket.close()
        return

    if not authenticate(username, password):
        await websocket.send_text("Erro: Credenciais inválidas.")
        await websocket.close()
        return

    # Conecta localmente e adiciona no 'active_clients'
    await connection_manager.connect(cliente_id, websocket)

    # Envia pendências, se houver
    await connection_manager.send_pending_messages(cliente_id, websocket)

    # Confirma
    await websocket.send_text(f"OK: Conexão autenticada no worker {MY_WORKER_ID}.")

    try:
        while True:
            await websocket.receive_text()  # Bloqueia esperando mensagens do cliente
    except WebSocketDisconnect:
        await connection_manager.disconnect(cliente_id)
        logging.warning(f"[WEBSOCKET] Cliente {cliente_id} desconectado do worker {MY_WORKER_ID}.")

# -----------------------------------------------------------------------------
# redis_listener: lê pubsub e despacha mensagens
# -----------------------------------------------------------------------------
async def redis_listener():
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(CHANNEL)
    logging.info(f"[REDIS] Worker {MY_WORKER_ID} assinou no canal Redis '{CHANNEL}'. Aguardando mensagens...")

    while True:
        try:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                cliente_id = data.get("cliente_id")

                if not isinstance(cliente_id, int):
                    logging.warning("[REDIS] Mensagem ignorada. Cliente ID ausente ou inválido.")
                    continue

                # Se este worker tem o cliente, envia
                if cliente_id in connection_manager.active_connections:
                    logging.info(f"[REDIS] Worker {MY_WORKER_ID} processará mensagem: {data}")
                    await connection_manager.send_message(cliente_id, data)
                else:
                    # Cliente não está neste worker
                    in_cluster = await redis_client.sismember("active_clients", cliente_id)
                    if not in_cluster:
                        # Offline => armazena
                        logging.info(f"[REDIS] Worker {MY_WORKER_ID}: {cliente_id} não está em active_clients. Armazenando pendente.")
                        await store_message_if_offline(cliente_id, data)
                    else:
                        # Conectado em outro worker
                        logging.debug(f"[REDIS] Mensagem para {cliente_id} ignorada por {MY_WORKER_ID}; cliente conectado em outro worker.")
        except Exception as e:
            logging.error(f"[REDIS] Erro ao processar mensagem no worker {MY_WORKER_ID}: {e}")
        await asyncio.sleep(0.1)

# -----------------------------------------------------------------------------
# Tarefas assíncronas extras
# -----------------------------------------------------------------------------
async def cleanup_inactive_connections_task():
    while True:
        await connection_manager.cleanup_inactive_connections()
        await asyncio.sleep(10)

async def keepalive_task():
    while True:
        await connection_manager.send_keepalive()
        await asyncio.sleep(300)  # Ajuste conforme necessidade

# -----------------------------------------------------------------------------
# Eventos de ciclo de vida
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    logging.info(f"[APP] Iniciando worker {MY_WORKER_ID}...")
    asyncio.create_task(redis_listener())
    asyncio.create_task(cleanup_inactive_connections_task())
    asyncio.create_task(keepalive_task())
    logging.info(f"[APP] Startup: Tarefas de listener, cleanup e keepalive inicializadas no worker {MY_WORKER_ID}.")

@app.on_event("shutdown")
async def on_shutdown():
    logging.info(f"[APP] Shutdown event: Worker {MY_WORKER_ID} finalizando.")