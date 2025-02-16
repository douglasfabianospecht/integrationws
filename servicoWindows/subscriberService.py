import asyncio
import websockets
import json
import os
import requests
import servicemanager
import socket
import sys
import win32event
import win32service
import win32serviceutil
import threading
import traceback
from dotenv import load_dotenv
import logging

# Garante que o .env seja carregado externamente
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path)

# Configura o nível de log a partir do .env (default DEBUG)
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
numeric_level = getattr(logging, LOG_LEVEL, None)
if not isinstance(numeric_level, int):
    raise ValueError("Nível de log inválido: %s" % LOG_LEVEL)
logging.basicConfig(level=numeric_level, format="%(asctime)s - %(levelname)s - %(message)s")

CLIENTE_ID = int(os.getenv("CLIENTE_ID", "9999"))
API_URL = os.getenv("API_URL", "http://127.0.0.1:18690")
#URL da chamada para a API do DesbravadorConnect
API_BASE_URL = f"{API_URL}/DSLPlugin/Executar?action="
AUTH_URL = f"{API_URL}/DSLPlugin/Auth"
# Usuário para autenticação no DesbravadorConnect Server
AUTH_USER = os.getenv("AUTH_USER", "userapi")
AUTH_PASS = os.getenv("AUTH_PASS", "userapi123")
# Usuário para autenticação no WebSocket Server
AUTH_USER_WS = os.getenv("AUTH_USER", "user")
AUTH_PASS_WS = os.getenv("AUTH_PASS", "user123")
#URL da chamada para o WebSocket Server
WEBSOCKET_URL = os.getenv("WEBSOCKET_URL", "ws://localhost:9000/ws")
TOKEN = None

class SubscriberService(win32serviceutil.ServiceFramework):
    _svc_name_ = "Client_Windows_WebSocket"
    _svc_display_name_ = "Client WebSocket Subscriber Service"
    _svc_description_ = "Serviço para conectar ao WebSocket e processar Integrações."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.stop_event = threading.Event()
        self.loop = asyncio.new_event_loop()
        self.websocket = None

    def log_message(self, message):
        log_path = os.path.join(BASE_DIR, "SubscriberService.log")
        try:
            with open(log_path, "a", encoding="utf-8") as log:
                log.write(message + "\n")
        except Exception as e:
            servicemanager.LogErrorMsg(f"Erro ao escrever no log: {str(e)}")

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.stop_event.set()
        win32event.SetEvent(self.hWaitStop)
        if self.websocket:
            self.loop.run_until_complete(self.websocket.close())
        self.loop.stop()
        self.log_message("[SERVIÇO] Parando o serviço...")

    def SvcDoRun(self):
        self.log_message("[SERVIÇO] Iniciando WebSocket Subscriber...")
        try:
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(connect(self.stop_event))
        except Exception as e:
            self.log_message(f"[ERRO] Falha ao iniciar o serviço: {str(e)}\n{traceback.format_exc()}")
            servicemanager.LogErrorMsg(f"[ERRO] {str(e)}")

async def authenticate():
    global TOKEN
    while True:
        try:
            headers = {"Content-Type": "application/json"}
            payload = {"user": AUTH_USER, "pass": AUTH_PASS}
            response = requests.post(AUTH_URL, json=payload, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            TOKEN = data.get("token")
            if TOKEN:
                return TOKEN
        except requests.exceptions.RequestException as e:
            with open(os.path.join(BASE_DIR, "SubscriberService.log"), "a", encoding="utf-8") as log:
                log.write(f"[ERRO] Autenticação falhou: {e}\n")
            await asyncio.sleep(5)

async def send_http_request(action_params):
    global TOKEN
    TOKEN = await authenticate()
    url = API_BASE_URL + action_params
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    try:
        with open(os.path.join(BASE_DIR, "SubscriberService.log"), "a", encoding="utf-8") as log:
            log.write(f"[HTTP] Enviando requisição para {url}\n")
        response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=5)
        response.raise_for_status()
        with open(os.path.join(BASE_DIR, "SubscriberService.log"), "a", encoding="utf-8") as log:
            log.write(f"[HTTP] Resposta recebida: {response.status_code} - {response.text}\n")
    except requests.exceptions.RequestException as e:
        with open(os.path.join(BASE_DIR, "SubscriberService.log"), "a", encoding="utf-8") as log:
            log.write(f"[ERRO] Erro ao enviar requisição HTTP: {e}\n")

async def connect(stop_event):
    global websocket
    while not stop_event.is_set():
        try:
            with open(os.path.join(BASE_DIR, "SubscriberService.log"), "a", encoding="utf-8") as log:
                log.write("[WEBSOCKET] Tentando conectar ao WebSocket...\n")
            websocket = await websockets.connect(WEBSOCKET_URL)
            with open(os.path.join(BASE_DIR, "SubscriberService.log"), "a", encoding="utf-8") as log:
                log.write(f"[WEBSOCKET] Conectado! Enviando ID {CLIENTE_ID} com autenticação\n")
            # Envia o ID do cliente junto com as credenciais para autenticação no WebSocket
            await websocket.send(json.dumps({
                "cliente_id": CLIENTE_ID,
                "username": AUTH_USER_WS,
                "password": AUTH_PASS_WS
            }))
            while not stop_event.is_set():
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1)
                    with open(os.path.join(BASE_DIR, "SubscriberService.log"), "a", encoding="utf-8") as log:
                        log.write(f"[WEBSOCKET] Mensagem recebida: {message}\n")
                    data = json.loads(message)
                    action_params = data.get("action_params")
                    if action_params:
                        with open(os.path.join(BASE_DIR, "SubscriberService.log"), "a", encoding="utf-8") as log:
                            log.write(f"[PROCESSO] Enviando requisição com params: {action_params}\n")
                        await send_http_request(action_params)
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    with open(os.path.join(BASE_DIR, "SubscriberService.log"), "a", encoding="utf-8") as log:
                        log.write("[WEBSOCKET] Conexão fechada. Tentando reconectar em 5s...\n")
                    await asyncio.sleep(5)
                    break
        except Exception as e:
            with open(os.path.join(BASE_DIR, "SubscriberService.log"), "a", encoding="utf-8") as log:
                log.write(f"[ERRO] WebSocket erro: {e}\n")
            await asyncio.sleep(5)

if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(SubscriberService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(SubscriberService)
