"""
Classement des noeuds techniques en categories humaines (persona "Karim")
et enrichissement de chaque noeud avec les faits bruts qui le concernent
(CMDB, sauvegardes, coffre cyber, evaluation d'impact, vulnerabilites).

Tout est deterministe: on ne fait ici que des jointures/lookups sur les
dataframes charges par data_loader.load_all().
"""
from dataclasses import dataclass, field
import pandas as pd

from tools.schema_mapping import get_table

# Categorie humaine par noeud technique (heuristique fixe, basee sur le
# vocabulaire metier NovaRetail). Un noeud absent de ce mapping tombe dans
# "Autre".
HUMAN_CATEGORY = {
    "P01": "Processus",
    "AD01": "Identite", "AD02": "Identite", "IAM-SSO": "Identite",
    "DNS01": "Reseau / DNS", "DNS02": "Reseau / DNS", "NTP01": "Reseau / DNS",
    "FW-EDGE-01": "Reseau / DNS", "VPN-PAYMENT": "Reseau / DNS",
    "PKI01": "Certificats (PKI)",
    "SECRETS-VAULT": "Coffre-fort secrets", "CYBER-VAULT": "Coffre-fort secrets",
    "VCENTER01": "Serveurs (compute)", "ESX-CLUSTER-PROD01": "Serveurs (compute)",
    "K8S-PRD": "Serveurs (compute)",
    "VM-ERP01": "Serveurs (compute)", "VM-ERP02": "Serveurs (compute)",
    "VM-DBERP01": "Serveurs (compute)", "VM-WMS01": "Serveurs (compute)",
    "VM-MQ01": "Serveurs (compute)",
    "ERPDB": "Donnees", "ORDERDB": "Donnees", "WMSDB": "Donnees", "DWH": "Donnees",
    "SAP-ERP": "Boutique", "ECOM-WEB": "Boutique", "ORDER-MGT": "Boutique",
    "REDIS-CART": "Boutique", "CDN-PUBLIC": "Boutique",
    "API-GW": "Boutique",
    "PAY-ADAPTER": "Paiement",
    "WMS": "Stock & Livraison", "TMS": "Stock & Livraison",
    "MQ-BROKER": "Stock & Livraison",
    "CRM-SFDC": "Service client", "MDM-CUSTOMER": "Service client",
    "BI-REPORT": "Autre", "PIM": "Autre", "POS-STORE": "Autre",
    "SMTP01": "Autre", "SIEM-XDR": "Securite / Supervision",
    "BACKUP-ORCH": "Sauvegardes",
}

# Ordre d'affichage des couches techniques (utilise pour la vue "architecte")
LAYER_ORDER = [
    "Identite", "Reseau / DNS", "Certificats (PKI)", "Coffre-fort secrets",
    "Securite / Supervision", "Sauvegardes", "Serveurs (compute)", "Donnees",
    "Boutique", "Paiement", "Stock & Livraison", "Service client", "Autre",
]


def human_category(node: str) -> str:
    return HUMAN_CATEGORY.get(node, "Autre")


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
