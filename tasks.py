import redis
import json

# Defina o canal corretamente
CHANNEL = "canal_eventos"

def publish_event(cliente_id: int, action_params: str):
    """
    Publica uma mensagem no canal 'canal_eventos'.
    """
    try:
        # Criar conexão com Redis
        redis_client = redis.Redis.from_url("redis://redis:6379", decode_responses=True)
        
        # Criar mensagem
        message = {"cliente_id": cliente_id, "action_params": action_params}

        # Publicar no canal
        result = redis_client.publish(CHANNEL, json.dumps(message))
        
        # Debug para confirmar que foi publicado
        print(f"[DEBUG] Mensagem publicada no canal {CHANNEL}: {message}, Retorno do Redis: {result}")

    except Exception as e:
        print(f"[ERROR] Falha ao publicar no canal {CHANNEL}: {e}")
