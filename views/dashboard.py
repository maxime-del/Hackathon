"""
SOS Redémarrage - Page 2/2 : Dashboard.

Ne recalcule jamais rien : lit uniquement l'EngineState déposé en
session_state par la page de dépôt (app.py), à une exception près - le
simulateur "et si" (onglet dédié), qui rejoue des calculs déjà
déterministes avec une hypothèse différente, sans jamais toucher à
l'EngineState stocké ni relancer le pipeline. Organisé en onglets pour
rester lisible sans un long défilement unique : Cartographie (graphe +
état des services), Top actions urgentes (ce qu'il faut valider/traiter
en premier), Plan de reprise (l'ordre complet, avec suivi d'avancement),
Simulateur (hypothèses de délai / panne supplémentaire), Assistant
(résumé, questions libres, export).
"""
import streamlit as st

from agents import translator_agent
from core.format import eur
from core.llm import llm_is_available
from tools.categorize import CATEGORY_ICONS, LAYER_ORDER
from tools.narrate import category_status_color, explain_step, human_name, status_kind_human
from tools.simulator import simulate_extra_delay, simulate_extra_failure

RISK_BADGE = {"FAIBLE": "🟢", "MOYEN": "🟠", "ELEVE": "🔴"}
RISK_LABEL = {"FAIBLE": "Risque faible si redémarré maintenant", "MOYEN": "Risque moyen si redémarré maintenant",
              "ELEVE": "Risque élevé si redémarré maintenant"}
RISK_ORDER = {"FAIBLE": 0, "MOYEN": 1, "ELEVE": 2}

# Messages d'encouragement affichés selon l'avancement coché par
# l'utilisateur dans le plan - dimension volontairement positive : cocher
# une case doit donner une sensation de progrès tangible, pas juste
# ajouter une ligne barrée dans une liste.
PROGRESS_MESSAGES = [
    (1.0, "🎉 Reprise complète ! Toutes les étapes du plan sont sécurisées."),
    (0.75, "💪 Presque terminé, la boutique redémarre bientôt."),
    (0.5, "🚀 Vous êtes à mi-chemin, chaque étape cochée réduit le risque."),
    (0.25, "👍 Bon départ, continuez dans l'ordre du plan."),
    (0.0, "▶️ Cochez une étape dès qu'elle est réellement terminée pour suivre votre avancement."),
]


def _pourquoi(reasons: list[str], sources: list[str], key: str) -> None:
    """Explicabilité uniforme : partout où un chiffre ou un statut est
    affiché, le lecteur doit pouvoir déplier "pourquoi" pour voir la
    chaîne de faits/sources qui le justifie - jamais une affirmation
    non sourcée."""
    if not reasons:
        return
    with st.expander("🔎 Pourquoi je vous dis ça ?"):
        for reason, source in zip(reasons, sources or [""] * len(reasons)):
            st.write(f"- {reason}" + (f" _(source : {source})_" if source else ""))


if "engine_state" not in st.session_state:
    st.title("📊 Dashboard")
    st.info("Aucun diagnostic en mémoire. Retournez sur la page **Dépôt des sources** pour en lancer un.")
    if st.button("📂 Aller au dépôt des sources", type="primary"):
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

# Suivi d'avancement coché par l'utilisateur (dimension psychologique
# positive) - persiste tant que la session Streamlit vit, jamais écrit
# dans l'EngineState (ce n'est pas un fait calculé, c'est une action humaine).
# Synchronisé ICI, avant tout affichage : Streamlit met à jour l'état d'une
# case à cocher AVANT de relancer le script, donc lire les clés `done_*`
# maintenant (plutôt qu'au moment de dessiner chaque case, plus bas) évite
# que la barre de progression affiche un tour de retard sur le clic.
completed_steps: set[int] = st.session_state.setdefault("completed_steps", set())
for _s in STEPS:
    _key = f"done_{_s.step}"
    if _key in st.session_state:
        (completed_steps.add if st.session_state[_key] else completed_steps.discard)(_s.step)
progress_fraction = len(completed_steps) / len(STEPS) if STEPS else 0.0

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
st.caption("Photographie de la situation au moment du diagnostic. Relancez le diagnostic depuis la page de dépôt pour l'actualiser.")

risk_neutralized = RISK.data_sufficient and any(s.node == RISK.asset for s in STEPS if s.step in completed_steps)
if RISK.data_sufficient and risk_neutralized:
    st.success(
        f"✅ **Risque financier neutralisé** — {eur(RISK.estimated_loss_eur)} évités sur **{RISK.asset}**, "
        f"l'étape correspondante du plan a été cochée comme terminée."
    )
elif RISK.data_sufficient:
    st.error(
        f"⚠️ **Perte financière estimée : {eur(RISK.estimated_loss_eur)}** — actif le plus exposé : **{RISK.asset}**, "
        f"dernière sauvegarde fiable le **{RISK.last_reliable_backup:%d/%m/%Y %H:%M}** "
        f"(~{RISK.gap_hours:.0f}h avant l'incident). {RISK.confidence_note}"
    )
    _pourquoi(
        [f"Écart de {RISK.gap_hours:.0f}h entre la dernière sauvegarde fiable et l'incident, "
         f"valorisé au coût horaire de perte du processus ({eur(RISK.eur_per_hour)}/h)."] + [RISK.confidence_note],
        RISK.sources, key="risk_banner",
    )
    if len(STATE.risk_items) > 1:
        st.caption(
            "Autres actifs également en violation de RPO : " + ", ".join(
                f"{r.asset} ({eur(r.estimated_loss_eur)})" for r in STATE.risk_items[1:]
            )
        )
else:
    st.warning(f"ℹ️ {RISK.confidence_note}")

kpi_cols = st.columns(5)
kpi_cols[0].metric("Étapes du plan", len(STEPS))
kpi_cols[1].metric("Étapes bloquantes", len(blocking_steps))
kpi_cols[2].metric("Décisions à risque élevé", len(high_risk_steps))
kpi_cols[3].metric("Anomalies critiques", len(critical_findings))
kpi_cols[4].metric(
    "Perte financière" if not risk_neutralized else "Perte évitée",
    eur(RISK.estimated_loss_eur) if RISK.data_sufficient else "n/a",
)

st.caption(
    f"Répartition du risque par décision : 🟢 {len(low_risk_steps)} faible · "
    f"🟠 {len(medium_risk_steps)} moyen · 🔴 {len(high_risk_steps)} élevé"
)
st.progress(progress_fraction, text=f"Avancement de la reprise : {len(completed_steps)}/{len(STEPS)} étape(s) sécurisée(s)")

st.divider()

tab_map, tab_actions, tab_plan, tab_sim, tab_assistant = st.tabs([
    "🗺️ Cartographie", "🚨 Top actions urgentes", "📋 Plan de reprise d'activité",
    "🧪 Simulateur \"et si\"", "💬 Assistant & export",
])

# ============================================================ CARTOGRAPHIE =
with tab_map:
    st.subheader("État des services")
    st.caption(
        "🛑 Compromis = hors service, ne pas reconnecter · 🔴 Risqué à redémarrer = la sauvegarde n'est pas fiable · "
        "🟠 À vérifier · ⚪ Non documenté · 🟢 Fiable. Cliquez sur *Détail* pour voir les systèmes concernés."
    )

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
                st.caption(f"{len(nodes_in_group)} élément(s)")
                if st.button("🔍 Détail", key=f"cat_btn_{label}", use_container_width=True):
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
            st.markdown(f"#### 🔎 Détail — {selected_category}")
            if not nodes_in_group:
                st.caption("Aucun élément dans cette catégorie pour ce processus.")
            for s in nodes_in_group:
                status_icon, status_label, status_explain = status_kind_human(s.status_kind)
                st.markdown(
                    f"{status_icon} **{human_name(s.node)}** — {status_label} "
                    f"({RISK_BADGE.get(s.risk_level, '⚪')} {RISK_LABEL.get(s.risk_level, 'risque non évalué')})"
                )
                st.caption(status_explain)
                st.caption(s.risk_consequence)
                _pourquoi(s.confidence_reasons, s.confidence_sources, key=f"detail_{s.node}")

    st.divider()
    st.subheader("Graphe de dépendances")
    try:
        from pyvis.network import Network
        import streamlit.components.v1 as components

        net = Network(height="550px", width="100%", directed=True, notebook=False, bgcolor="#ffffff", font_color="#0f172a")
        color_map = {
            "COMPROMIS": "#7f1d1d", "RESTAURATION_RISQUEE": "#dc2626",
            "A_VERIFIER": "#f59e0b", "NON_DOCUMENTE": "#94a3b8", "FIABLE": "#16a34a",
        }
        for node in G.nodes:
            data = G.nodes[node]
            kind = data.get("status_kind", "FIABLE")
            _, status_label, status_explain = status_kind_human(kind)
            net.add_node(node, label=node, color=color_map.get(kind, "#94a3b8"),
                         title=f"{data.get('category', '')} — {status_label} : {status_explain}")
        for u, v, data in G.edges(data=True):
            net.add_edge(u, v, title=data.get("dependency_type", ""), color="#cbd5e1")
        net.repulsion(node_distance=160, spring_length=160)
        html_path = "/tmp/graph_p01.html"
        net.write_html(html_path, open_browser=False, notebook=False)
        with open(html_path, "r", encoding="utf-8") as f:
            components.html(f.read(), height=570, scrolling=True)
        st.caption(
            "🟢 Fiable · 🟠 À vérifier · 🔴 Risqué à redémarrer (sauvegarde non fiable) · "
            "🛑 Compromis (hors service) · ⚪ Non documenté — survolez un noeud pour le détail."
        )
    except Exception as e:
        st.warning(f"Rendu interactif indisponible ({e}). Liste des arêtes ci-dessous.")
        for u, v, data in G.edges(data=True):
            st.write(f"`{u}` → `{v}` ({data.get('dependency_type', '')}, confiance {data.get('confidence', '?')})")

    if BROKEN_CYCLES:
        st.error(f"Cycles détectés et rompus pour permettre le tri topologique : {BROKEN_CYCLES}")

    with st.expander("Couches techniques (référence)"):
        st.write(" → ".join(LAYER_ORDER))

# ==================================================== TOP ACTIONS URGENTES =
with tab_actions:
    if critical_actions:
        st.subheader("🧑‍🔧 À faire valider par un professionnel avant d'agir")
        for a in critical_actions:
            st.warning(f"**{a.title_human}** — {a.action_pro}")
            _pourquoi([a.detail_human] if a.sources else [], a.sources, key=f"action_{a.id}")
    else:
        st.success("Aucune validation professionnelle bloquante identifiée.")

    st.divider()

    if high_risk_steps:
        st.subheader("🔴 Décisions à risque élevé, dans l'ordre du plan")
        for s in high_risk_steps:
            status_icon, status_label, _ = status_kind_human(s.status_kind)
            with st.container(border=True):
                st.markdown(f"**Étape {s.step} — {human_name(s.node)}** {status_icon} _{status_label}_")
                st.caption(s.risk_consequence)
                _pourquoi(s.confidence_reasons, s.confidence_sources, key=f"actions_{s.node}")
    else:
        st.info("Aucune décision classée à risque élevé actuellement.")

    st.divider()
    st.subheader(f"🔎 Incohérences détectées dans les documents ({len(ANOMALIES)})")
    for a in ANOMALIES:
        icon = {"CRITIQUE": "🔴", "HAUTE": "🟠", "MOYENNE": "🟡"}.get(a.severity, "⚪")
        with st.expander(f"{icon} {a.title_human}"):
            st.write(a.detail_human)
            st.markdown("---")
            st.caption(f"**Détail technique :** {a.detail_tech}")
            st.caption(f"**Sources :** {', '.join(a.sources)}")

# ===================================================== PLAN DE REPRISE =====
with tab_plan:
    st.subheader("Plan de redémarrage, dans l'ordre")

    message = next(msg for threshold, msg in PROGRESS_MESSAGES if progress_fraction >= threshold)
    st.progress(progress_fraction, text=f"{len(completed_steps)}/{len(STEPS)} étape(s) cochée(s) comme terminées")
    st.caption(message)
    st.divider()

    for s in STEPS:
        status_icon, status_label, status_explain = status_kind_human(s.status_kind)
        done = s.step in completed_steps
        col_check, col_body = st.columns([1, 11])
        with col_check:
            checked = st.checkbox("Fait", key=f"done_{s.step}", value=done, label_visibility="collapsed")
            if checked and s.step not in completed_steps:
                completed_steps.add(s.step)
            elif not checked and s.step in completed_steps:
                completed_steps.discard(s.step)
        with col_body:
            label = f"**Étape {s.step}.** {explain_step(s)}"
            st.markdown(f"~~{label}~~" if checked else label)
            st.caption(
                f"{status_icon} **{status_label}** — {status_explain}"
            )
            st.caption(
                f"{RISK_BADGE.get(s.risk_level, '⚪')} **{RISK_LABEL.get(s.risk_level, '?')}** — {s.risk_consequence}"
            )
            with st.expander("🔎 Pourquoi je vous dis ça ?"):
                st.write(f"Système : `{s.node}` — catégorie technique : {s.category} — criticité : {s.criticality}")
                st.write("Raisons du statut affiché :")
                for reason, source in zip(s.confidence_reasons, s.confidence_sources):
                    st.write(f"- {reason} _(source : {source})_")
                if s.prerequisites:
                    st.write("Doit être restauré après : " + ", ".join(f"`{p}`" for p in s.prerequisites))

    with st.expander("Vue tableau (référence technique)"):
        st.table([
            {
                "Étape": s.step, "Noeud": s.node, "Catégorie": s.category, "Profondeur": s.depth,
                "Criticité": s.criticality, "Statut": status_kind_human(s.status_kind)[1],
                "Risque": RISK_LABEL.get(s.risk_level, "?"), "Prérequis": ", ".join(s.prerequisites),
            }
            for s in STEPS
        ])

# ============================================================ SIMULATEUR ===
with tab_sim:
    st.subheader("🧪 Simulateur \"et si\"")
    st.caption(
        "Explorez une hypothèse sans relancer le diagnostic : les calculs ci-dessous rejouent instantanément "
        "les mêmes formules que le plan, avec une donnée différente. Rien n'est envoyé au modèle IA, rien n'est "
        "modifié dans le diagnostic déjà affiché dans les autres onglets."
    )

    st.markdown("### ⏳ Et si on attend avant d'agir ?")
    st.caption(
        "Chaque heure de plus avant de traiter les actifs à risque prolonge l'écart entre la dernière sauvegarde "
        "fiable et l'incident, donc la perte potentielle."
    )
    extra_hours = st.slider("Heures d'attente supplémentaires avant intervention", 0, 72, 0, step=1)
    if extra_hours > 0 and RISK.data_sufficient:
        sim = simulate_extra_delay(STATE.risk_items, extra_hours)
        c1, c2, c3 = st.columns(3)
        c1.metric("Perte totale maintenant", eur(sim.total_before_eur))
        c2.metric(f"Perte totale dans {extra_hours}h", eur(sim.total_after_eur), delta=eur(sim.delta_eur))
        c3.metric("Coût de l'attente, par heure", eur(sim.eur_per_extra_hour) + "/h")
        st.error(
            f"⚠️ Attendre {extra_hours}h de plus avant d'agir coûterait environ **{eur(sim.delta_eur)}** de plus, "
            f"soit {eur(sim.eur_per_extra_hour)} par heure d'inaction sur les actifs déjà exposés."
        )
        _pourquoi(
            ["Recalcul de `perte = (écart RPO déjà connu + heures d'attente simulées) × coût horaire du BIA`, "
             "pour chaque actif déjà en violation de RPO — même formule que le plan, hypothèse de délai en plus."],
            ["tools/risk_calc.py", "tools/simulator.py"], key="sim_delay",
        )
    elif not RISK.data_sufficient:
        st.info("Pas de risque financier chiffré sur ce corpus : rien à simuler sur ce levier.")
    else:
        st.caption("Déplacez le curseur pour voir l'impact chiffré de l'attente.")

    st.divider()

    st.markdown("### 💥 Et si un actif de plus tombait en panne ?")
    st.caption(
        "Sélectionnez un système du plan : on lit dans le graphe tout ce qui en dépend, pour voir ce qui resterait "
        "bloqué si cet actif s'ajoutait à la liste des systèmes compromis ou peu fiables."
    )
    node_options = [s.node for s in STEPS]
    if node_options:
        picked = st.selectbox(
            "Système à simuler en panne supplémentaire",
            node_options, format_func=lambda n: f"{n} — {human_name(n)}",
        )
        fail_sim = simulate_extra_failure(G, STEPS, picked)
        if fail_sim.already_at_risk:
            st.info(f"**{human_name(picked)}** est déjà classé à risque dans le diagnostic actuel.")
        if fail_sim.newly_blocked:
            st.error(
                f"⚠️ Si **{human_name(picked)}** tombe en panne, **{len(fail_sim.newly_blocked)} système(s)** "
                f"qui en dépendent ne pourront pas redémarrer tant qu'il n'est pas traité, dont "
                f"**{len(fail_sim.newly_blocked_previously_safe)}** actuellement classés fiables."
            )
            st.write(", ".join(f"`{n}` ({human_name(n)})" for n in fail_sim.newly_blocked))
        else:
            st.success(f"Aucun système ne dépend de **{human_name(picked)}** — une panne isolée resterait sans effet en cascade.")
        _pourquoi(
            ["Les systèmes listés sont les ancêtres de l'actif choisi dans le graphe de dépendances déjà "
             "construit (convention : A -> B signifie \"A dépend de B\") - lecture directe, aucune nouvelle donnée."],
            ["tools/graph_builder.py", "tools/simulator.py"], key="sim_failure",
        )

# ======================================================== ASSISTANT/EXPORT =
with tab_assistant:
    st.subheader("Résumé de la situation")
    if not llm_is_available():
        st.caption("ℹ️ Clé API Qwen non configurée — résumé généré par gabarit déterministe (hors-ligne).")
    st.markdown(STATE.situation_summary)

    st.divider()
    st.subheader("💬 Poser une question au copilote")
    question = st.text_input("Ex : les clients peuvent-ils payer maintenant ?")
    if question:
        with st.spinner("Recherche de la réponse..."):
            answer = translator_agent.answer_question(STATE, question)
        st.markdown(answer)

    st.divider()
    st.subheader("📤 Exporter le plan")

    def build_export_markdown() -> str:
        lines = [
            f"# Plan de redémarrage — Processus {STATE.process_id}",
            "",
            "## Risque financier principal",
            f"Actif le plus exposé : {RISK.asset} — Perte estimée : {eur(RISK.estimated_loss_eur)} "
            f"(source : {', '.join(RISK.sources)})",
            "",
            "## À faire valider par un professionnel",
        ]
        for a in critical_actions:
            lines.append(f"- {a.title_human} : {a.action_pro}")
        lines += ["", "## Plan de redémarrage, dans l'ordre"]
        for s in STEPS:
            done_mark = "[x]" if s.step in completed_steps else "[ ]"
            lines.append(
                f"{done_mark} {s.step}. {human_name(s.node)} — statut : {status_kind_human(s.status_kind)[1]} — "
                f"{RISK_LABEL.get(s.risk_level, '?')} : {s.risk_consequence}"
            )
        lines += ["", "## Incohérences détectées"]
        for a in ANOMALIES:
            lines.append(f"- [{a.severity}] {a.title_human} (sources : {', '.join(a.sources)})")
        return "\n".join(lines)

    st.download_button(
        "Télécharger la checklist (Markdown)",
        data=build_export_markdown(),
        file_name=f"plan_redemarrage_{STATE.process_id}.md",
        mime="text/markdown",
    )

    st.divider()
    st.subheader("🤖 Traces des agents spécialisés")
    st.caption("Chaque spécialiste ne reçoit que les résultats des tools déterministes qui le concernent.")
    with st.expander("graph_agent"):
        st.write(STATE.graph_narrative)
    with st.expander("anomaly_agent"):
        st.write(STATE.anomaly_narrative)
    with st.expander("risk_agent"):
        st.write(STATE.risk_narrative)
    with st.expander("decider_agent (synthèse finale)"):
        st.write(STATE.decider_narrative)
