import os
import io
import base64
import redis
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from sentence_transformers import SentenceTransformer
from PIL import Image
import uuid

# ─── .env support ─────────────────────────────────────────────────────────────
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# ─── Connections ──────────────────────────────────────────────────────────────
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)

qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")
if qdrant_url:
    qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=120)
else:
    qdrant_client = QdrantClient(host="localhost", port=6333, timeout=60)

# Auto-create collection if absent
collections = [c.name for c in qdrant_client.get_collections().collections]
if "fashion_images" not in collections:
    qdrant_client.create_collection(
        collection_name="fashion_images",
        vectors_config=VectorParams(size=512, distance=Distance.COSINE),
    )

THUMB_MAX_WIDTH = 400

# ─── CLIP model ───────────────────────────────────────────────────────────────
model_vision = SentenceTransformer('clip-ViT-B-32')

print('Extracteur de features charge, en attente de taches...')
while True:
    queue_name, image_path_bytes = redis_client.brpop('image_queue')
    image_path = image_path_bytes.decode('utf-8')
    image_path = os.path.normpath(os.path.join("..", image_path))
    if not os.path.exists(image_path):
        print(f"Fichier introuvable : {image_path}, passage au suivant.")
        continue

    try:
        with Image.open(image_path) as image:
            image.load()
            vecteur = model_vision.encode(image).tolist()

            # Generate base64 thumbnail
            ratio = THUMB_MAX_WIDTH / image.width
            thumb = image.resize((THUMB_MAX_WIDTH, int(image.height * ratio)), Image.LANCZOS)
            if thumb.mode in ("RGBA", "LA", "P"):
                thumb = thumb.convert("RGB")
            buf = io.BytesIO()
            thumb.save(buf, format="JPEG", quality=80)
            thumb_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        qdrant_client.upsert(
            collection_name="fashion_images",
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vecteur,
                    payload={
                        "filename": os.path.basename(image_path),
                        "image_path": image_path,
                        "thumb_b64": thumb_b64,
                    }
                )
            ]
        )
        print(f"Indexe : {image_path}")
    except Exception as e:
        print(f"Erreur pour {image_path} : {e}")