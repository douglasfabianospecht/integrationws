import asyncio
import websockets
import json

CLIENTE_ID = 9001  # Defina um ID único para o cliente
WEBSOCKET_URL = "ws://localhost:9000/ws"
USERNAME = "user"
PASSWORD = "user123"

async def connect():
    """Conecta ao WebSocket e gerencia reconexões."""
    while True:
        try:
            async with websockets.connect(WEBSOCKET_URL) as websocket:
                print(f"Cliente {CLIENTE_ID} conectado ao WebSocket!")
                
                # Envia o ID do cliente e as credenciais ao conectar
                auth_data = {
                    "cliente_id": CLIENTE_ID,
                    "username": USERNAME,
                    "password": PASSWORD
                }
                await websocket.send(json.dumps(auth_data))
                
                while True:
                    message = await websocket.recv()
                    print(f"Mensagem recebida: {message}")
                    
        except (websockets.exceptions.ConnectionClosedError, ConnectionRefusedError):
            print("Conexão perdida ou recusada. Tentando reconectar em 5 segundos...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(connect())
