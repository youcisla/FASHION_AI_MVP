import os
from PIL import Image
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
import uuid

# 1. Configuration
DATA_DIR = "../Data/catalog/"
COLLECTION_NAME = "fashion_images"

client = QdrantClient(host="localhost", port=6333, timeout=120)
model = SentenceTransformer('clip-ViT-B-32')

# 2. Vérifier si la collection existe
if COLLECTION_NAME not in [c.name for c in client.get_collections().collections]:
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=512, distance=Distance.COSINE)
    )

# 3. Récupération des images
images = [f for f in os.listdir(DATA_DIR) if f.lower().endswith(('.jpg', '.png'))]

print(f"Batch lancé : {len(images)} images détectées")

points = []

# 4. Encodage
for img_name in images:

    img_path = os.path.join(DATA_DIR, img_name)

    try:
        with Image.open(img_path) as img:
            vector = model.encode(img).tolist()

        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "filename": img_name,
                    "image_path": img_path
                }
            )
        )

        print(f"Encodée : {img_name}")

    except Exception as e:
        print(f"Erreur sur {img_name} : {e}")

# 5. Envoi batch vers Qdrant
client.upsert(
    collection_name=COLLECTION_NAME,
    points=points
)

print(f"Batch terminé : {len(points)} images indexées")