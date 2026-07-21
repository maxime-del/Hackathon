"""
SOS Redemarrage - Copilote de reprise apres cyberattaque (NovaRetail / P01).

Principe directeur: le CODE calcule (graphe, ordre de reconstruction,
anomalies, euros) de facon deterministe et reproductible, via des tools
appeles par des agents specialises (graph/anomaly/risk), arbitres par un
decideur. Qwen ne fait que traduire ces faits en langage clair et
dialoguer - jamais de calcul cache dans un prompt.

Les fichiers source (CSV + .docx) peuvent etre ceux de l'exemple NovaRetail
livre dans data/, ou deposes par l'utilisateur via l'interface - dans ce
second cas, noms de fichiers et noms de colonnes peuvent etre totalement
differents: `tools.schema_mapping` les reconnait par similarite de colonnes
plutot que par nom exact.
"""
import pandas as pd
import streamlit as st

from agents import ingestion_agent, translator_agent
from core.format import eur
from core.llm import llm_is_available
from tools import data_loader, retrieval
from tools.categorize import LAYER_ORDER
from tools.narrate import category_status_color, explain_step, human_name
from tools.schema_mapping import ROLE_SCHEMAS, classify_and_normalize

PROCESS_ID = "P01"

st.set_page_config(page_title="SOS Redemarrage", page_icon="🆘", layout="wide")

DASHBOARD_GROUPS = {
    "🛒 Boutique en ligne": ["Boutique"],
    "💳 Paiement": ["Paiement"],
    "📦 Stock & Livraison": ["Stock & Livraison"],
    "🗄️ Donnees (commandes, ERP)": ["Donnees"],
    "🔐 Securite & identite": ["Identite", "Reseau / DNS", "Certificats (PKI)", "Coffre-fort secrets"],
    "🎧 Service client": ["Service client"],
}


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
    "pour un gerant sans DSI. Cas d'usage par defaut: NovaRetail, processus P01 (commandes e-commerce)."
)

mode = st.radio("Mode d'affichage", ["🙂 Mode Gerant (Karim)", "🛠️ Mode Architecte"], horizontal=True)

st.divider()

# ------------------------------------------------------------ vos fichiers --
st.subheader("📂 Vos fichiers")
st.caption(
    "Deposez vos propres exports (CSV) et documents (.docx) — noms de fichiers et noms de "
    "colonnes peuvent etre completement differents de l'exemple, le systeme essaie de les "
    "reconnaitre automatiquement par similarite. Sans depot, la demo tourne sur le cas "
    "NovaRetail fourni."
)
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
st.subheader("Qu'est-ce qui ne marche plus ?")
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

run = st.button("🔍 Lancer le diagnostic", type="primary")

if run:
    classification_report = prepare_dataset(csv_files, docx_files, incident_dt_text)
    with st.spinner("Analyse en cours (graphe, anomalies, risque, traduction)..."):
        st.session_state["engine_state"] = ingestion_agent.run(PROCESS_ID)
    st.session_state["classification_report"] = classification_report
    st.session_state["diagnosed"] = True

if "diagnosed" not in st.session_state:
    st.info("Cliquez sur *Lancer le diagnostic* pour generer le plan de reprise.")
    st.stop()

STATE = st.session_state["engine_state"]
G = STATE.graph
STEPS = STATE.final_plan
BROKEN_CYCLES = STATE.broken_cycles
ANOMALIES = STATE.findings
RISK = STATE.risk_items[0]
critical_actions = STATE.manual_validations

st.divider()

# --------------------------------------------- rapport de reconnaissance ----
report = st.session_state.get("classification_report") or []
if report:
    st.subheader("🔎 Reconnaissance des fichiers deposes")
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

# ----------------------------------------------------- tableau de bord ----
st.subheader("Etat des services")
cards = st.columns(len(DASHBOARD_GROUPS))
for col, (label, categories) in zip(cards, DASHBOARD_GROUPS.items()):
    nodes_in_group = [s for s in STEPS if s.category in categories]
    color = category_status_color(nodes_in_group) if nodes_in_group else "⚪"
    with col:
        st.markdown(f"### {color}")
        st.markdown(f"**{label}**")
        st.caption(f"{len(nodes_in_group)} element(s) concerne(s)")

st.divider()

# --------------------------------------------------------- alerte risque --
st.subheader("⚠️ Risque financier principal")
if RISK.data_sufficient:
    st.error(
        f"**Perte estimee : {eur(RISK.estimated_loss_eur)}**\n\n"
        f"La derniere sauvegarde vraiment fiable des commandes clients date du "
        f"**{RISK.last_reliable_backup:%d/%m/%Y %H:%M}**, soit environ **{RISK.gap_hours:.0f} heures** "
        f"avant l'incident. {RISK.confidence_note}\n\n"
        f"_Sources : {', '.join(RISK.sources)}_"
    )
else:
    st.warning(f"ℹ️ {RISK.confidence_note}")

st.divider()

# --------------------------------------------------- narration Qwen -------
st.subheader("Resume de la situation")
if not llm_is_available():
    st.caption("ℹ️ Cle API Qwen non configuree — resume genere par gabarit deterministe (hors-ligne).")
st.markdown(STATE.situation_summary)

st.divider()

# ------------------------------------------------ a valider par un pro ----
if critical_actions:
    st.subheader("🧑‍🔧 A faire valider par un professionnel avant d'agir")
    for a in critical_actions:
        st.warning(f"**{a.title_human}** — {a.action_pro}")

st.divider()

# ------------------------------------------------------------- le plan ----
st.subheader("📋 Plan de redemarrage, dans l'ordre")
for s in STEPS:
    st.markdown(f"**Etape {s.step}.** {explain_step(s)}")
    with st.expander("Details techniques"):
        st.write(f"Systeme : `{s.node}` — categorie technique : {s.category} — criticite : {s.criticality}")
        st.write("Raisons de la confiance affichee :")
        for reason, source in zip(s.confidence_reasons, s.confidence_sources):
            st.write(f"- {reason} _(source: {source})_")
        if s.prerequisites:
            st.write("Doit etre restaure apres : " + ", ".join(f"`{p}`" for p in s.prerequisites))

st.divider()

# --------------------------------------------------------- anomalies ------
st.subheader(f"🔎 Incoherences detectees dans les documents ({len(ANOMALIES)})")
for a in ANOMALIES:
    icon = {"CRITIQUE": "🔴", "HAUTE": "🟠", "MOYENNE": "🟡"}.get(a.severity, "⚪")
    with st.expander(f"{icon} {a.title_human}"):
        st.write(a.detail_human)
        st.markdown("---")
        st.caption(f"**Detail technique :** {a.detail_tech}")
        st.caption(f"**Sources :** {', '.join(a.sources)}")

st.divider()

# --------------------------------------------------------------- Q&A ------
st.subheader("💬 Poser une question au copilote")
question = st.text_input("Ex: les clients peuvent-ils payer maintenant ?")
if question:
    with st.spinner("Recherche de la reponse..."):
        answer = translator_agent.answer_question(STATE, question)
    st.markdown(answer)

st.divider()

# ------------------------------------------------------------- export -----
st.subheader("📤 Exporter le plan")


def build_export_markdown() -> str:
    lines = [
        "# Plan de redemarrage — NovaRetail — Processus P01",
        "",
        f"## Risque financier principal",
        f"Perte estimee : {eur(RISK.estimated_loss_eur)} "
        f"(source : {', '.join(RISK.sources)})",
        "",
        "## A faire valider par un professionnel",
    ]
    for a in critical_actions:
        lines.append(f"- {a.title_human} : {a.action_pro}")
    lines += ["", "## Plan de redemarrage, dans l'ordre"]
    for s in STEPS:
        lines.append(f"{s.step}. {human_name(s.node)} — confiance : {s.confidence}")
    lines += ["", "## Incoherences detectees"]
    for a in ANOMALIES:
        lines.append(f"- [{a.severity}] {a.title_human} (sources : {', '.join(a.sources)})")
    return "\n".join(lines)


st.download_button(
    "Telecharger la checklist (Markdown)",
    data=build_export_markdown(),
    file_name="plan_redemarrage_novaretail.md",
    mime="text/markdown",
)

# ============================================================ ARCHITECTE ==
if mode.startswith("🛠️"):
    st.divider()
    st.header("🛠️ Vue architecte")

    st.subheader("Graphe de dependances (P01)")
    try:
        from pyvis.network import Network
        import streamlit.components.v1 as components

        net = Network(height="600px", width="100%", directed=True, notebook=False, bgcolor="#111111", font_color="white")
        color_map = {"SUR": "#2ecc71", "INCERTAIN": "#f39c12", "DANGER": "#e74c3c", "INCONNU": "#95a5a6"}
        for node in G.nodes:
            data = G.nodes[node]
            conf = data.get("confidence", "INCONNU")
            net.add_node(node, label=node, color=color_map.get(conf, "#95a5a6"),
                         title=f"{data.get('category','')} — confiance: {conf}")
        for u, v, data in G.edges(data=True):
            net.add_edge(u, v, title=data.get("dependency_type", ""))
        net.repulsion(node_distance=160, spring_length=160)
        html_path = "/tmp/graph_p01.html"
        net.write_html(html_path, open_browser=False, notebook=False)
        with open(html_path, "r", encoding="utf-8") as f:
            components.html(f.read(), height=620, scrolling=True)
    except Exception as e:
        st.warning(f"Rendu interactif indisponible ({e}). Liste des aretes ci-dessous.")
        for u, v, data in G.edges(data=True):
            st.write(f"`{u}` → `{v}` ({data.get('dependency_type','')}, confiance {data.get('confidence','?')})")

    if BROKEN_CYCLES:
        st.error(f"Cycles detectes et rompus pour permettre le tri topologique : {BROKEN_CYCLES}")

    st.subheader("Ordre de reconstruction — detail complet")
    st.table([
        {
            "Etape": s.step, "Noeud": s.node, "Categorie": s.category, "Profondeur": s.depth,
            "Criticite": s.criticality, "Confiance": s.confidence,
            "Prerequis": ", ".join(s.prerequisites),
        }
        for s in STEPS
    ])

    st.subheader("Couches techniques (reference)")
    st.write(" → ".join(LAYER_ORDER))

    st.subheader("🤖 Traces des agents specialises")
    st.caption("Chaque specialiste ne recoit que les resultats des tools deterministes qui le concernent.")
    with st.expander("graph_agent"):
        st.write(STATE.graph_narrative)
    with st.expander("anomaly_agent"):
        st.write(STATE.anomaly_narrative)
    with st.expander("risk_agent"):
        st.write(STATE.risk_narrative)
    with st.expander("decider_agent (synthese finale)"):
        st.write(STATE.decider_narrative)
