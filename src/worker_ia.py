import redis
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from sentence_transformers import SentenceTransformer
from PIL import Image
import uuid
import os

#connection à redis et qdrant ayant monté les volume dans docker
redis_client = redis.Redis(host='localhost', port=6379, db=0)
qdrant_client = QdrantClient(host='localhost', port=6333, timeout=60.0)
if "fashion_images" not in [c.name for c in qdrant_client.get_collections().collections]:
    qdrant_client.recreate_collection(
        collection_name="fashion_images",
        vectors_config={"size": 512, "distance": "Cosine"}
    )
#chargement du modèle de vision CLIP pour extrait les embedding
model_vision = SentenceTransformer('clip-ViT-B-32')

print('Extrateur de features chargé, en attente de tâches...')
while True:
    queue_name, image_path_bytes = redis_client.brpop('image_queue')
    image_path = image_path_bytes.decode('utf-8')
    image_path = os.path.normpath(os.path.join("..", image_path))
    if not os.path.exists(image_path):
        print(f"⚠️ Fichier introuvable : {image_path}, passage au suivant.")
        continue

    image = Image.open(image_path)
    
    vecteur = model_vision.encode(image).tolist()
    
    qdrant_client.upsert(
        collection_name="fashion_images",
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vecteur,
                payload={"image_path": image_path}
            )
        ]
    )   