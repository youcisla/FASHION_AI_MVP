import streamlit as st
from PIL import Image
from utile import init_tools, get_user_profile, hash_password, get_color_advice
from profile_ai import show_profile_sidebar
from search import show_search

# ---------------- INIT ----------------
model, client = init_tools()

# ---------------- SESSION ----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

# ---------------- LOGIN / SIGNUP ----------------
if not st.session_state.logged_in:

    st.title("🔐 Fashion AI - Accès")

    tab1, tab2 = st.tabs(["Connexion", "Inscription"])

    # -------- LOGIN --------
    with tab1:

        username_input = st.text_input("Nom d'utilisateur")
        password_input = st.text_input("Mot de passe", type="password")

        if st.button("Se connecter"):

            user_profile = get_user_profile(client, username_input)

            if user_profile and "password" in user_profile:

                if hash_password(password_input) == user_profile["password"]:

                    st.session_state.logged_in = True
                    st.session_state.username = username_input

                    st.success(f"Connexion réussie ! Bienvenue {username_input}")
                    st.rerun()

                else:
                    st.error("Mot de passe incorrect")

            else:
                st.error("Utilisateur non trouvé")

        if st.button("Mot de passe ou pseudo oublié ?"):
            st.info("Contactez l'administrateur pour réinitialiser votre compte.")

    # -------- SIGNUP --------
    with tab2:

        st.subheader("Créer mon compte et mon profil")

        show_profile_sidebar(
            client,
            model,
            username="",
            user_profile=None,
            require_password=True
        )

# ---------------- DASHBOARD ----------------
else:

    username = st.session_state.username
    user_profile = get_user_profile(client, username) or {}

    st.sidebar.title(f"👋 Bonjour {username}")

    # -------- IMAGE PROFIL --------
    profile_img_path = user_profile.get("profile_img_path")

    if profile_img_path:
        st.sidebar.image(profile_img_path, width=150)

    # -------- LOGOUT --------
    if st.sidebar.button("Déconnexion"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

    # -------- MODIFIER PROFIL --------
    with st.sidebar.expander("Modifier mon profil"):

        show_profile_sidebar(
            client,
            model,
            username,
            user_profile=user_profile,
            require_password=False
        )

    # ---------------- MENU ----------------
    mode = st.selectbox(
        "Fonctionnalité",
        ["Recherche", "Look Generator", "Analytics"]
    )

    # ---------------- RECHERCHE ----------------
    if mode == "Recherche":

        show_search(model, client)

    # ---------------- LOOK GENERATOR ----------------
    elif mode == "Look Generator":

        st.header("✨ Salon d'Essayage")

        teint = user_profile.get("teint", "Clair / Pâle")
        st.info(get_color_advice(teint))

        img = st.file_uploader(
            "Uploader une pièce ou utiliser votre photo",
            type=["png", "jpg", "jpeg"]
        )

        source_img = None

        if img:
            source_img = Image.open(img)

        elif profile_img_path:
            source_img = Image.open(profile_img_path)

        if source_img:

            vec = model.encode(source_img).tolist()

            res = client.query_points(
                collection_name="fashion_images",
                query=vec,
                limit=5
            ).points

            if res:

                st.image(res[0].payload["image_path"], width=200)

                st.write("Suggestions assorties :")

                cols = st.columns(min(4, len(res)-1))

                for i, h in enumerate(res[1:]):

                    cols[i].image(
                        h.payload["image_path"],
                        caption=f"{round(h.score,2)}"
                    )

    # ---------------- ANALYTICS ----------------
    elif mode == "Analytics":

        st.header("📊 Analyse Style")

        import pandas as pd
        import plotly.express as px
        from sklearn.decomposition import PCA

        pts = client.scroll(
            collection_name="fashion_images",
            with_vectors=True,
            limit=500
        )[0]

        if pts:

            vecs = [p.vector for p in pts]

            pca = PCA(n_components=2).fit_transform(vecs)

            df = pd.DataFrame(pca, columns=["x", "y"])

            fig = px.scatter(
                df,
                x="x",
                y="y",
                title="Distribution du catalogue"
            )

            st.plotly_chart(fig)

        else:

            st.warning("Pas assez de données pour l'analyse.")