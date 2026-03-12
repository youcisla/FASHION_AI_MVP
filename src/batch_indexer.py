"""
batch_indexer.py — Index all catalog images into Qdrant.

Supports Qdrant Cloud (via QDRANT_URL / QDRANT_API_KEY env vars) or localhost.
Stores a base64 thumbnail in each payload so images display on Streamlit Cloud.

Usage:
    # Local Qdrant
    python batch_indexer.py

    # Qdrant Cloud (set env vars first, or use a .env file)
    set QDRANT_URL=https://...cloud.qdrant.io:6333
    set QDRANT_API_KEY=...
    python batch_indexer.py
"""
import os
import io
import base64
import uuid
from PIL import Image
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance

# ─── Configuration ────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "Data", "catalog")
COLLECTION_NAME = "fashion_images"
THUMB_MAX_WIDTH = 400  # px — keeps base64 payload <50 KB per image

# ─── .env support (optional) ─────────────────────────────────────────────────
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# ─── Qdrant client ───────────────────────────────────────────────────────────
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")

if qdrant_url:
    print(f"Connexion à Qdrant Cloud : {qdrant_url}")
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=120)
else:
    print("Connexion à Qdrant localhost:6333")
    client = QdrantClient(host="localhost", port=6333, timeout=120)

# ─── CLIP model ──────────────────────────────────────────────────────────────
model = SentenceTransformer("clip-ViT-B-32")

# ─── Collection ──────────────────────────────────────────────────────────────
existing = [c.name for c in client.get_collections().collections]
if COLLECTION_NAME not in existing:
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=512, distance=Distance.COSINE),
    )
    print(f"Collection '{COLLECTION_NAME}' créée.")
else:
    print(f"Collection '{COLLECTION_NAME}' existante.")


def make_thumbnail_b64(img: Image.Image) -> str:
    """Resize image to THUMB_MAX_WIDTH and return base64-encoded JPEG string."""
    ratio = THUMB_MAX_WIDTH / img.width
    new_size = (THUMB_MAX_WIDTH, int(img.height * ratio))
    thumb = img.resize(new_size, Image.LANCZOS)
    if thumb.mode in ("RGBA", "LA", "P"):
        thumb = thumb.convert("RGB")
    buf = io.BytesIO()
    thumb.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ─── Scan images ─────────────────────────────────────────────────────────────
images = [f for f in os.listdir(DATA_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
print(f"Batch lancé : {len(images)} images détectées")

points = []
BATCH_SIZE = 64

for idx, img_name in enumerate(images, 1):
    img_path = os.path.join(DATA_DIR, img_name)
    try:
        with Image.open(img_path) as img:
            img.load()
            vector = model.encode(img).tolist()
            thumb_b64 = make_thumbnail_b64(img)

        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "filename": img_name,
                    "image_path": img_path,
                    "thumb_b64": thumb_b64,
                },
            )
        )
        print(f"[{idx}/{len(images)}] ✓ {img_name}")

        # Flush in batches to avoid huge memory spikes
        if len(points) >= BATCH_SIZE:
            client.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"  → {len(points)} points envoyés")
            points = []

    except Exception as e:
        print(f"[{idx}/{len(images)}] ✗ {img_name} : {e}")

# Final flush
if points:
    client.upsert(collection_name=COLLECTION_NAME, points=points)

print(f"Batch terminé : {idx} images traitées")