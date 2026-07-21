# 🆘 SOS Redemarrage

Copilote de reprise apres cyberattaque pour NovaRetail (processus P01 —
commandes e-commerce). Traduit un diagnostic technique complexe en plan
d'action clair pour un gerant sans DSI.

## Principe

- **Les tools calculent** (deterministe, reproductible) : graphe de
  dependances (NetworkX), ordre de reconstruction, detection d'incoherences
  dans le corpus (croisement multi-CSV + RAG sur les documents texte),
  ecart RPO converti en euros.
- **Les agents specialises orchestrent et expliquent** : `graph_agent`,
  `anomaly_agent` et `risk_agent` appellent chacun leurs tools puis
  demandent a Qwen une courte explication ; `decider_agent` arbitre et
  synthetise leurs resultats ; `translator_agent` traduit la synthese en
  langage clair pour le gerant et repond aux questions libres. Qwen ne fait
  jamais de calcul, uniquement de la reformulation sourcee — et chaque agent
  fonctionne aussi hors-ligne (gabarits de secours) si `API_KEY` n'est pas
  configuree.

## Lancer l'app

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Optionnel — activer les reponses Qwen (sinon gabarits deterministes) :
copier `.env.example` en `.env` et renseigner `API_KEY`.

## Vos propres fichiers

L'interface accepte aussi vos propres exports CSV et documents `.docx`,
depuis la section "Vos fichiers" — noms de fichiers et noms de colonnes
peuvent etre completement differents de l'exemple NovaRetail.
`tools/schema_mapping.py` reconnait automatiquement a quel role (BIA,
CMDB, Backup_Catalog...) correspond chaque fichier depose, par similarite
de colonnes plutot que par nom exact, et affiche un rapport de
reconnaissance (fichier -> role detecte, confiance, roles non couverts).
Un role non retrouve n'est jamais devine : les analyses qui en dependent
sont simplement incompletes, jamais fausses.

Limite assumee : seule l'*ingestion* est generique. Les anomalies les plus
specifiques (ex. coffre-fort SECRETS-VAULT, IP DNS perimee) restent
calibrees sur les noms d'actifs du cas NovaRetail et ne se declencheront
que sur un corpus qui les reprend.

## Interface — deux pages

- **📂 Depot des sources** (`views/upload.py`) — depot des fichiers, description
  du probleme, bouton "Lancer le diagnostic". Calcule une fois et stocke le
  resultat en session.
- **📊 Dashboard** (`views/dashboard.py`) — ne recalcule jamais rien, lit
  uniquement le resultat stocke. Organise en 4 onglets pour rester lisible :
  **Cartographie** (graphe des dependances + etat des services par metier),
  **Top actions urgentes** (validations professionnelles bloquantes + decisions
  a risque eleve + anomalies), **Plan de reprise d'activite** (l'ordre complet,
  etape par etape, avec un badge de risque visible sur chaque decision),
  **Assistant & export** (resume, questions libres, export Markdown, traces
  des agents).
- Theme clair/professionnel configure dans `.streamlit/config.toml`.

## Structure

- `data/` — CSV du corpus NovaRetail (05_Datasets + 06_Incident) et `data/docs/`
  (.docx utilises par le RAG : PRA, rapport d'incident, notes de crise...)
- `core/` — schemas partages (`Finding`/`RebuildStep`/`RiskItem`, source et
  confiance obligatoires), client Qwen unique (`llm.py`), blackboard
  partage entre agents (`state.py`)
- `tools/` — fonctions deterministes appelees par les agents : construction
  du graphe, ordre de reconstruction, controles d'anomalies, calcul de
  risque, facteur de risque par decision (`decision_risk.py`), RAG (TF-IDF)
  sur les documents texte
- `agents/` — `graph_agent`, `anomaly_agent`, `risk_agent`, `decider_agent`,
  `translator_agent`, et `ingestion_agent` qui orchestre les cinq dans l'ordre
- `prompts/` — system prompt de chaque agent
- `app.py` — routeur `st.navigation` entre les deux pages de `views/`
