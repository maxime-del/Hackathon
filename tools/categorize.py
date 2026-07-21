"""
Classement des noeuds techniques en categories et enrichissement de
chaque noeud avec les faits bruts qui le concernent (CMDB, sauvegardes,
coffre cyber, evaluation d'impact, vulnerabilites).

Tout est deterministe: on ne fait ici que des jointures/lookups sur les
dataframes charges par data_loader.load_all(). La categorie n'est PAS un
dictionnaire code en dur par nom d'actif (ca ne marcherait que sur le
corpus NovaRetail) - elle est deduite par mots-cles generiques a partir
du champ CMDB "Type" (ex: "Database Oracle" -> Donnees, "DNS" -> Reseau),
donc reutilisable sur n'importe quel export CMDB.
"""
from dataclasses import dataclass, field
import pandas as pd

from tools.schema_mapping import get_table

# Regles generiques: mots-cles cherches dans le champ CMDB "Type" (en
# minuscule). La premiere regle qui matche l'emporte. Aucun nom d'actif
# n'apparait ici - uniquement du vocabulaire d'infrastructure generique.
_CATEGORY_RULES: list[tuple[list[str], str]] = [
    (["directory", "identity", "iam", "sso", "active directory"], "Identite"),
    (["dns", "ntp", "firewall", "vpn", "network", "load balanc"], "Reseau / DNS"),
    (["pki", "certificat", "certificate", "ca "], "Certificats (PKI)"),
    (["secret", "vault"], "Coffre-fort secrets"),
    (["monitoring", "siem", "xdr", "security"], "Securite / Supervision"),
    (["backup"], "Sauvegardes"),
    (["database", "db2", "oracle", "postgres", "sql server", "data warehouse", "dwh"], "Donnees"),
    (["vmware", "vcenter", "kubernetes", "cluster", "server", "compute", "esx"], "Serveurs (compute)"),
    (["middleware", "message", "broker", " mq", "smtp", "cache", "redis"], "Integration & messagerie"),
    (["application", "saas", "external service", "api"], "Applications"),
]

# Ordre d'affichage des couches (categories generiques, reutilisable sur
# n'importe quel corpus - contrairement aux anciennes categories "metier"
# type "Boutique"/"Paiement" qui etaient specifiques a NovaRetail).
LAYER_ORDER = [
    "Identite", "Reseau / DNS", "Certificats (PKI)", "Coffre-fort secrets",
    "Securite / Supervision", "Sauvegardes", "Serveurs (compute)", "Donnees",
    "Applications", "Integration & messagerie", "Autre",
]

CATEGORY_ICONS = {
    "Identite": "🪪", "Reseau / DNS": "🌐", "Certificats (PKI)": "🔏",
    "Coffre-fort secrets": "🔐", "Securite / Supervision": "🛡️", "Sauvegardes": "💾",
    "Serveurs (compute)": "🖥️", "Donnees": "🗄️", "Applications": "🧩",
    "Integration & messagerie": "🔗", "Autre": "❔",
}


def human_category(node: str, cmdb_type: str | None = None) -> str:
    """Categorie generique deduite du type CMDB (mots-cles). Sans type
    documente, l'actif tombe dans 'Autre' plutot que d'etre devine par
    son nom - on ne veut pas remplacer un dictionnaire code en dur par
    un autre."""
    haystack = f"{cmdb_type or ''}".lower()
    if not haystack.strip():
        return "Autre"
    for keywords, category in _CATEGORY_RULES:
        if any(kw in haystack for kw in keywords):
            return category
    return "Autre"


@dataclass
class NodeFacts:
    node: str
    cmdb_type: str | None = None
    cmdb_criticality: str | None = None
    in_cmdb: bool = False
    backup_rows: list[dict] = field(default_factory=list)
    vault_rows: list[dict] = field(default_factory=list)
    impact_status: str | None = None
    impact_confidence: str | None = None
    impact_action: str | None = None
    vuln_rows: list[dict] = field(default_factory=list)


def build_node_facts(tables: dict[str, pd.DataFrame]) -> dict[str, NodeFacts]:
    cmdb = get_table(tables, "CMDB_Export")
    backup = get_table(tables, "Backup_Catalog")
    vault = get_table(tables, "Cyber_Vault_Catalog")
    impact = get_table(tables, "Impact_Assessment")
    vulns = get_table(tables, "Vulnerabilities_Extract")

    facts: dict[str, NodeFacts] = {}

    def get(node: str) -> NodeFacts:
        if node not in facts:
            facts[node] = NodeFacts(node=node)
        return facts[node]

    for _, row in cmdb.iterrows():
        name = row.get("Name")
        if pd.isna(name):
            continue
        f = get(name)
        f.cmdb_type = row.get("Type")
        f.cmdb_criticality = row.get("Criticality")
        f.in_cmdb = True

    for _, row in backup.iterrows():
        asset = row.get("Asset")
        if pd.isna(asset):
            continue
        f = get(asset)
        f.backup_rows.append(row.to_dict())

    for _, row in vault.iterrows():
        asset = row.get("Asset")
        if pd.isna(asset):
            continue
        f = get(asset)
        f.vault_rows.append(row.to_dict())

    for _, row in impact.iterrows():
        asset_raw = row.get("Asset")
        if pd.isna(asset_raw):
            continue
        for asset in str(asset_raw).split("/"):
            f = get(asset.strip())
            f.impact_status = row.get("Status")
            f.impact_confidence = row.get("Confidence")
            f.impact_action = row.get("Immediate_Action")

    for _, row in vulns.iterrows():
        asset = row.get("Asset")
        if pd.isna(asset):
            continue
        f = get(asset)
        f.vuln_rows.append(row.to_dict())

    return facts
