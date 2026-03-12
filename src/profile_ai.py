import streamlit as st
from utile import save_profile_to_qdrant

def show_profile_sidebar(client, model, username, user_profile=None, require_password=False):
    """
    Affiche un formulaire complet pour créer ou mettre à jour un profil utilisateur.
    - client : Qdrant client
    - model : modèle d'encodage pour images
    - username : pseudo utilisateur
    - user_profile : dictionnaire des données existantes (optionnel)
    - require_password : True si on veut demander mot de passe et confirmation (création de compte)
    """

    st.header("Mon Profil")

    with st.form("profile_form"):

        col1, col2 = st.columns(2)

        # Nom et Prénom
        nom = col1.text_input("Nom", value=user_profile.get("nom", "") if user_profile else "")
        prenom = col2.text_input("Prénom", value=user_profile.get("prenom", "") if user_profile else "")

        # Âge
        age = st.number_input(
            "Âge",
            min_value=15,
            max_value=100,
            value=user_profile.get("age", 25) if user_profile else 25
        )

        # Teint
        teint_options = ["Clair / Pâle", "Intermédiaire / Mat", "Foncé / Noir"]
        default_teint = user_profile.get("teint", "Clair / Pâle") if user_profile else "Clair / Pâle"
        teint = st.radio("Teint", teint_options, index=teint_options.index(default_teint))

        # Morphologie
        morpho_options = ["A", "V", "H", "X", "O"]
        default_morpho = user_profile.get("morpho", "A") if user_profile else "A"
        morpho = st.selectbox("Morphologie", morpho_options, index=morpho_options.index(default_morpho))

        # Taille
        taille = st.number_input(
            "Taille (cm)",
            min_value=120,
            max_value=220,
            value=user_profile.get("taille", 170) if user_profile else 170
        )

        # Pseudo
        st.text_input("Pseudo", value=username)

        # Mot de passe (si création de compte)
        password = None
        if require_password:
            password = st.text_input("Mot de passe", type="password")
            password_confirm = st.text_input("Confirmer mot de passe", type="password")
            if password != password_confirm:
                st.warning("Les mots de passe ne correspondent pas !")
                st.stop()

        # Photo entière
        profile_img = st.file_uploader(
            "Uploader une photo entière (optionnel)",
            type=["png", "jpg", "jpeg"]
        )

        submit_btn = st.form_submit_button("Enregistrer le profil")

       if submit_btn:
          user_data = {
              "nom": nom,
              "prenom": prenom,
              "age": age,
              "teint": teint,
              "morpho": morpho,
              "taille": taille,
              "user_pseudo": username,
              "password": hash_password(password) if require_password else None
         } 

    if profile_img:
        user_data["profile_img_file"] = profile_img

    save_profile_to_qdrant(client, model, username, user_data)
    st.success("Profil sauvegardé avec succès !")

    # remplacer experimental_rerun par st.stop pour forcer Streamlit à recharger
    st.stop()