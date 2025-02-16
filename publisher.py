import redis
import json

# Conectar ao Redis
redis_client = redis.Redis(host="localhost", port=6379, decode_responses=False)

def publish_event(cliente_id, action_params):
    """Publica um evento no canal Redis."""
    event = {
        "cliente_id": cliente_id,
        "action_params": action_params
    }

    message = json.dumps(event)  # Converte para JSON antes de publicar
    redis_client.publish("canal_eventos", message)
    print(f"[PUBLISHER] Mensagem enviada: {event}")

# Teste de publicação
if __name__ == "__main__":
    cliente_id = 9001  # Cliente que deve receber a mensagem
    action_params = "GetBooks&companyid=9000&startdate=2022-08-11&enddate=2022-08-13"

    publish_event(cliente_id, action_params)
