"""
SOS Redemarrage - point d'entree / routeur entre les deux pages :
depot des sources et dashboard des resultats.
"""
import streamlit as st

st.set_page_config(page_title="SOS Redemarrage", page_icon="🆘", layout="wide")

pages = [
    st.Page("views/upload.py", title="Depot des sources", icon="📂", default=True),
    st.Page("views/dashboard.py", title="Dashboard", icon="📊"),
]
st.navigation(pages).run()
