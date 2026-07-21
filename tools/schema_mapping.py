"""
Classification et normalisation heuristique de fichiers CSV arbitraires
vers les 13 "roles" que les tools savent exploiter (BIA, Backup_Catalog,
CMDB...), quels que soient le nom du fichier et les noms de colonnes
exacts utilises par l'entreprise qui fournit les donnees.

Principe: pour chaque role, on connait un petit nombre de colonnes
canoniques et une liste de synonymes plausibles par colonne. On score
chaque fichier uploade contre chaque role (fraction de colonnes
canoniques retrouvees) et on garde le meilleur score au-dessus d'un
seuil. En dessous du seuil, le fichier est un "role non reconnu" - il
n'est pas invente, il est simplement ignore par les checks qui en ont
besoin (ce qui degrade gracieusement plutot que de planter ou d'inventer
un mapping faux).
"""
import re
import unicodedata
from dataclasses import dataclass, field

import pandas as pd

MATCH_THRESHOLD = 0.55  # fraction minimale de colonnes canoniques retrouvees pour retenir un role


def normalize_header(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text


# role -> { colonne_canonique_attendue_par_les_tools: [synonymes normalises] }
ROLE_SCHEMAS: dict[str, dict[str, list[str]]] = {
    "BIA_Export": {
        "Process_ID": ["process_id", "processid", "id_processus", "proc_id", "process", "processus", "code_processus"],
        "Applications_Declared": ["applications_declared", "applications", "apps_declared", "declared_applications",
                                   "applications_declarees", "apps_declarees"],
        "RTO": ["rto", "recovery_time_objective", "delai_reprise", "temps_de_reprise", "delai_de_reprise"],
        "RPO": ["rpo", "recovery_point_objective", "perte_donnees_max", "perte_max_donnees", "perte_de_donnees_maximale"],
        "Max_Data_Loss_EUR_Hour": ["max_data_loss_eur_hour", "cost_per_hour", "eur_hour", "data_loss_cost_hour",
                                    "loss_eur_hour", "cout_horaire_eur", "cout_horaire", "cout_par_heure", "cout_heure"],
    },
    "Backup_Catalog": {
        "Asset": ["asset", "ci", "component", "system", "actif"],
        "Last_Successful_Backup": ["last_successful_backup", "last_backup", "backup_date", "derniere_sauvegarde"],
        "Immutability": ["immutability", "immutable", "is_immutable"],
        "RPO_Target": ["rpo_target", "target_rpo"],
        "RPO_Status": ["rpo_status", "rpo_compliance"],
        "Notes": ["notes", "comment", "comments", "remark", "remarks"],
    },
    "CMDB_Export": {
        "CI_ID": ["ci_id", "asset_id", "id"],
        "Name": ["name", "asset_name", "nom"],
        "Type": ["type", "category"],
        "Criticality": ["criticality", "priority", "criticite"],
        "RTO_Declared": ["rto_declared", "declared_rto"],
        "Notes": ["notes", "comment", "comments", "remark", "remarks"],
    },
    "Cyber_Vault_Catalog": {
        "Asset": ["asset", "ci", "component", "system", "actif"],
        "Vault_Copy_Timestamp": ["vault_copy_timestamp", "vault_timestamp", "copy_timestamp"],
        "Integrity_Check": ["integrity_check", "integrity", "integrity_status"],
    },
    "DNS_Export": {
        "Record": ["record", "hostname", "fqdn", "dns_record"],
        "Value": ["value", "ip", "ip_address", "target_value"],
        "Last_Changed": ["last_changed", "updated_at", "modified", "change_date"],
        "Notes": ["notes", "comment", "comments", "remark", "remarks"],
    },
    "Application_Dependencies": {
        "Source": ["source", "from", "src"],
        "Target": ["target", "to", "dest", "destination"],
        "Dependency_Type": ["dependency_type", "relation_type", "link_type"],
        "Criticality": ["criticality", "priority", "criticite"],
        "Confidence": ["confidence", "confidence_level", "trust"],
        "Source_Document": ["source_document", "source_doc", "reference"],
        "Notes": ["notes", "comment", "comments", "remark", "remarks"],
    },
    "Infrastructure_Dependencies": {
        "Asset": ["asset", "ci", "component", "system", "actif"],
        "Depends_On": ["depends_on", "dependency", "parent", "requires"],
        "Reason": ["reason", "justification", "raison"],
        "Criticality": ["criticality", "priority", "criticite"],
        "Notes": ["notes", "comment", "comments", "remark", "remarks"],
    },
    "Process_to_Applications_Map": {
        "Process_ID": ["process_id", "processid", "id_processus", "proc_id", "process"],
        "Application": ["application", "app", "system_name"],
        "Role": ["role", "function"],
        "Dependency_Level": ["dependency_level", "criticality_level", "importance"],
        "Source": ["source", "from", "src", "reference"],
    },
    "Impact_Assessment": {
        "Asset": ["asset", "ci", "component", "system", "actif"],
        "Status": ["status", "state", "etat"],
        "Confidence": ["confidence", "confidence_level", "trust"],
        "Immediate_Action": ["immediate_action", "action", "recommended_action"],
    },
    "Vulnerabilities_Extract": {
        "Asset": ["asset", "ci", "component", "system", "actif"],
        "Finding": ["finding", "issue", "vulnerability", "vulnerabilite"],
        "Severity": ["severity", "criticity", "level"],
        "Notes": ["notes", "comment", "comments", "remark", "remarks"],
    },
    "Ticket_Extract": {
        "Ticket_ID": ["ticket_id", "id_ticket", "reference"],
        "Asset": ["asset", "ci", "component", "system", "actif"],
        "Type": ["type", "category"],
        "Summary": ["summary", "description", "title"],
        "Notes": ["notes", "comment", "comments", "remark", "remarks"],
    },
    "VMware_Inventory": {
        "VM": ["vm", "virtual_machine", "server"],
        "Backup_Protected": ["backup_protected", "is_backed_up", "backup_status"],
        "Notes": ["notes", "comment", "comments", "remark", "remarks"],
    },
    "Monitoring_Alerts": {
        "Asset": ["asset", "ci", "component", "system", "related_ci"],
        "Message": ["message", "description", "alert_message"],
    },
}


def empty_table(role: str) -> pd.DataFrame:
    """DataFrame vide avec les colonnes canoniques attendues - utilisee quand
    un role n'a pas ete reconnu parmi les fichiers uploades, pour que les
    tools qui le lisent degradent gracieusement (iterer sur rien) plutot
    que de planter avec un KeyError."""
    return pd.DataFrame(columns=list(ROLE_SCHEMAS[role].keys()))


def get_table(tables: dict[str, pd.DataFrame], role: str) -> pd.DataFrame:
    """Renvoie la table pour ce role, en garantissant que toutes les
    colonnes canoniques existent (remplies a NA si non retrouvees dans le
    fichier source) - meme un role partiellement reconnu ne fait donc
    jamais planter un `df["Colonne"]` en aval."""
    canonical_cols = list(ROLE_SCHEMAS[role].keys())
    df = tables.get(role)
    if df is None:
        return pd.DataFrame(columns=canonical_cols)
    missing = [c for c in canonical_cols if c not in df.columns]
    if missing:
        df = df.copy()
        for c in missing:
            df[c] = pd.NA
    return df


@dataclass
class ClassificationResult:
    filename: str
    role: str | None
    score: float
    column_mapping: dict[str, str] = field(default_factory=dict)  # canonique -> colonne reelle du fichier


def _token_match(normalized_name: str, alias: str) -> bool:
    """Alias present comme mot entier dans un nom compose (ex:
    'composant_source' matche l'alias 'source'). N'est utilisee qu'en
    repli, apres avoir cherche une correspondance exacte, pour eviter
    qu'un alias generique ('source') ne vole une colonne qui correspond
    exactement a un autre champ canonique ('Source_Document')."""
    tokens = normalized_name.split("_")
    return alias in tokens or all(t in tokens for t in alias.split("_"))


def score_role(columns_normalized: dict[str, str], role: str) -> tuple[float, dict[str, str]]:
    """columns_normalized: {nom_normalise: nom_original_dans_le_fichier}.

    Deux passes pour eviter les collisions entre alias generiques: on
    cherche d'abord une correspondance exacte pour tous les champs
    canoniques, puis seulement en repli une correspondance partielle
    (mot dans un nom compose). Une meme colonne reelle n'est jamais
    assignee a deux champs canoniques differents (`used`).
    """
    schema = ROLE_SCHEMAS[role]
    mapping: dict[str, str] = {}
    used: set[str] = set()

    # passe 1: correspondance exacte uniquement
    for canonical, aliases in schema.items():
        for alias in aliases:
            actual = columns_normalized.get(alias)
            if actual is not None and actual not in used:
                mapping[canonical] = actual
                used.add(actual)
                break

    # passe 2: correspondance partielle (mot dans un nom compose), pour les
    # champs canoniques encore non resolus
    for canonical, aliases in schema.items():
        if canonical in mapping:
            continue
        for alias in aliases:
            match = next(
                (norm for norm, actual in columns_normalized.items() if actual not in used and _token_match(norm, alias)),
                None,
            )
            if match is not None:
                actual = columns_normalized[match]
                mapping[canonical] = actual
                used.add(actual)
                break

    return len(mapping) / len(schema), mapping


def classify_file(filename: str, df: pd.DataFrame) -> ClassificationResult:
    columns_normalized = {normalize_header(c): c for c in df.columns}
    best_role, best_score, best_mapping = None, 0.0, {}
    for role in ROLE_SCHEMAS:
        score, mapping = score_role(columns_normalized, role)
        if score > best_score:
            best_role, best_score, best_mapping = role, score, mapping
    if best_score < MATCH_THRESHOLD:
        return ClassificationResult(filename=filename, role=None, score=best_score, column_mapping={})
    return ClassificationResult(filename=filename, role=best_role, score=best_score, column_mapping=best_mapping)


def apply_mapping(df: pd.DataFrame, column_mapping: dict[str, str]) -> pd.DataFrame:
    """Renomme les colonnes reconnues vers leur nom canonique, garde les autres telles quelles."""
    rename = {actual: canonical for canonical, actual in column_mapping.items()}
    return df.rename(columns=rename)


def classify_and_normalize(uploads: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], list[ClassificationResult]]:
    """uploads: {nom_de_fichier: DataFrame brut}. Renvoie (tables_par_role, rapport)."""
    tables: dict[str, pd.DataFrame] = {}
    report: list[ClassificationResult] = []
    for filename, df in uploads.items():
        result = classify_file(filename, df)
        report.append(result)
        if result.role is not None:
            normalized = apply_mapping(df, result.column_mapping)
            # si deux fichiers matchent le meme role, on garde celui au meilleur score
            if result.role not in tables or result.score > next(
                (r.score for r in report if r.role == result.role and r.filename != filename), 0
            ):
                tables[result.role] = normalized
    return tables, report
