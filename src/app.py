# app.py
import streamlit as st
import requests
import os
from datetime import datetime
from utile import init_tools, get_user_profile, hash_password
from profile_ai import show_profile_sidebar

# ─── Airflow config ───────────────────────────────────────────────────────────
AIRFLOW_BASE_URL = os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080")
AIRFLOW_USER = os.getenv("AIRFLOW_USER", "admin")
AIRFLOW_PASSWORD = os.getenv("AIRFLOW_PASSWORD", "admin")
DAG_ID = "fashion_pipeline"

# ---------------- INIT ----------------
model, client = init_tools()

# ---------------- SESSION ----------------
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

# ---------------- LOGIN / SIGNUP ----------------
if not st.session_state.logged_in:

    st.title("🔐 Fashion AI - Accès")
    tab1, tab2 = st.tabs(["Connexion", "Inscription"])

    # -------- LOGIN --------
    with tab1:
        username = st.text_input("Nom d'utilisateur")
        password = st.text_input("Mot de passe", type="password")

        if st.button("Se connecter"):
            user_profile = get_user_profile(client, username)
            if user_profile and 'password_hash' in user_profile:
                if hash_password(password) == user_profile['password_hash']:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.success(f"Connexion réussie ! Bienvenue {username}")
                    st.experimental_rerun()
                else:
                    st.error("Mot de passe incorrect")
            else:
                st.error("Utilisateur non trouvé")

    # -------- SIGNUP --------
    with tab2:
        st.subheader("Créer mon compte et mon profil")
        show_profile_sidebar(client, model, username="", user_profile=None, require_password=True)

# ---------------- DASHBOARD ----------------
else:
    username = st.session_state.username
    user_profile = get_user_profile(client, username)

    st.sidebar.title(f"👋 Bonjour {username}")

    # -------- IMAGE PROFIL --------
    if user_profile and "profile_img_path" in user_profile:
        st.sidebar.image(user_profile["profile_img_path"], width=150)

    # -------- LOGOUT --------
    if st.sidebar.button("Déconnexion"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.experimental_rerun()

    # -------- MODIFIER PROFIL --------
    with st.sidebar.expander("Modifier mon profil"):
        show_profile_sidebar(client, model, username, user_profile=user_profile, require_password=False)

    # ---------------- DASHBOARD ----------------
    mode = st.selectbox(
        "Fonctionnalité",
        ["Recherche", "Look Generator", "Analytics", "Pipeline Admin"]
    )

    # ---------------- RECHERCHE ----------------
    if mode == "Recherche":
        q = st.text_input("Recherche texte")
        if q:
            vec = model.encode(q).tolist()
            res = client.search(collection_name="fashion_images", query_vector=vec, limit=4)
            cols = st.columns(4)
            for i, h in enumerate(res):
                cols[i].image(h.payload["path"])

    # ---------------- LOOK GENERATOR ----------------
    elif mode == "Look Generator":
        st.header("✨ Salon d'Essayage")
        from utile import get_color_advice

        teint = user_profile.get("teint", "Clair / Pâle")
        st.info(get_color_advice(teint))

        img = st.file_uploader("Uploader une pièce ou utiliser votre photo", type=["png", "jpg", "jpeg"])
        source_img = img if img else user_profile.get("profile_img_path")

        if source_img:
            vec = model.encode(source_img).tolist()
            res = client.search(collection_name="fashion_items", query_vector=vec, limit=5)
            st.image(res[0].payload["path"], width=200)
            st.write("Suggestions assorties :")
            cols = st.columns(4)
            for i, h in enumerate(res[1:]):
                cols[i].image(h.payload["path"])

    # ---------------- ANALYTICS ----------------
    elif mode == "Analytics":
        st.header("📊 Analyse Style")
        import pandas as pd
        import plotly.express as px
        from sklearn.decomposition import PCA

        pts = client.scroll(collection_name="fashion_items", with_vectors=True)[0]
        vecs = [p.vector for p in pts]
        pca = PCA(n_components=2).fit_transform(vecs)
        df = pd.DataFrame(pca, columns=["x", "y"])
        fig = px.scatter(df, x="x", y="y", title="Distribution du catalogue")
        st.plotly_chart(fig)

    # ---------------- PIPELINE ADMIN ----------------
    elif mode == "Pipeline Admin":
        st.header("⚙️ Gestion du Pipeline Airflow")

        col1, col2 = st.columns(2)

        # Trigger DAG manually
        with col1:
            if st.button("▶️ Lancer le pipeline maintenant"):
                run_id = f"manual__{datetime.utcnow().isoformat()}"
                try:
                    response = requests.post(
                        f"{AIRFLOW_BASE_URL}/api/v1/dags/{DAG_ID}/dagRuns",
                        json={"dag_run_id": run_id},
                        auth=(AIRFLOW_USER, AIRFLOW_PASSWORD),
                        timeout=10,
                    )
                    if response.status_code == 200:
                        st.success(f"Pipeline lancé ! Run ID: {run_id}")
                    else:
                        st.error(f"Erreur : {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("Impossible de contacter Airflow. Vérifiez que le service est démarré.")

        # Get last DAG run status
        with col2:
            if st.button("🔄 Statut du dernier run"):
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
                            st.json({
                                "state": last["state"],
                                "run_id": last["dag_run_id"],
                                "start_date": last["start_date"],
                                "end_date": last["end_date"],
                            })
                        else:
                            st.info("Aucun run trouvé.")
                    else:
                        st.error(f"Erreur : {response.text}")
                except requests.exceptions.ConnectionError:
                    st.error("Impossible de contacter Airflow. Vérifiez que le service est démarré.")

        # Run history
        st.subheader("📋 Historique des runs")
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
                        color = (
                            "🟢" if run["state"] == "success"
                            else "🔴" if run["state"] == "failed"
                            else "🟡"
                        )
                        st.write(
                            f"{color} `{run['dag_run_id']}` — "
                            f"{run['state']} — {run['start_date']}"
                        )
                else:
                    st.info("Aucun run dans l'historique.")
        except requests.exceptions.ConnectionError:
            st.warning("Airflow non disponible — historique indisponible.")