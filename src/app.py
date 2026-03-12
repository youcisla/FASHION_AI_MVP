# app.py
import streamlit as st
import requests
import os
import io
import base64
from datetime import datetime

# ─── Load env vars: Streamlit Cloud secrets → os.environ ──────────────────────
try:
    for key in ("QDRANT_URL", "QDRANT_API_KEY", "AIRFLOW_BASE_URL", "AIRFLOW_USER", "AIRFLOW_PASSWORD"):
        if key in st.secrets:
            os.environ[key] = st.secrets[key]
except FileNotFoundError:
    pass

from utile import init_tools, get_user_profile, hash_password, verify_password, get_model, toggle_favorite, get_favorites, username_exists
from profile_ai import show_profile_sidebar

# ─── Airflow config ───────────────────────────────────────────────────────────
AIRFLOW_BASE_URL = os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080")
AIRFLOW_USER = os.getenv("AIRFLOW_USER", "admin")
AIRFLOW_PASSWORD = os.getenv("AIRFLOW_PASSWORD", "admin")
DAG_ID = "fashion_pipeline"

# ─── Page config (must be first st call) ──────────────────────────────────────
st.set_page_config(
    page_title="Fashion AI",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
    /* ─── Hide default Streamlit chrome ─── */
    #MainMenu, footer, header {visibility: hidden;}

    /* ─── Global ─── */
    .block-container {
        padding: 1.5rem 1.5rem 5rem 1.5rem !important;
        max-width: 900px !important;
        margin: 0 auto;
    }

    /* ─── Buttons ─── */
    .stButton > button, .stFormSubmitButton > button {
        width: 100%;
        min-height: 48px;
        font-size: 1rem;
        font-weight: 600;
        border-radius: 12px;
        transition: transform 0.1s, box-shadow 0.2s;
    }
    .stButton > button:active {
        transform: scale(0.97);
    }

    /* ─── Primary action button ─── */
    .stFormSubmitButton > button {
        background: linear-gradient(135deg, #FF4B6E, #FF8E53) !important;
        color: white !important;
        border: none !important;
    }

    /* ─── Inputs ─── */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        font-size: 1rem;
        min-height: 44px;
        border-radius: 10px;
    }
    .stSelectbox > div > div { min-height: 44px; }

    /* ─── Tabs ─── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        justify-content: center;
    }
    .stTabs [data-baseweb="tab"] {
        min-height: 48px;
        font-size: 1rem;
        font-weight: 600;
        padding: 0.6rem 2rem;
        border-radius: 12px 12px 0 0;
    }

    /* ─── Image cards ─── */
    [data-testid="stImage"] {
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
        transition: transform 0.2s;
    }
    [data-testid="stImage"]:hover {
        transform: translateY(-2px);
    }

    /* ─── Sidebar profile image ─── */
    [data-testid="stSidebar"] img {
        border-radius: 50%;
        max-width: 100px;
        margin: 0 auto;
        display: block;
        border: 3px solid #FF4B6E;
    }

    /* ─── Login page ─── */
    .login-header {
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .login-header h1 {
        font-size: 2.2rem;
        margin-bottom: 0.25rem;
    }
    .login-header p {
        color: #888;
        font-size: 1rem;
    }

    /* ─── Welcome banner ─── */
    .welcome-banner {
        background: linear-gradient(135deg, #FF4B6E 0%, #FF8E53 100%);
        color: white;
        padding: 1.2rem 1.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
    }
    .welcome-banner h2 {
        margin: 0;
        font-size: 1.3rem;
        color: white;
    }
    .welcome-banner p {
        margin: 0.2rem 0 0 0;
        opacity: 0.9;
        font-size: 0.9rem;
    }

    /* ─── Feature cards ─── */
    .feature-card {
        background: white;
        border: 1px solid #f0f0f0;
        border-radius: 16px;
        padding: 1.5rem;
        text-align: center;
        transition: transform 0.2s, box-shadow 0.2s;
        min-height: 140px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    .feature-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    .feature-card .icon { font-size: 2.2rem; margin-bottom: 0.5rem; }
    .feature-card .label { font-weight: 600; font-size: 1rem; color: #1a1a2e; }
    .feature-card .desc { font-size: 0.8rem; color: #888; margin-top: 0.3rem; }

    /* ─── Mobile ─── */
    @media (max-width: 640px) {
        .block-container {
            padding: 1rem 0.75rem 5rem 0.75rem !important;
        }
        [data-testid="column"] {
            width: 50% !important;
            flex: 0 0 50% !important;
            min-width: 0 !important;
        }
        h1 { font-size: 1.5rem !important; }
        h2 { font-size: 1.2rem !important; }
        .welcome-banner h2 { font-size: 1.1rem; }
        .feature-card { min-height: 110px; padding: 1rem; }
        .feature-card .icon { font-size: 1.8rem; }
    }
</style>
""", unsafe_allow_html=True)

# ─── Init ─────────────────────────────────────────────────────────────────────
model, client = init_tools()

# ─── Session state ────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
if "page" not in st.session_state:
    st.session_state.page = "home"
if "favorites" not in st.session_state:
    st.session_state.favorites = set()


def go_to(page):
    st.session_state.page = page


def display_image(payload, **kwargs):
    """Display an image from Qdrant payload: prefers base64 thumbnail, falls back to path."""
    b64 = payload.get("thumb_b64")
    if b64:
        st.image(f"data:image/jpeg;base64,{b64}", **kwargs)
    else:
        path = payload.get("path", payload.get("image_path", ""))
        if path:
            st.image(path, **kwargs)


# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN / SIGNUP
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:

    st.markdown("""
    <div class="login-header">
        <h1>👗 Fashion AI</h1>
        <p>Votre assistant mode intelligent</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["Connexion", "Créer un compte"])

    with tab_login:
        with st.form("login_form"):
            username_input = st.text_input("Nom d'utilisateur", placeholder="Entrez votre pseudo")
            password_input = st.text_input("Mot de passe", type="password", placeholder="••••••••")
            st.markdown("")  # spacer
            login_submitted = st.form_submit_button("Se connecter")

        if login_submitted:
            if not username_input or not password_input:
                st.warning("Veuillez remplir tous les champs.")
            else:
                user_profile = get_user_profile(client, username_input)
                if user_profile and "password" in user_profile:
                    if verify_password(password_input, user_profile["password"]):
                        st.session_state.logged_in = True
                        st.session_state.username = username_input
                        st.session_state.page = "home"
                        st.rerun()
                    else:
                        st.error("Mot de passe incorrect.")
                else:
                    st.error("Utilisateur non trouvé.")

    with tab_signup:
        show_profile_sidebar(client, model, username="", user_profile=None, require_password=True)

# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD (logged in)
# ══════════════════════════════════════════════════════════════════════════════
else:
    username = st.session_state.username
    user_profile = get_user_profile(client, username) or {}
    # Profile image: prefer base64, fallback to path
    profile_img_b64 = user_profile.get("profile_img_b64")
    profile_img_path = user_profile.get("profile_img_path")
    prenom = user_profile.get("prenom", username)

    # Load favorites into session
    if not st.session_state.favorites:
        st.session_state.favorites = set(get_favorites(client, username))

    # ──── Sidebar ─────────────────────────────────────────────────────────────
    with st.sidebar:
        if profile_img_b64:
            st.image(f"data:image/jpeg;base64,{profile_img_b64}", width=100)
        elif profile_img_path:
            st.image(profile_img_path, width=100)
        st.markdown(f"### {prenom}")
        st.caption(f"@{username}")
        st.divider()

        if st.button("🏠 Accueil", use_container_width=True):
            go_to("home")
            st.rerun()
        if st.button("🔍 Recherche", use_container_width=True):
            go_to("search")
            st.rerun()
        if st.button("✨ Look Generator", use_container_width=True):
            go_to("looks")
            st.rerun()
        if st.button("❤️ Favoris", use_container_width=True):
            go_to("favorites")
            st.rerun()
        if st.button("📊 Analytics", use_container_width=True):
            go_to("analytics")
            st.rerun()
        if st.button("⚙️ Pipeline", use_container_width=True):
            go_to("pipeline")
            st.rerun()

        st.divider()

        with st.expander("✏️ Modifier mon profil"):
            show_profile_sidebar(client, model, username, user_profile=user_profile, require_password=False)

        st.markdown("")
        if st.button("🚪 Déconnexion", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.page = "home"
            st.rerun()

    page = st.session_state.page

    # ══════════════════════════════════════════════════════════════════════════
    #  HOME
    # ══════════════════════════════════════════════════════════════════════════
    if page == "home":
        st.markdown(f"""
        <div class="welcome-banner">
            <div>
                <h2>Bonjour, {prenom} 👋</h2>
                <p>Que souhaitez-vous faire aujourd'hui ?</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ─── Profile completeness ─────────────────────────────────────────
        profile_fields = ["nom", "prenom", "age", "taille", "teint", "morpho"]
        has_img = bool(user_profile.get("profile_img_b64") or user_profile.get("profile_img_path"))
        filled = sum(1 for f in profile_fields if user_profile.get(f)) + (1 if has_img else 0)
        pct = int(filled / (len(profile_fields) + 1) * 100)
        if pct < 100:
            st.progress(pct / 100, text=f"Profil complété à {pct}%")
            st.caption("Complétez votre profil pour de meilleures recommandations.")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
            <div class="feature-card">
                <div class="icon">🔍</div>
                <div class="label">Recherche</div>
                <div class="desc">Trouvez des pièces par texte</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Ouvrir la recherche", key="nav_search"):
                go_to("search")
                st.rerun()

        with c2:
            st.markdown("""
            <div class="feature-card">
                <div class="icon">✨</div>
                <div class="label">Look Generator</div>
                <div class="desc">Créez des tenues assorties</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Créer un look", key="nav_looks"):
                go_to("looks")
                st.rerun()

        c3, c4 = st.columns(2)
        with c3:
            st.markdown("""
            <div class="feature-card">
                <div class="icon">❤️</div>
                <div class="label">Favoris</div>
                <div class="desc">Vos pièces sauvegardées</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Mes favoris", key="nav_favorites"):
                go_to("favorites")
                st.rerun()

        with c4:
            st.markdown("""
            <div class="feature-card">
                <div class="icon">📊</div>
                <div class="label">Analytics</div>
                <div class="desc">Analysez votre style</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Voir les stats", key="nav_analytics"):
                go_to("analytics")
                st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    #  SEARCH
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "search":
        if st.button("← Accueil", key="back_search"):
            go_to("home")
            st.rerun()
        st.markdown("## 🔍 Recherche Mode")

        # Quick filters
        categories = ["Robe", "Veste", "Pantalon", "Jupe", "Manteau", "T-shirt", "Chaussures"]
        filter_cols = st.columns(len(categories))
        selected_cat = ""
        for i, cat in enumerate(categories):
            if filter_cols[i].button(cat, key=f"cat_{cat}"):
                selected_cat = cat

        q = st.text_input(
            "Décrivez ce que vous cherchez",
            value=selected_cat,
            placeholder="Ex: robe rouge élégante, veste en cuir noire...",
            label_visibility="collapsed",
        )

        if q:
            with st.spinner("Recherche en cours..."):
                vec = model().encode(q).tolist()
                res = client.search(collection_name="fashion_images", query_vector=vec, limit=6)

            if res:
                st.caption(f"{len(res)} résultats pour « {q} »")
                cols = st.columns(2)
                for i, h in enumerate(res):
                    with cols[i % 2]:
                        display_image(h.payload, use_container_width=True)
                        point_id = str(h.id)
                        is_fav = point_id in st.session_state.favorites
                        label = "💔 Retirer" if is_fav else "❤️ Favoris"
                        if st.button(label, key=f"fav_s_{point_id}"):
                            toggle_favorite(client, username, point_id)
                            if is_fav:
                                st.session_state.favorites.discard(point_id)
                            else:
                                st.session_state.favorites.add(point_id)
                            st.rerun()
            else:
                st.info("Aucun résultat trouvé. Essayez d'autres mots-clés.")
        else:
            st.caption("Tapez un mot-clé pour lancer la recherche sémantique dans le catalogue.")

    # ══════════════════════════════════════════════════════════════════════════
    #  LOOK GENERATOR
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "looks":
        if st.button("← Accueil", key="back_looks"):
            go_to("home")
            st.rerun()
        st.markdown("## ✨ Salon d'Essayage")

        from utile import get_color_advice
        teint = user_profile.get("teint", "Clair / Pâle")
        st.info(f"💡 {get_color_advice(teint)}")

        img = st.file_uploader(
            "Uploader une pièce ou utiliser votre photo",
            type=["png", "jpg", "jpeg"],
            help="L'IA trouvera des pièces assorties",
        )
        source_img = img
        if not source_img and profile_img_b64:
            source_img = io.BytesIO(base64.b64decode(profile_img_b64))
        elif not source_img and profile_img_path:
            source_img = profile_img_path

        if source_img:
            with st.spinner("Génération du look..."):
                vec = model().encode(source_img).tolist()
                res = client.search(collection_name="fashion_images", query_vector=vec, limit=5)

            if res:
                st.markdown("**Pièce principale**")
                display_image(res[0].payload, use_container_width=True)

                st.markdown("**Suggestions assorties**")
                cols = st.columns(2)
                for i, h in enumerate(res[1:]):
                    with cols[i % 2]:
                        display_image(h.payload, use_container_width=True)
                        point_id = str(h.id)
                        is_fav = point_id in st.session_state.favorites
                        label = "💔 Retirer" if is_fav else "❤️ Favoris"
                        if st.button(label, key=f"fav_l_{point_id}"):
                            toggle_favorite(client, username, point_id)
                            if is_fav:
                                st.session_state.favorites.discard(point_id)
                            else:
                                st.session_state.favorites.add(point_id)
                            st.rerun()
        else:
            st.caption("Uploadez une image ou ajoutez une photo de profil pour commencer.")

    # ══════════════════════════════════════════════════════════════════════════
    #  FAVORITES
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "favorites":
        if st.button("← Accueil", key="back_favorites"):
            go_to("home")
            st.rerun()
        st.markdown("## ❤️ Mes Favoris")

        fav_ids = list(st.session_state.favorites)
        if fav_ids:
            try:
                fav_points = client.retrieve(collection_name="fashion_images", ids=fav_ids)
            except Exception:
                fav_points = []

            if fav_points:
                st.caption(f"{len(fav_points)} article(s) sauvegardé(s)")
                cols = st.columns(2)
                for i, pt in enumerate(fav_points):
                    with cols[i % 2]:
                        display_image(pt.payload, use_container_width=True)
                        if st.button("💔 Retirer", key=f"unfav_{pt.id}"):
                            toggle_favorite(client, username, str(pt.id))
                            st.session_state.favorites.discard(str(pt.id))
                            st.rerun()
            else:
                st.info("Vos favoris n'ont pas pu être chargés.")
        else:
            st.info("Vous n'avez pas encore de favoris. Explorez le catalogue et sauvegardez des pièces !")

    # ══════════════════════════════════════════════════════════════════════════
    #  ANALYTICS
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "analytics":
        if st.button("← Accueil", key="back_analytics"):
            go_to("home")
            st.rerun()
        st.markdown("## 📊 Analyse du Catalogue")

        import pandas as pd
        import plotly.express as px
        from sklearn.decomposition import PCA
        from sklearn.cluster import KMeans

        with st.spinner("Chargement des données..."):
            pts = client.scroll(collection_name="fashion_images", with_vectors=True)[0]

        if pts:
            # ─── Key metrics row ──────────────────────────────────────────
            m1, m2, m3 = st.columns(3)
            m1.metric("📦 Articles", len(pts))
            m2.metric("❤️ Favoris", len(st.session_state.favorites))
            profile_fields = ["nom", "prenom", "age", "taille", "teint", "morpho"]
            has_img = bool(user_profile.get("profile_img_b64") or user_profile.get("profile_img_path"))
            pct = int((sum(1 for f in profile_fields if user_profile.get(f)) + (1 if has_img else 0)) / (len(profile_fields) + 1) * 100)
            m3.metric("👤 Profil", f"{pct}%")

            st.divider()

            # ─── PCA scatter with clusters ────────────────────────────────
            vecs = [p.vector for p in pts]
            n_clusters = min(5, len(pts))
            pca = PCA(n_components=2).fit_transform(vecs)
            clusters = KMeans(n_clusters=n_clusters, n_init=10, random_state=42).fit_predict(vecs)
            df = pd.DataFrame(pca, columns=["x", "y"])
            df["cluster"] = [f"Groupe {c+1}" for c in clusters]

            fig = px.scatter(
                df, x="x", y="y", color="cluster",
                title="Distribution du catalogue (PCA + Clusters)",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig.update_layout(
                margin=dict(l=10, r=10, t=40, b=10),
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=False),
                legend_title_text="",
            )
            fig.update_traces(marker=dict(size=8, opacity=0.7))
            st.plotly_chart(fig, use_container_width=True)

            # ─── Style summary ────────────────────────────────────────────
            st.divider()
            st.markdown("### 👤 Votre profil style")
            from utile import get_color_advice
            teint = user_profile.get("teint", "Clair / Pâle")
            morpho = user_profile.get("morpho", "A")
            st.markdown(f"**Morphologie :** {morpho} &emsp; **Teint :** {teint}")
            st.info(f"💡 {get_color_advice(teint)}")
        else:
            st.info("Le catalogue est vide. Lancez le pipeline pour indexer des images.")

    # ══════════════════════════════════════════════════════════════════════════
    #  PIPELINE ADMIN
    # ══════════════════════════════════════════════════════════════════════════
    elif page == "pipeline":
        if st.button("← Accueil", key="back_pipeline"):
            go_to("home")
            st.rerun()
        st.markdown("## ⚙️ Pipeline Airflow")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("▶️ Lancer le pipeline", use_container_width=True):
                run_id = f"manual__{datetime.utcnow().isoformat()}"
                try:
                    response = requests.post(
                        f"{AIRFLOW_BASE_URL}/api/v1/dags/{DAG_ID}/dagRuns",
                        json={"dag_run_id": run_id},
                        auth=(AIRFLOW_USER, AIRFLOW_PASSWORD),
                        timeout=10,
                    )
                    if response.status_code == 200:
                        st.success("Pipeline lancé !")
                    else:
                        st.error(f"Erreur : {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("Airflow non joignable.")

        with col2:
            if st.button("🔄 Rafraîchir le statut", use_container_width=True):
                try:
                    response = requests.get(
                        f"{AIRFLOW_BASE_URL}/api/v1/dags/{DAG_ID}/dagRuns"
                        "?limit=1&order_by=-execution_date",
                        auth=(AIRFLOW_USER, AIRFLOW_PASSWORD),
                        timeout=10,
                    )
                    if response.status_code == 200:
                        runs = response.json().get("dag_runs", [])
                        if runs:
                            last = runs[0]
                            state = last["state"]
                            icon = "🟢" if state == "success" else "🔴" if state == "failed" else "🟡"
                            st.info(f"{icon} Dernier run : **{state}**")
                        else:
                            st.info("Aucun run trouvé.")
                    else:
                        st.error(f"Erreur : {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("Airflow non joignable.")

        st.markdown("---")
        st.markdown("**Historique récent**")

        try:
            response = requests.get(
                f"{AIRFLOW_BASE_URL}/api/v1/dags/{DAG_ID}/dagRuns"
                "?limit=5&order_by=-execution_date",
                auth=(AIRFLOW_USER, AIRFLOW_PASSWORD),
                timeout=10,
            )
            if response.status_code == 200:
                runs = response.json().get("dag_runs", [])
                if runs:
                    for run in runs:
                        state = run["state"]
                        icon = "🟢" if state == "success" else "🔴" if state == "failed" else "🟡"
                        rid = run["dag_run_id"]
                        date = run["start_date"] or "—"
                        st.markdown(f"{icon} &ensp; **{state}** &ensp; `{rid}` &ensp; {date}")
                else:
                    st.caption("Aucun run dans l'historique.")
            else:
                st.caption("Impossible de charger l'historique.")
        except requests.exceptions.ConnectionError:
            st.warning("Airflow non disponible — historique indisponible.")
