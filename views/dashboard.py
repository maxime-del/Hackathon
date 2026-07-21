"""
SOS Redemarrage - Page 2/2 : Dashboard.

Ne recalcule jamais rien : lit uniquement l'EngineState depose en
session_state par la page de depot (app.py). Organise en onglets pour
rester lisible sans un long defilement unique : Cartographie (graphe +
etat des services), Top actions urgentes (ce qu'il faut valider/traiter
en premier), Plan de reprise (l'ordre complet), Assistant (resume,
questions libres, export).
"""
import streamlit as st

from agents import translator_agent
from core.format import eur
from core.llm import llm_is_available
from tools.categorize import CATEGORY_ICONS, LAYER_ORDER
from tools.narrate import category_status_color, explain_step, human_name

RISK_BADGE = {"FAIBLE": "🟢", "MOYEN": "🟠", "ELEVE": "🔴"}
RISK_LABEL = {"FAIBLE": "Risque faible", "MOYEN": "Risque moyen", "ELEVE": "Risque eleve"}
RISK_ORDER = {"FAIBLE": 0, "MOYEN": 1, "ELEVE": 2}

if "engine_state" not in st.session_state:
    st.title("📊 Dashboard")
    st.info("Aucun diagnostic en memoire. Retournez sur la page **Depot des sources** pour en lancer un.")
    if st.button("📂 Aller au depot des sources", type="primary"):
        st.switch_page("views/upload.py")
    st.stop()

STATE = st.session_state["engine_state"]
G = STATE.graph
STEPS = STATE.final_plan
BROKEN_CYCLES = STATE.broken_cycles
ANOMALIES = STATE.findings
RISK = STATE.risk_items[0]
critical_actions = STATE.manual_validations

blocking_steps = [s for s in STEPS if s.criticality == "Bloquante"]
high_risk_steps = [s for s in STEPS if s.risk_level == "ELEVE"]
medium_risk_steps = [s for s in STEPS if s.risk_level == "MOYEN"]
low_risk_steps = [s for s in STEPS if s.risk_level == "FAIBLE"]
critical_findings = [a for a in ANOMALIES if a.severity == "CRITIQUE"]

# Groupes du dashboard construits dynamiquement a partir des categories
# reellement presentes dans le plan (deduites du type CMDB, generique) -
# plus de dictionnaire fige de categories "metier" specifiques a un corpus.
present_categories = sorted(
    {s.category for s in STEPS},
    key=lambda c: LAYER_ORDER.index(c) if c in LAYER_ORDER else len(LAYER_ORDER),
)
DASHBOARD_GROUPS = {f"{CATEGORY_ICONS.get(c, '❔')} {c}": [c] for c in present_categories}

# ---------------------------------------------------------------- header --
st.title(f"📊 Dashboard de reprise — Processus {STATE.process_id}")
st.caption("Photographie de la situation au moment du diagnostic. Relancez le diagnostic depuis la page de depot pour l'actualiser.")

if RISK.data_sufficient:
    st.error(
        f"⚠️ **Perte financiere estimee : {eur(RISK.estimated_loss_eur)}** — actif le plus expose : **{RISK.asset}**, "
        f"derniere sauvegarde fiable le **{RISK.last_reliable_backup:%d/%m/%Y %H:%M}** "
        f"(~{RISK.gap_hours:.0f}h avant l'incident). {RISK.confidence_note}"
    )
    if len(STATE.risk_items) > 1:
        st.caption(
            "Autres actifs egalement en violation de RPO : " + ", ".join(
                f"{r.asset} ({eur(r.estimated_loss_eur)})" for r in STATE.risk_items[1:]
            )
        )
else:
    st.warning(f"ℹ️ {RISK.confidence_note}")

kpi_cols = st.columns(5)
kpi_cols[0].metric("Etapes du plan", len(STEPS))
kpi_cols[1].metric("Etapes bloquantes", len(blocking_steps))
kpi_cols[2].metric("Decisions a risque eleve", len(high_risk_steps))
kpi_cols[3].metric("Anomalies critiques", len(critical_findings))
kpi_cols[4].metric("Perte financiere", eur(RISK.estimated_loss_eur) if RISK.data_sufficient else "n/a")

st.caption(
    f"Repartition du risque par decision : 🟢 {len(low_risk_steps)} faible · "
    f"🟠 {len(medium_risk_steps)} moyen · 🔴 {len(high_risk_steps)} eleve"
)

st.divider()

tab_map, tab_actions, tab_plan, tab_assistant = st.tabs([
    "🗺️ Cartographie", "🚨 Top actions urgentes", "📋 Plan de reprise d'activite", "💬 Assistant & export",
])

# ============================================================ CARTOGRAPHIE =
with tab_map:
    st.subheader("Etat des services")
    st.caption("Cliquez sur *Detail* pour voir les systemes concernes et leur risque.")

    if "selected_category" not in st.session_state:
        st.session_state["selected_category"] = None

    cards = st.columns(len(DASHBOARD_GROUPS))
    for col, (label, categories) in zip(cards, DASHBOARD_GROUPS.items()):
        nodes_in_group = [s for s in STEPS if s.category in categories]
        color = category_status_color(nodes_in_group) if nodes_in_group else "⚪"
        with col:
            with st.container(border=True):
                st.markdown(f"### {color}")
                st.markdown(f"**{label}**")
                st.caption(f"{len(nodes_in_group)} element(s)")
                if st.button("🔍 Detail", key=f"cat_btn_{label}", use_container_width=True):
                    st.session_state["selected_category"] = (
                        None if st.session_state["selected_category"] == label else label
                    )

    selected_category = st.session_state.get("selected_category")
    if selected_category:
        categories = DASHBOARD_GROUPS[selected_category]
        nodes_in_group = sorted(
            (s for s in STEPS if s.category in categories),
            key=lambda s: -RISK_ORDER.get(s.risk_level, 0),
        )
        with st.container(border=True):
            st.markdown(f"#### 🔎 Detail — {selected_category}")
            if not nodes_in_group:
                st.caption("Aucun element dans cette categorie pour ce processus.")
            for s in nodes_in_group:
                st.markdown(
                    f"{RISK_BADGE.get(s.risk_level, '⚪')} **{human_name(s.node)}** "
                    f"({RISK_LABEL.get(s.risk_level, 'Risque non evalue')})"
                )
                st.caption(s.risk_consequence)

    st.divider()
    st.subheader("Graphe de dependances")
    try:
        from pyvis.network import Network
        import streamlit.components.v1 as components

        net = Network(height="550px", width="100%", directed=True, notebook=False, bgcolor="#ffffff", font_color="#0f172a")
        color_map = {"SUR": "#16a34a", "INCERTAIN": "#f59e0b", "DANGER": "#dc2626", "INCONNU": "#94a3b8"}
        for node in G.nodes:
            data = G.nodes[node]
            conf = data.get("confidence", "INCONNU")
            net.add_node(node, label=node, color=color_map.get(conf, "#94a3b8"),
                         title=f"{data.get('category', '')} — confiance: {conf}")
        for u, v, data in G.edges(data=True):
            net.add_edge(u, v, title=data.get("dependency_type", ""), color="#cbd5e1")
        net.repulsion(node_distance=160, spring_length=160)
        html_path = "/tmp/graph_p01.html"
        net.write_html(html_path, open_browser=False, notebook=False)
        with open(html_path, "r", encoding="utf-8") as f:
            components.html(f.read(), height=570, scrolling=True)
        st.caption("🟢 Sauvegarde fiable · 🟠 A verifier · 🔴 Danger · ⚪ Non documente")
    except Exception as e:
        st.warning(f"Rendu interactif indisponible ({e}). Liste des aretes ci-dessous.")
        for u, v, data in G.edges(data=True):
            st.write(f"`{u}` → `{v}` ({data.get('dependency_type', '')}, confiance {data.get('confidence', '?')})")

    if BROKEN_CYCLES:
        st.error(f"Cycles detectes et rompus pour permettre le tri topologique : {BROKEN_CYCLES}")

    with st.expander("Couches techniques (reference)"):
        st.write(" → ".join(LAYER_ORDER))

# ==================================================== TOP ACTIONS URGENTES =
with tab_actions:
    if critical_actions:
        st.subheader("🧑‍🔧 A faire valider par un professionnel avant d'agir")
        for a in critical_actions:
            st.warning(f"**{a.title_human}** — {a.action_pro}")
    else:
        st.success("Aucune validation professionnelle bloquante identifiee.")

    st.divider()

    if high_risk_steps:
        st.subheader("🔴 Decisions a risque eleve, dans l'ordre du plan")
        for s in high_risk_steps:
            with st.container(border=True):
                st.markdown(f"**Etape {s.step} — {human_name(s.node)}**")
                st.caption(s.risk_consequence)
    else:
        st.info("Aucune decision classee a risque eleve actuellement.")

    st.divider()
    st.subheader(f"🔎 Incoherences detectees dans les documents ({len(ANOMALIES)})")
    for a in ANOMALIES:
        icon = {"CRITIQUE": "🔴", "HAUTE": "🟠", "MOYENNE": "🟡"}.get(a.severity, "⚪")
        with st.expander(f"{icon} {a.title_human}"):
            st.write(a.detail_human)
            st.markdown("---")
            st.caption(f"**Detail technique :** {a.detail_tech}")
            st.caption(f"**Sources :** {', '.join(a.sources)}")

# ===================================================== PLAN DE REPRISE =====
with tab_plan:
    st.subheader("Plan de redemarrage, dans l'ordre")
    for s in STEPS:
        st.markdown(f"**Etape {s.step}.** {explain_step(s)}")
        st.caption(
            f"{RISK_BADGE.get(s.risk_level, '⚪')} **{RISK_LABEL.get(s.risk_level, '?')} si on redemarre "
            f"maintenant** — {s.risk_consequence}"
        )
        with st.expander("Details techniques"):
            st.write(f"Systeme : `{s.node}` — categorie technique : {s.category} — criticite : {s.criticality}")
            st.write("Raisons de la confiance affichee :")
            for reason, source in zip(s.confidence_reasons, s.confidence_sources):
                st.write(f"- {reason} _(source: {source})_")
            if s.prerequisites:
                st.write("Doit etre restaure apres : " + ", ".join(f"`{p}`" for p in s.prerequisites))

    with st.expander("Vue tableau (reference technique)"):
        st.table([
            {
                "Etape": s.step, "Noeud": s.node, "Categorie": s.category, "Profondeur": s.depth,
                "Criticite": s.criticality, "Confiance": s.confidence, "Risque": RISK_LABEL.get(s.risk_level, "?"),
                "Prerequis": ", ".join(s.prerequisites),
            }
            for s in STEPS
        ])

# ======================================================== ASSISTANT/EXPORT =
with tab_assistant:
    st.subheader("Resume de la situation")
    if not llm_is_available():
        st.caption("ℹ️ Cle API Qwen non configuree — resume genere par gabarit deterministe (hors-ligne).")
    st.markdown(STATE.situation_summary)

    st.divider()
    st.subheader("💬 Poser une question au copilote")
    question = st.text_input("Ex: les clients peuvent-ils payer maintenant ?")
    if question:
        with st.spinner("Recherche de la reponse..."):
            answer = translator_agent.answer_question(STATE, question)
        st.markdown(answer)

    st.divider()
    st.subheader("📤 Exporter le plan")

    def build_export_markdown() -> str:
        lines = [
            f"# Plan de redemarrage — Processus {STATE.process_id}",
            "",
            "## Risque financier principal",
            f"Actif le plus expose : {RISK.asset} — Perte estimee : {eur(RISK.estimated_loss_eur)} "
            f"(source : {', '.join(RISK.sources)})",
            "",
            "## A faire valider par un professionnel",
        ]
        for a in critical_actions:
            lines.append(f"- {a.title_human} : {a.action_pro}")
        lines += ["", "## Plan de redemarrage, dans l'ordre"]
        for s in STEPS:
            lines.append(
                f"{s.step}. {human_name(s.node)} — confiance : {s.confidence} — "
                f"{RISK_LABEL.get(s.risk_level, '?')} : {s.risk_consequence}"
            )
        lines += ["", "## Incoherences detectees"]
        for a in ANOMALIES:
            lines.append(f"- [{a.severity}] {a.title_human} (sources : {', '.join(a.sources)})")
        return "\n".join(lines)

    st.download_button(
        "Telecharger la checklist (Markdown)",
        data=build_export_markdown(),
        file_name=f"plan_redemarrage_{STATE.process_id}.md",
        mime="text/markdown",
    )

    st.divider()
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
