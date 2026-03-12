import redis

# Connexion à Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Simuler l'arrivée d'une image
image_path = "Data/catalog/1af5219860d3f6d462bf4f268382b0ff.jpg" # Mets le chemin réel d'une image
redis_client.lpush('image_queue', image_path)
