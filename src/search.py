import streamlit as st


def show_search(model, client):

    q = st.text_input("Recherche texte")

    if q:

        vec = model.encode(q).tolist()

        res = client.search(
            collection_name="fashion_images",
            query_vector=vec,
            limit=4
        )

        cols = st.columns(4)

        for i, h in enumerate(res):
            cols[i].image(h.payload["path"])