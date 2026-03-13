# utile.py
import hashlib
import os
import io
import base64
import secrets
from PIL import Image
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import streamlit as st


# ---------------- SECRETS HELPER ----------------
def _get_secret(key: str, default: str = "") -> str:
    """Read from st.secrets (Streamlit Cloud) then fall back to os.environ."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.environ.get(key, default)


# ---------------- CACHED QDRANT CLIENT ----------------
@st.cache_resource
def get_qdrant_client():
    """Qdrant client — created once, shared across sessions."""
    qdrant_url = _get_secret("QDRANT_URL")
    qdrant_api_key = _get_secret("QDRANT_API_KEY")

    if qdrant_url:
        client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key if qdrant_api_key else None,
            timeout=30,
            prefer_grpc=False,
        )
    else:
        client = QdrantClient(host="localhost", port=6333, timeout=30)

    # Auto-create collections if absent
    try:
        collections = [c.name for c in client.get_collections().collections]
        if "user_profiles" not in collections:
            client.create_collection(
                collection_name="user_profiles",
                vectors_config=VectorParams(size=512, distance=Distance.COSINE),
            )
        if "fashion_images" not in collections:
            client.create_collection(
                collection_name="fashion_images",
                vectors_config=VectorParams(size=512, distance=Distance.COSINE),
            )
    except Exception as e:
        st.warning(f"Qdrant collection check failed: {e}")

    return client


# ---------------- CACHED CLIP MODEL ----------------
@st.cache_resource
def get_model():
    """CLIP model — loaded once on first use, shared across sessions."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("clip-ViT-B-32")


# ---------------- INIT TOOLS ----------------
def init_tools():
    """Returns (model, client). Both are cached — fast on reload."""
    return get_model(), get_qdrant_client()

# ---------------- HASH PASSWORD (PBKDF2) ----------------
def hash_password(password: str, salt: str | None = None) -> str:
    """Hash password with PBKDF2-HMAC-SHA256. Returns salt:hash."""
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations=100_000)
    return f"{salt}:{h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify password against stored salt:hash. Also accepts legacy SHA-256."""
    if ":" in stored:
        salt = stored.split(":")[0]
        return hash_password(password, salt) == stored
    # Legacy: plain SHA-256 (for existing accounts)
    return hashlib.sha256(password.encode()).hexdigest() == stored

# ---------------- USER ID STABLE ----------------
def generate_user_id(username: str) -> int:
    """Génère un ID stable pour Qdrant à partir du pseudo."""
    return int(hashlib.sha256(username.encode()).hexdigest(), 16) % (10**12)

# ---------------- SAVE PROFILE IMAGE (base64) ----------------
def save_profile_image(uploaded_file, username):
    """
    Encode uploaded image as base64 JPEG thumbnail for Qdrant storage.
    Returns base64 string (no local file needed).
    """
    if uploaded_file is None:
        return None
    try:
        image = Image.open(uploaded_file)
        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGB")
        # Resize to max 200px wide for profile thumbnails
        ratio = 200 / image.width
        image = image.resize((200, int(image.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        print("        ", e)
        return None

# ---------------- SAVE / UPDATE USER ----------------
def save_profile_to_qdrant(client, model, username: str, user_data: dict, password: str | None = None):
    """
    Sauvegarde ou met à jour le profil utilisateur dans Qdrant.
    - Si password est fourni, il sera hashé et ajouté.
    """
    user_id = generate_user_id(username)

    # Gestion de l'image — store as base64
    profile_img = user_data.get("profile_img_file")
    if profile_img:
        b64 = save_profile_image(profile_img, username)
        if b64:
            user_data["profile_img_b64"] = b64
        user_data.pop("profile_img_file", None)
        user_data.pop("profile_img_path", None)

    # Hash du mot de passe si présent
    if password:
        user_data["password"] = hash_password(password)

    # Embedding texte pour Qdrant
    profile_text = f"""
    {user_data.get('teint','')}
    {user_data.get('morpho','')}
    {user_data.get('age','')}
    {user_data.get('taille','')}
    """
    # Resolve model if it's a lazy loader
    if callable(model) and not hasattr(model, 'encode'):
        model = model()
    vec = model.encode(profile_text).tolist()

    # Upsert dans Qdrant
    client.upsert(
        collection_name="user_profiles",
        points=[
            PointStruct(
                id=user_id,
                vector=vec,
                payload=user_data
            )
        ]
    )

# ---------------- GET USER PROFILE ----------------
def get_user_profile(client, username: str) -> dict | None:
    """Récupère le profil utilisateur depuis Qdrant."""
    user_id = generate_user_id(username)
    try:
        res = client.retrieve(
            collection_name="user_profiles",
            ids=[user_id]
        )
        if res:
            return res[0].payload
        return None
    except Exception as e:
        print("Erreur Qdrant:", e)
        return None


# ---------------- COLOR ADVICE ----------------
def get_color_advice(teint: str) -> str:
    """Donne des conseils de couleurs en fonction du teint."""
    if teint == "Clair / Pâle":
        return "Couleurs recommandées : bleu marine, vert émeraude, rose poudré."
    if teint == "Intermédiaire / Mat":
        return "Couleurs recommandées : beige, olive, rouge profond."
    if teint == "Foncé / Noir":
        return "Couleurs recommandées : jaune vif, blanc, violet."
    return ""


# ---------------- USERNAME EXISTS CHECK ----------------
def username_exists(client, username: str) -> bool:
    """Check if a username is already registered."""
    user_id = generate_user_id(username)
    try:
        res = client.retrieve(collection_name="user_profiles", ids=[user_id])
        return len(res) > 0
    except Exception:
        return False


# ---------------- FAVORITES ----------------
def get_favorites(client, username: str) -> list[str]:
    """Return list of favorite point IDs for a user."""
    profile = get_user_profile(client, username)
    if profile and "favorites" in profile:
        return profile["favorites"]
    return []


def toggle_favorite(client, username: str, point_id: str):
    """Add or remove a point ID from the user's favorites list."""
    user_id = generate_user_id(username)
    profile = get_user_profile(client, username) or {}
    favs = profile.get("favorites", [])

    if point_id in favs:
        favs.remove(point_id)
    else:
        favs.append(point_id)

    # Update only the favorites field
    client.set_payload(
        collection_name="user_profiles",
        payload={"favorites": favs},
        points=[user_id],
    )


# ---------------- DISPLAY IMAGE HELPER ────────────────────────────────────────
def display_image(payload, **kwargs):
    """Display an image from Qdrant payload: prefers base64 thumbnail, falls back to path."""
    b64 = payload.get("thumb_b64")
    if b64:
        st.image(f"data:image/jpeg;base64,{b64}", **kwargs)
    else:
        path = payload.get("path", payload.get("image_path", ""))
        if path:
            st.image(path, **kwargs)