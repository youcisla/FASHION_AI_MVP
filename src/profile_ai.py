# profile_ai.py
import streamlit as st
from utile import save_profile_to_qdrant, hash_password, get_user_profile, username_exists
 
def show_profile_sidebar(client, model, username, user_profile=None, require_password=False):
    """
    Formulaire création ou mise à jour de profil.
    Logique "patch" : seuls les champs modifiés sont mis à jour dans la BD.
    """

    if user_profile is None:
        user_profile = get_user_profile(client, username) or {}

    with st.form("profile_form"):

        col1, col2 = st.columns(2)
        nom_input = col1.text_input("Nom", value=user_profile.get("nom", ""), placeholder="Dupont")
        prenom_input = col2.text_input("Prénom", value=user_profile.get("prenom", ""), placeholder="Marie")

        col3, col4 = st.columns(2)
        age_input = col3.number_input("Âge", min_value=15, max_value=100, value=user_profile.get("age", 25))
        taille_input = col4.number_input("Taille (cm)", min_value=120, max_value=220, value=user_profile.get("taille", 170))

        teint_options = ["Clair / Pâle", "Intermédiaire / Mat", "Foncé / Noir"]
        default_teint = user_profile.get("teint", "Clair / Pâle")
        teint_input = st.radio("Teint", teint_options, index=teint_options.index(default_teint), horizontal=True)

        morpho_options = ["A", "V", "H", "X", "O"]
        default_morpho = user_profile.get("morpho", "A")
        morpho_input = st.selectbox("Morphologie", morpho_options, index=morpho_options.index(default_morpho))

        # Pseudo
        username_input = st.text_input("Pseudo", value=user_profile.get("user_pseudo", username))
 
        # Mot de passe
        password_input = None
        password_to_store = user_profile.get("password")  # On conserve le hash existant par défaut
        if require_password:
            password_input = st.text_input("Mot de passe", type="password")
            password_confirm = st.text_input("Confirmer mot de passe", type="password")
            if password_input and password_confirm and password_input != password_confirm:
                st.warning("Les mots de passe ne correspondent pas")
                st.stop()
            if password_input:
                password_to_store = hash_password(password_input)
        else:
            modify_password = st.checkbox("Modifier le mot de passe")
            if modify_password:
                password_input = st.text_input("Nouveau mot de passe", type="password")
                password_confirm = st.text_input("Confirmer le nouveau mot de passe", type="password")
                if password_input and password_confirm and password_input != password_confirm:
                    st.warning("Les mots de passe ne correspondent pas")
                    st.stop()
                if password_input:
                    password_to_store = hash_password(password_input)
 
        profile_img_input = st.file_uploader("📷 Photo de profil (optionnel)", type=["png","jpg","jpeg"])

        submit_label = "Créer mon compte" if require_password else "💾 Enregistrer"
        submit_btn = st.form_submit_button(submit_label)
 
        if submit_btn:
            # Dictionnaire pour mettre à jour uniquement les champs modifiés
            updated_fields = {}
 
            if nom_input != user_profile.get("nom", ""):
                updated_fields["nom"] = nom_input
            if prenom_input != user_profile.get("prenom", ""):
                updated_fields["prenom"] = prenom_input
            if age_input != user_profile.get("age", 25):
                updated_fields["age"] = age_input
            if teint_input != user_profile.get("teint", "Clair / Pâle"):
                updated_fields["teint"] = teint_input
            if morpho_input != user_profile.get("morpho", "A"):
                updated_fields["morpho"] = morpho_input
            if taille_input != user_profile.get("taille", 170):
                updated_fields["taille"] = taille_input
            if username_input != user_profile.get("user_pseudo", username):
                updated_fields["user_pseudo"] = username_input
            if password_to_store != user_profile.get("password"):
                updated_fields["password"] = password_to_store
            if profile_img_input is not None:
                updated_fields["profile_img_file"] = profile_img_input
 
            if updated_fields:
                # Username uniqueness check on signup
                if require_password and username_exists(client, username_input):
                    st.error("Ce pseudo est déjà pris. Choisissez-en un autre.")
                    st.stop()
                # Appel patch / update partiel
                save_profile_to_qdrant(client, model, username_input, updated_fields)
                if require_password:
                    # Signup: auto-login and redirect to home
                    st.session_state.logged_in = True
                    st.session_state.username = username_input
                    st.session_state.page = "home"
                    st.rerun()
                else:
                    st.success("Profil sauvegardé avec succès !")
            else:
                st.info("Aucune modification détectée.")