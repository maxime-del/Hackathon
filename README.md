# 🆘 SOS Redémarrage

Copilote de reprise après cyberattaque pour NovaRetail (processus P01 —
commandes e-commerce). Traduit un diagnostic technique complexe en plan
d'action clair pour un gérant sans DSI.

## Principe

- **Les tools calculent** (déterministe, reproductible) : graphe de
  dépendances (NetworkX), ordre de reconstruction, détection d'incohérences
  dans le corpus (croisement multi-CSV + RAG sur les documents texte),
  écart RPO converti en euros.
- **Les agents spécialisés orchestrent et expliquent** : `graph_agent`,
  `anomaly_agent` et `risk_agent` appellent chacun leurs tools puis
  demandent à Qwen une courte explication ; `decider_agent` arbitre et
  synthétise leurs résultats ; `translator_agent` traduit la synthèse en
  langage clair pour le gérant et répond aux questions libres. Qwen ne fait
  jamais de calcul, uniquement de la reformulation sourcée — et chaque agent
  fonctionne aussi hors-ligne (gabarits de secours) si `API_KEY` n'est pas
  configurée.
- **Chaque affirmation est explicable** : partout dans le dashboard, un
  encart "🔎 Pourquoi je vous dis ça ?" déplie les faits et les sources
  exacts qui ont produit le chiffre ou le statut affiché — jamais une
  affirmation sans provenance visible.
- **Le statut d'un actif dit précisément pourquoi il est rouge** : un
  actif "🛑 Compromis" (déclaré atteint, hors service) n'a pas la même
  implication qu'un actif "🔴 Risqué à redémarrer" (probablement sain,
  mais la sauvegarde disponible n'est pas fiable) — voir
  `tools/graph_builder.py::score_node_confidence` et `tools/narrate.py`.

## Lancer l'app

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Optionnel — activer les réponses Qwen (sinon gabarits déterministes) :
copier `.env.example` en `.env` et renseigner `API_KEY`.

## Vos propres fichiers

L'interface accepte aussi vos propres exports CSV et documents `.docx`,
depuis la section "Vos fichiers" — noms de fichiers et noms de colonnes
peuvent être complètement différents de l'exemple NovaRetail.
`tools/schema_mapping.py` reconnaît automatiquement à quel rôle (BIA,
CMDB, Backup_Catalog...) correspond chaque fichier déposé, par similarité
de colonnes plutôt que par nom exact, et affiche un rapport de
reconnaissance (fichier -> rôle détecté, confiance, rôles non couverts).
Un rôle non retrouvé n'est jamais deviné : les analyses qui en dépendent
sont simplement incomplètes, jamais fausses.

Limite assumée : seule l'*ingestion* est générique. Les anomalies les plus
spécifiques (ex. coffre-fort SECRETS-VAULT, IP DNS périmée) restent
calibrées sur les noms d'actifs du cas NovaRetail et ne se déclencheront
que sur un corpus qui les reprend.

## Interface — deux pages

- **📂 Dépôt des sources** (`views/upload.py`) — dépôt des fichiers, description
  du problème, bouton "Lancer le diagnostic". Calcule une fois et stocke le
  résultat en session.
- **📊 Dashboard** (`views/dashboard.py`) — ne recalcule jamais rien, lit
  uniquement le résultat stocké. Organisé en 5 onglets pour rester lisible :
  **Cartographie** (graphe des dépendances + état des services par métier,
  distinguant explicitement 🛑 compromis / 🔴 risqué à redémarrer / 🟠 à
  vérifier / ⚪ non documenté / 🟢 fiable), **Top actions urgentes**
  (validations professionnelles bloquantes + décisions à risque élevé +
  anomalies), **Plan de reprise d'activité** (l'ordre complet, étape par
  étape, avec une case à cocher par étape et une barre d'avancement),
  **Simulateur "et si"** (impact chiffré d'un délai avant intervention, ou
  d'une panne supplémentaire, recalculé instantanément sans nouvel appel
  IA), **Assistant & export** (résumé, questions libres, export Markdown,
  traces des agents).
- Thème clair/professionnel configuré dans `.streamlit/config.toml`.

## Structure

- `data/` — CSV du corpus NovaRetail (05_Datasets + 06_Incident) et `data/docs/`
  (.docx utilisés par le RAG : PRA, rapport d'incident, notes de crise...)
- `core/` — schémas partagés (`Finding`/`RebuildStep`/`RiskItem`, source et
  confiance obligatoires), client Qwen unique (`llm.py`), blackboard
  partagé entre agents (`state.py`)
- `tools/` — fonctions déterministes appelées par les agents : construction
  du graphe (avec distinction compromis/risqué par noeud), ordre de
  reconstruction, contrôles d'anomalies, calcul de risque, facteur de
  risque par décision (`decision_risk.py`), recalculs instantanés du
  simulateur "et si" (`simulator.py`), RAG (TF-IDF) sur les documents texte
- `agents/` — `graph_agent`, `anomaly_agent`, `risk_agent`, `decider_agent`,
  `translator_agent`, et `ingestion_agent` qui orchestre les cinq dans l'ordre
- `prompts/` — system prompt de chaque agent
- `app.py` — routeur `st.navigation` entre les deux pages de `views/`
