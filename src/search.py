# search.py  —  Unified 3-tab search page (Text / Category / Image)
import streamlit as st
from PIL import Image

def show_search(model, client):

    st.subheader("🔍 Recherche intelligente")

    mode = st.radio(
        "Mode de recherche",
        ["Texte", "Image"]
    )

    vec = None

    # ---------------- RECHERCHE TEXTE ----------------
    if mode == "Texte":

        q = st.text_input(
            "Décrivez le vêtement",
            placeholder="ex: veste en cuir noir"
        )

        if st.button("Lancer la recherche 🔎"):

            if q:

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
                caption="Image utilisée pour la recherche",
                width=200
            )

            if st.button("Lancer la recherche 🔎"):

                with st.spinner("Analyse de l'image..."):

                    vec = model.encode(img).tolist()

    # ---------------- LANCEMENT RECHERCHE ----------------
    if vec:

        res = client.query_points(
            collection_name="fashion_images",
            query=vec,
            limit=4
        ).points

        if res:

            st.write("### Résultats trouvés")

            cols = st.columns(len(res))

            for i, h in enumerate(res):

                cols[i].image(
                    h.payload["image_path"],
                    caption=f"Score: {round(h.score,2)}"
                )

        else:

            st.warning("Aucun résultat trouvé.")