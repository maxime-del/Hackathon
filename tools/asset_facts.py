"""
Construit une fiche de faits generique par actif, destinee a etre lue par
Qwen pour qu'il analyse REELLEMENT les donnees plutot que de reconnaitre
des identifiants connus a l'avance (SAP-ERP, ORDERDB...). Uniquement des
jointures sur les colonnes canoniques deja normalisees par
tools.schema_mapping - aucun nom d'actif n'est code en dur ici.
"""
import pandas as pd

from tools.schema_mapping import get_table


def _rows_for(df: pd.DataFrame, asset_col: str, asset: str) -> list[dict]:
    if asset_col not in df.columns:
        return []
    matches = df[df[asset_col].astype(str) == str(asset)]
    return matches.to_dict("records")


def _fmt(row: dict, *fields: str) -> str:
    parts = []
    for field in fields:
        value = row.get(field)
        if value is not None and not (isinstance(value, float) and pd.isna(value)):
            parts.append(f"{field}={value}")
    return " ".join(parts)


def build_fact_sheet(tables: dict[str, pd.DataFrame], assets: list[str], process_id: str) -> str:
    """assets: noeuds du graphe pour ce processus (hors process_id lui-meme)."""
    cmdb = get_table(tables, "CMDB_Export")
    backup = get_table(tables, "Backup_Catalog")
    vault = get_table(tables, "Cyber_Vault_Catalog")
    impact = get_table(tables, "Impact_Assessment")
    vulns = get_table(tables, "Vulnerabilities_Extract")
    tickets = get_table(tables, "Ticket_Extract")
    vm = get_table(tables, "VMware_Inventory")
    bia = get_table(tables, "BIA_Export")
    app_deps = get_table(tables, "Application_Dependencies")
    infra_deps = get_table(tables, "Infrastructure_Dependencies")

    blocks: list[str] = []

    bia_matches = bia[bia["Process_ID"] == process_id] if "Process_ID" in bia.columns else bia.iloc[0:0]
    if not bia_matches.empty:
        r = bia_matches.iloc[0]
        blocks.append(
            f"[Processus {process_id}] {_fmt(r, 'RTO', 'RPO', 'Max_Data_Loss_EUR_Hour', 'Applications_Declared')}"
        )
    blocks.append(f"[Dependances reelles constatees dans le graphe pour {process_id}] {', '.join(sorted(assets))}")

    for asset in sorted(assets):
        parts = [f"### Actif: {asset}"]

        cmdb_rows = _rows_for(cmdb, "Name", asset)
        if cmdb_rows:
            parts.append("CMDB: " + _fmt(cmdb_rows[0], "Type", "Criticality", "RTO_Declared", "Notes"))
        else:
            parts.append("CMDB: absent (non documente officiellement)")

        for row in _rows_for(backup, "Asset", asset):
            parts.append("Backup_Catalog: " + _fmt(
                row, "Last_Successful_Backup", "Immutability", "RPO_Target", "RPO_Status", "Notes"
            ))

        for row in _rows_for(vault, "Asset", asset):
            parts.append("Cyber_Vault_Catalog: " + _fmt(row, "Vault_Copy_Timestamp", "Integrity_Check"))

        for row in _rows_for(impact, "Asset", asset):
            parts.append("Impact_Assessment: " + _fmt(row, "Status", "Confidence", "Immediate_Action"))

        for row in _rows_for(vulns, "Asset", asset):
            parts.append("Vulnerabilities_Extract: " + _fmt(row, "Finding", "Severity", "Notes"))

        for row in _rows_for(tickets, "Asset", asset):
            parts.append("Ticket_Extract: " + _fmt(row, "Ticket_ID", "Type", "Summary", "Notes"))

        for row in _rows_for(vm, "Application", asset):
            parts.append("VMware_Inventory: " + _fmt(row, "VM", "Backup_Protected", "Notes"))

        if "Source" in app_deps.columns:
            for _, row in app_deps[app_deps["Source"] == asset].iterrows():
                parts.append("Depend de (applicatif): " + _fmt(
                    row.to_dict(), "Target", "Dependency_Type", "Criticality", "Confidence", "Notes"
                ))

        if "Asset" in infra_deps.columns:
            for _, row in infra_deps[infra_deps["Asset"] == asset].iterrows():
                parts.append("Depend de (infra): " + _fmt(row.to_dict(), "Depends_On", "Reason", "Criticality", "Notes"))

        if len(parts) > 1:
            blocks.append("\n".join(parts))

    return "\n\n".join(blocks)
