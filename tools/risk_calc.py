"""
Calcul du risque financier residuel: ecart entre RPO cible (BIA) et RPO
reellement atteignable (Backup_Catalog), converti en euros via le cout
horaire de perte de donnees declare dans le BIA.

Limite assumee: ce calcul cible specifiquement l'actif "ORDERDB" du
processus P01 (le cas NovaRetail). Avec un autre jeu de donnees, cet actif
n'existera probablement pas sous ce nom - le calcul renvoie alors une
exposition marquee "donnees insuffisantes" plutot que de planter ou
d'inventer un chiffre.
"""
from dataclasses import dataclass
import pandas as pd

from tools.data_loader import load_all, get_incident_time
from tools.schema_mapping import get_table

TARGET_ASSET = "ORDERDB"


@dataclass
class FinancialExposure:
    asset: str
    process_id: str
    rpo_target: str | None
    last_reliable_backup: pd.Timestamp | None
    gap_hours: float | None
    eur_per_hour: float | None
    estimated_loss_eur: float
    confidence_note: str
    sources: list[str]
    data_sufficient: bool = True


def _insufficient(process_id: str, reason: str) -> FinancialExposure:
    return FinancialExposure(
        asset=TARGET_ASSET, process_id=process_id, rpo_target=None, last_reliable_backup=None,
        gap_hours=None, eur_per_hour=None, estimated_loss_eur=0.0,
        confidence_note=f"Donnees insuffisantes pour chiffrer ce risque : {reason}",
        sources=[], data_sufficient=False,
    )


def compute_orderdb_exposure(process_id: str = "P01") -> FinancialExposure:
    tables = load_all()
    bia = get_table(tables, "BIA_Export")
    backup = get_table(tables, "Backup_Catalog")

    bia_matches = bia[bia["Process_ID"] == process_id]
    if bia_matches.empty:
        return _insufficient(process_id, f"aucune ligne BIA trouvee pour le processus {process_id}")
    bia_row = bia_matches.iloc[0]
    if pd.isna(bia_row.get("Max_Data_Loss_EUR_Hour")):
        return _insufficient(process_id, "cout de perte horaire (Max_Data_Loss_EUR_Hour) absent du BIA")

    orderdb_rows = backup[backup["Asset"] == TARGET_ASSET]
    if orderdb_rows.empty:
        return _insufficient(process_id, f"aucune sauvegarde trouvee pour l'actif {TARGET_ASSET}")

    immutable = orderdb_rows[orderdb_rows["Immutability"] == "Yes"]
    usable_row = immutable.iloc[0] if not immutable.empty else orderdb_rows.iloc[0]
    if pd.isna(usable_row.get("Last_Successful_Backup")):
        return _insufficient(process_id, f"date de derniere sauvegarde manquante pour {TARGET_ASSET}")

    last_backup = pd.Timestamp(usable_row["Last_Successful_Backup"])
    gap_hours = max(0.0, (get_incident_time() - last_backup).total_seconds() / 3600)
    eur_per_hour = float(bia_row["Max_Data_Loss_EUR_Hour"])
    loss = gap_hours * eur_per_hour

    non_immutable = orderdb_rows[orderdb_rows["Immutability"] != "Yes"]
    confidence_note = (
        "Une copie plus recente existe (PITR) mais elle n'est pas immuable et son compte "
        "d'administration est possiblement compromis - non retenue comme base fiable."
        if not non_immutable.empty else
        "Aucune copie plus recente disponible."
    )

    return FinancialExposure(
        asset=TARGET_ASSET, process_id=process_id, rpo_target=bia_row.get("RPO"),
        last_reliable_backup=last_backup, gap_hours=gap_hours, eur_per_hour=eur_per_hour,
        estimated_loss_eur=loss, confidence_note=confidence_note,
        sources=["BIA_Export.csv", "Backup_Catalog.csv"],
    )


def euro_impact(process_id: str = "P01") -> FinancialExposure:
    """Alias explicite - c'est le tool que le risk_agent appelle."""
    return compute_orderdb_exposure(process_id)
