# search.py  —  Unified search page (Text / Image)
import streamlit as st
from PIL import Image
from utile import display_image, toggle_favorite

def show_search(model, client, username=""):

    st.subheader("Recherche intelligente")

    mode = st.radio(
        "Mode de recherche",
        ["Texte", "Image"]
    )

    vec = None

    # ---------------- RECHERCHE TEXTE ----------------
    if mode == "Texte":

        q = st.text_input(
            "Decrivez le vetement",
            placeholder="ex: veste en cuir noir"
        )

        if st.button("Lancer la recherche"):

            if q:
                # Track search history
                if "search_history" not in st.session_state:
                    st.session_state.search_history = []
                st.session_state.search_history.append(q)

                with st.spinner("Recherche en cours..."):
                    vec = model.encode(q).tolist()
            else:
                st.warning("Veuillez entrer une description.")

    # ---------------- RECHERCHE IMAGE ----------------
    elif mode == "Image":

        uploaded_file = st.file_uploader(
            "Uploader une image",
            type=["jpg", "jpeg", "png"]
        )

        if uploaded_file:

            img = Image.open(uploaded_file)

            st.image(
                img,
                caption="Image utilisee pour la recherche",
                width=200
            )

            if st.button("Lancer la recherche"):

                with st.spinner("Analyse de l'image..."):
                    vec = model.encode(img).tolist()

    # ---------------- RESULTATS ----------------
    if vec:

        try:
            res = client.query_points(
                collection_name="fashion_images",
                query=vec,
                limit=8
            ).points
        except Exception:
            res = []
            st.error("Erreur de connexion a la base vectorielle.")

        if res:

            st.write("### Resultats trouves")

            cols = st.columns(min(len(res), 4))

            for i, h in enumerate(res):
                with cols[i % 4]:
                    display_image(h.payload, use_container_width=True)
                    st.caption(f"Score : {round(h.score * 100)}%")

                    if username:
                        point_id = str(h.id)
                        is_fav = point_id in st.session_state.get("favorites", set())
                        fav_label = "Retirer" if is_fav else "Sauvegarder"
                        if st.button(fav_label, key=f"fav_s_{point_id}"):
                            toggle_favorite(client, username, point_id)
                            if is_fav:
                                st.session_state.favorites.discard(point_id)
                            else:
                                st.session_state.favorites.add(point_id)
                            st.rerun()

                        if st.button("Essayer", key=f"vton_s_{point_id}"):
                            st.session_state.vton_item = h.payload
                            st.session_state.page = "vton"
                            st.rerun()

        else:
            st.warning("Aucun resultat trouve.")