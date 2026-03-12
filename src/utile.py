# utile.py
import hashlib
import os
from PIL import Image
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

# ---------------- INIT TOOLS ----------------
def init_tools():
    """Initialisation du modèle et du client Qdrant."""
    model = SentenceTransformer("clip-ViT-B-32")

    client = QdrantClient(
        host="localhost",
        port=6333,
        timeout=120
    )

    # création collection profils si absente
    collections = [c.name for c in client.get_collections().collections]
    if "user_profiles" not in collections:
        client.create_collection(
            collection_name="user_profiles",
            vectors_config=VectorParams(
                size=512,
                distance=Distance.COSINE
            )
        )

    return model, client

# ---------------- HASH PASSWORD ----------------
def hash_password(password: str) -> str:
    """Retourne le hash SHA256 du mot de passe."""
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------- USER ID STABLE ----------------
def generate_user_id(username: str) -> int:
    """Génère un ID stable pour Qdrant à partir du pseudo."""
    return int(hashlib.sha256(username.encode()).hexdigest(), 16) % (10**12)

# ---------------- SAVE PROFILE IMAGE ----------------
def save_profile_image(uploaded_file, username):
    """
    Sauvegarde l'image uploadée avec le bon format.
    Convertit PNG en JPG si nécessaire.
    """
    if uploaded_file is None:
        return None

    os.makedirs("profile_images", exist_ok=True)

    # Nom de base
    filename_base = f"profile_images/{username}"

    try:
        image = Image.open(uploaded_file)

        # Si l'image est PNG avec transparence, convertit en RGB
        if image.mode in ("RGBA", "LA"):
            image = image.convert("RGB")

        # On force l'extension en .jpg pour uniformité
        path = f"{filename_base}.jpg"
        image.save(path, format="JPEG")

        return path

    except Exception as e:
        print("         ", e)
        return None                 

# ---------------- SAVE / UPDATE USER ----------------
def save_profile_to_qdrant(client, model, username: str, user_data: dict, password: str | None = None):
    """
    Sauvegarde ou met à jour le profil utilisateur dans Qdrant.
    - Si password est fourni, il sera hashé et ajouté.
    """
    user_id = generate_user_id(username)

    # Gestion de l'image
    profile_img = user_data.get("profile_img_file")
    if profile_img:
        img_path = save_profile_image(profile_img, username)
        user_data["profile_img_path"] = img_path
        del user_data["profile_img_file"]

    # Hash du mot de passe si présent
    if password:
        user_data["password_hash"] = hash_password(password)

    # Embedding texte pour Qdrant
    profile_text = f"""
    {user_data.get('teint','')}
    {user_data.get('morpho','')}
    {user_data.get('age','')}
    {user_data.get('taille','')}
    """
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