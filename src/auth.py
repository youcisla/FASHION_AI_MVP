import streamlit as st
from utile import save_profile_to_qdrant, get_user_profile, hash_password


def show_auth(client, model):

    st.title("🔐 Fashion AI - Accès")

    tab1, tab2 = st.tabs(["Connexion", "Inscription"])


# ---------------- LOGIN ----------------

    with tab1:

        username = st.text_input("Pseudo")

        password = st.text_input(
            "Mot de passe",
            type="password"
        )

        if st.button("Se connecter"):

            profile = get_user_profile(client, username)

            if profile is None:

                st.error("Utilisateur introuvable")

            else:

                stored_pw = profile.get("password")

                if stored_pw == hash_password(password):

                    st.session_state.logged_in = True
                    st.session_state.username = username

                    st.success("Connexion réussie")

                    st.rerun()

                else:

                    st.error("Mot de passe incorrect")


# ---------------- SIGNUP ----------------

    with tab2:

        st.subheader("Créer mon compte")

        with st.form("signup_form"):

            col1, col2 = st.columns(2)

            nom = col1.text_input("Nom")
            prenom = col2.text_input("Prénom")

            age = st.number_input(
                "Âge",
                15,
                100,
                25
            )

            teint = st.radio(
                "Teint",
                [
                    "Clair / Pâle",
                    "Intermédiaire / Mat",
                    "Foncé / Noir"
                ]
            )

            morpho = st.selectbox(
                "Morphologie",
                ["A", "V", "H", "X", "O"]
            )

            taille = st.number_input(
                "Taille (cm)",
                120,
                220,
                170
            )

            username = st.text_input("Pseudo (unique)")

            password = st.text_input(
                "Mot de passe",
                type="password"
            )

            profile_img = st.file_uploader(
                "Photo entière (optionnel)",
                type=["png", "jpg", "jpeg"]
            )

            submit = st.form_submit_button(
                "Créer mon compte"
            )

            if submit:

                if not username or not password:

                    st.warning("Pseudo et mot de passe obligatoires")

                else:

                    existing = get_user_profile(client, username)

                    if existing:

                        st.error("Ce pseudo existe déjà")

                    else:

                        user_data = {

                            "nom": nom,
                            "prenom": prenom,
                            "age": age,
                            "teint": teint,
                            "morpho": morpho,
                            "taille": taille,

                            "password": hash_password(password)

                        }

                        if profile_img:

                            user_data["profile_img_file"] = profile_img

                        save_profile_to_qdrant(
                            client,
                            model,
                            username,
                            user_data
                        )

                        st.success("Compte créé !")

                        st.session_state.logged_in = True
                        st.session_state.username = username

                        st.rerun()