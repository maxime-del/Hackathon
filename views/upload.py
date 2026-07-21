"""
SOS Redemarrage - Page 1/2 : Depot des sources. Le calcul (graphe, ordre
de reconstruction, anomalies, euros) est fait une seule fois ici par les
agents specialises, puis stocke dans st.session_state pour que la page
Dashboard n'ait qu'a le lire - jamais de recalcul en changeant de page.

Les fichiers source (CSV + .docx) peuvent etre ceux de l'exemple NovaRetail
livre dans data/, ou deposes par l'utilisateur - dans ce second cas, noms
de fichiers et noms de colonnes peuvent etre totalement differents:
`tools.schema_mapping` les reconnait par similarite de colonnes plutot que
par nom exact.
"""
import pandas as pd
import streamlit as st

from agents import ingestion_agent
from tools import data_loader, retrieval
from tools.schema_mapping import ROLE_SCHEMAS, classify_and_normalize

PROCESS_ID = "P01"


def _read_uploaded_csv(uploaded_file) -> pd.DataFrame | None:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding=encoding)
        except Exception:
            continue
    return None


def prepare_dataset(csv_files, docx_files, incident_dt_text: str) -> list:
    """Bascule le moteur sur les fichiers uploades (ou revient au jeu
    d'exemple NovaRetail si rien n'est depose). Renvoie le rapport de
    classification pour affichage."""
    report = []
    if csv_files:
        uploads = {}
        for f in csv_files:
            df = _read_uploaded_csv(f)
            if df is None:
                st.warning(f"⚠️ Impossible de lire `{f.name}` comme un CSV valide — ignore.")
                continue
            df.columns = [str(c).strip() for c in df.columns]
            uploads[f.name] = df
        tables, report = classify_and_normalize(uploads)
        data_loader.set_active_tables(tables)
        try:
            data_loader.set_incident_time(pd.Timestamp(incident_dt_text))
        except (ValueError, TypeError):
            st.warning(f"⚠️ Date d'incident '{incident_dt_text}' illisible — heure par defaut conservee.")
    else:
        data_loader.clear_active_tables()

    if docx_files:
        retrieval.set_active_docs({f.name: f.read() for f in docx_files})
    else:
        retrieval.clear_active_docs()

    return report


# ---------------------------------------------------------------- header --
st.title("🆘 SOS Redemarrage")
st.caption(
    "Copilote de reprise apres cyberattaque — traduit le diagnostic technique en langage clair "
    "pour un dirigeant sans DSI. Cas d'usage par defaut : NovaRetail, processus P01 (commandes e-commerce)."
)

st.divider()

# ------------------------------------------------------------ vos fichiers --
st.header("📂 1. Deposez vos sources")
st.caption(
    "Exports CSV du SI et documents `.docx` (PRA, rapports, notes...) — noms de fichiers et noms de "
    "colonnes peuvent etre completement differents de l'exemple, le systeme les reconnait automatiquement "
    "par similarite. Sans depot, la demo tourne sur le cas NovaRetail fourni."
)
with st.container(border=True):
    col_csv, col_docx = st.columns(2)
    with col_csv:
        csv_files = st.file_uploader("Exports CSV du SI", type="csv", accept_multiple_files=True)
    with col_docx:
        docx_files = st.file_uploader("Documents (PRA, rapports, notes...)", type="docx", accept_multiple_files=True)

    if csv_files:
        incident_dt_text = st.text_input(
            "Date/heure de declaration de l'incident (sert au calcul des ecarts RPO)",
            value="2026-06-08 08:15",
        )
    else:
        incident_dt_text = "2026-06-08 08:15"

st.divider()

# ---------------------------------------------------------- entree gerant --
st.header("💬 2. Decrivez le probleme")
with st.container(border=True):
    col_in, col_q = st.columns([2, 1])
    with col_in:
        user_message = st.text_area(
            "Decrivez le probleme avec vos mots",
            value="Mon site de commandes ne marche plus, aide-moi a le redemarrer.",
            height=80,
        )
    with col_q:
        site_visible = st.checkbox("Les clients voient le site", value=False)
        peuvent_payer = st.checkbox("Les clients peuvent payer", value=False)

    run = st.button("🔍 Lancer le diagnostic", type="primary", use_container_width=True)

if run:
    classification_report = prepare_dataset(csv_files, docx_files, incident_dt_text)
    with st.spinner("Analyse en cours (graphe, anomalies, risque, traduction)..."):
        st.session_state["engine_state"] = ingestion_agent.run(PROCESS_ID)
    st.session_state["classification_report"] = classification_report
    st.session_state["diagnosed"] = True

st.divider()

# --------------------------------------------- rapport de reconnaissance ----
report = st.session_state.get("classification_report") or []
if report:
    st.header("🔎 Reconnaissance des fichiers deposes")
    found_roles = {r.role for r in report if r.role}
    for r in report:
        if r.role:
            st.success(f"`{r.filename}` → reconnu comme **{r.role}** (confiance {r.score:.0%})")
        else:
            st.warning(f"`{r.filename}` → non reconnu (meilleur score {r.score:.0%}), ignore")
    missing_roles = sorted(set(ROLE_SCHEMAS.keys()) - found_roles)
    if missing_roles:
        st.info(
            "Roles non couverts par vos fichiers : " + ", ".join(f"`{r}`" for r in missing_roles) +
            ". Les analyses qui en dependent seront incompletes ou absentes, plutot que devinees."
        )
    st.divider()

# ------------------------------------------------------------------ suite --
if st.session_state.get("diagnosed"):
    st.success("✅ Diagnostic pret. Ouvrez la page **Dashboard** dans le menu a gauche pour voir les resultats.")
    if st.button("📊 Aller au Dashboard", type="primary"):
        st.switch_page("views/dashboard.py")
else:
    st.info("Cliquez sur *Lancer le diagnostic* pour generer le plan de reprise.")
