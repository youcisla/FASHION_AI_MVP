# app.py  —  Fashion AI · Modular dark-luxury Streamlit app
import streamlit as st

st.set_page_config(page_title="Fashion AI", page_icon="\u2726", layout="wide")

from utile import (
    init_tools,
    get_user_profile,
    get_favorites,
    display_image,
)
from auth import render_login_page
from profile_ai import show_profile_sidebar
from search import show_search
import look_generator
import vton
import analytic

# ─── Dark luxury CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
:root {
    --surface: #1a1a2e;
    --surface-alt: #16213e;
    --accent: #c9a84c;
    --blush: #e8c4b8;
    --text: #f5f0e8;
    --muted: #8e8e9e;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
}
[data-testid="stSidebar"] * {
    color: var(--text) !important;
}
.fa-card {
    background: var(--surface-alt);
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
    border: 1px solid rgba(201,168,76,0.15);
}
.nav-btn button {
    text-align: left !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.6rem 1rem !important;
    margin-bottom: 2px !important;
    background: transparent !important;
    color: var(--text) !important;
    font-family: 'DM Sans', sans-serif !important;
}
.nav-btn button:hover {
    background: rgba(201,168,76,0.12) !important;
}
</style>
""", unsafe_allow_html=True)

# ─── Init ─────────────────────────────────────────────────────────────────────
model, client = init_tools()

# ─── Session state defaults ───────────────────────────────────────────────────
_defaults = {
    "logged_in": False,
    "username": "",
    "page": "home",
    "favorites": set(),
    "search_history": [],
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ═══════════════════════════════════════════════════════════════════════════════
#  AUTH GATE
# ═══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    render_login_page(client, model)
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════════
#  LOGGED-IN  —  sidebar + page router
# ═══════════════════════════════════════════════════════════════════════════════
username = st.session_state.username
user_profile = get_user_profile(client, username) or {}

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;margin:0 0 18px;">
        <span style="font-family:'Playfair Display',serif;font-size:2rem;color:var(--accent);font-weight:700;">FA</span>
        <p style="margin:2px 0 0;font-size:0.85rem;color:var(--muted);">Fashion AI</p>
    </div>
    """, unsafe_allow_html=True)

    # Profile image
    b64 = user_profile.get("profile_img_b64")
    if b64:
        st.markdown(
            f'<div style="text-align:center;margin-bottom:8px;">'
            f'<img src="data:image/jpeg;base64,{b64}" '
            f'style="width:80px;height:80px;border-radius:50%;object-fit:cover;'
            f'border:2px solid var(--accent);"></div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<p style="text-align:center;font-weight:600;margin-bottom:16px;">{username}</p>',
        unsafe_allow_html=True,
    )

    # Navigation
    pages = {
        "home": "Accueil",
        "search": "Recherche",
        "looks": "Looks",
        "vton": "Essayage Virtuel",
        "favorites": "Favoris",
        "analytics": "Analytics",
        "profile": "Mon Profil",
    }

    st.markdown('<div class="nav-btn">', unsafe_allow_html=True)
    for key, label in pages.items():
        if st.button(label, key=f"nav_{key}", use_container_width=True):
            st.session_state.page = key
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    if st.button("Deconnexion", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

# ─── Page router ──────────────────────────────────────────────────────────────
page = st.session_state.page

# ── HOME ──────────────────────────────────────────────────────────────────────
if page == "home":
    st.markdown("""
    <div style="text-align:center;padding:3rem 0 2rem;">
        <span style="font-family:'Playfair Display',serif;font-size:3rem;color:var(--accent);font-weight:700;">Fashion AI</span>
        <p style="color:var(--muted);font-size:1.05rem;margin-top:8px;">Votre assistant mode intelligent</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class="fa-card" style="text-align:center;">
            <p style="color:var(--accent);font-size:1.3rem;font-weight:700;">Recherche</p>
            <p style="color:var(--muted);font-size:0.85rem;">Trouvez des vetements par texte ou image</p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class="fa-card" style="text-align:center;">
            <p style="color:var(--accent);font-size:1.3rem;font-weight:700;">Looks</p>
            <p style="color:var(--muted);font-size:0.85rem;">Generez des tenues adaptees a votre profil</p>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class="fa-card" style="text-align:center;">
            <p style="color:var(--accent);font-size:1.3rem;font-weight:700;">Essayage</p>
            <p style="color:var(--muted);font-size:0.85rem;">Essayez virtuellement sur votre silhouette</p>
        </div>
        """, unsafe_allow_html=True)

# ── SEARCH ────────────────────────────────────────────────────────────────────
elif page == "search":
    show_search(model, client, username)

# ── LOOK GENERATOR ────────────────────────────────────────────────────────────
elif page == "looks":
    look_generator.render(client, model, user_profile, username)

# ── VTON ──────────────────────────────────────────────────────────────────────
elif page == "vton":
    vton.render(client, model, user_profile, username)

# ── FAVORITES ─────────────────────────────────────────────────────────────────
elif page == "favorites":
    st.markdown("## Mes Favoris")
    fav_ids = get_favorites(client, username)
    if not fav_ids:
        st.info("Vous n'avez pas encore de favoris. Explorez le catalogue et sauvegardez des articles.")
    else:
        try:
            points = client.retrieve(
                collection_name="fashion_images",
                ids=fav_ids,
                with_payload=True,
            )
        except Exception:
            points = []
            st.error("Erreur de connexion a la base vectorielle.")
        if points:
            cols = st.columns(min(len(points), 4))
            for i, pt in enumerate(points):
                with cols[i % 4]:
                    display_image(pt.payload, use_container_width=True)
                    st.caption(pt.payload.get("filename", ""))

# ── ANALYTICS ─────────────────────────────────────────────────────────────────
elif page == "analytics":
    analytic.render(client, model, user_profile, username)

# ── PROFILE ───────────────────────────────────────────────────────────────────
elif page == "profile":
    show_profile_sidebar(client, model, username, user_profile, require_password=False)