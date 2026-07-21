"""
Calcul du risque financier residuel, generalise a TOUS les actifs d'un
processus (plus un seul actif code en dur type "ORDERDB") : pour chaque
actif ayant une sauvegarde documentee, on compare le RPO cible declare a
l'ecart reel jusqu'a l'incident, et on chiffre la perte potentielle via
le cout horaire du processus (BIA). Reste 100% deterministe - seule la
DETECTION D'ANOMALIES (tools/anomaly_checks.py + anomaly_agent) est
passee a une analyse LLM ; le calcul de perte financiere n'a pas besoin
de deviner, juste de ne plus filtrer sur un nom fixe.
"""
from dataclasses import dataclass, field
import re

import pandas as pd

from tools.categorize import human_category
from tools.data_loader import load_all, get_incident_time
from tools.schema_mapping import get_table


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
    sources: list[str] = field(default_factory=list)
    data_sufficient: bool = True


def _insufficient(process_id: str, reason: str) -> FinancialExposure:
    return FinancialExposure(
        asset="?", process_id=process_id, rpo_target=None, last_reliable_backup=None,
        gap_hours=None, eur_per_hour=None, estimated_loss_eur=0.0,
        confidence_note=f"Donnees insuffisantes pour chiffrer un risque financier : {reason}",
        sources=[], data_sufficient=False,
    )


def _parse_hours(value) -> float | None:
    """'4h' -> 4.0, '30m' -> 0.5, '1d' -> 24.0. None si illisible."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    match = re.match(r"\s*([\d.]+)\s*([a-zA-Z]*)", str(value))
    if not match:
        return None
    amount, unit = float(match.group(1)), match.group(2).lower()
    if unit.startswith("m"):
        return amount / 60
    if unit.startswith("d"):
        return amount * 24
    return amount  # par defaut : heures


def compute_exposures(process_id: str = "P01", top_n: int = 5) -> list[FinancialExposure]:
    tables = load_all()
    bia = get_table(tables, "BIA_Export")
    backup = get_table(tables, "Backup_Catalog")

    bia_matches = bia[bia["Process_ID"] == process_id] if "Process_ID" in bia.columns else bia.iloc[0:0]
    if bia_matches.empty or pd.isna(bia_matches.iloc[0].get("Max_Data_Loss_EUR_Hour")):
        return [_insufficient(process_id, "aucun cout de perte horaire (BIA) trouve pour ce processus")]
    bia_row = bia_matches.iloc[0]
    eur_per_hour = float(bia_row["Max_Data_Loss_EUR_Hour"])
    incident_time = get_incident_time()

    exposures: list[FinancialExposure] = []
    if "Asset" not in backup.columns:
        return [_insufficient(process_id, "aucune table de sauvegardes reconnue (Backup_Catalog)")]

    cmdb = get_table(tables, "CMDB_Export")
    cmdb_type_by_name = dict(zip(cmdb.get("Name", []), cmdb.get("Type", [])))

    for asset, group in backup.groupby("Asset"):
        if pd.isna(asset):
            continue
        # Le cout horaire du BIA representant des ventes/commandes perdues,
        # ne l'appliquer qu'aux actifs qui portent reellement de la donnee
        # metier (bases de donnees) - sinon "sauvegarde vieille de 50 jours"
        # sur un annuaire ou un DNS se traduirait a tort par des dizaines
        # de millions d'euros de "perte", ce qui n'a pas de sens : une
        # sauvegarde d'infrastructure perimee n'efface pas des semaines de
        # chiffre d'affaires, elle signifie juste "config a rejouer".
        if human_category(str(asset), cmdb_type_by_name.get(asset)) != "Donnees":
            continue
        immutable = group[group["Immutability"] == "Yes"] if "Immutability" in group.columns else group.iloc[0:0]
        usable = immutable.iloc[0] if not immutable.empty else group.iloc[0]
        last_backup_raw = usable.get("Last_Successful_Backup")
        if last_backup_raw is None or (isinstance(last_backup_raw, float) and pd.isna(last_backup_raw)):
            continue
        try:
            last_backup = pd.Timestamp(last_backup_raw)
        except (ValueError, TypeError):
            continue
        gap_hours = max(0.0, (incident_time - last_backup).total_seconds() / 3600)
        rpo_target_hours = _parse_hours(usable.get("RPO_Target"))
        if rpo_target_hours is None or gap_hours <= rpo_target_hours:
            continue  # pas de violation constatee pour cet actif

        loss = gap_hours * eur_per_hour
        non_immutable = group[group["Immutability"] != "Yes"] if "Immutability" in group.columns else group.iloc[0:0]
        confidence_note = (
            "Une copie plus recente existe mais n'est pas immuable - non retenue comme base fiable."
            if not non_immutable.empty else "Aucune copie plus recente disponible."
        )
        exposures.append(FinancialExposure(
            asset=str(asset), process_id=process_id, rpo_target=usable.get("RPO_Target"),
            last_reliable_backup=last_backup, gap_hours=gap_hours, eur_per_hour=eur_per_hour,
            estimated_loss_eur=loss, confidence_note=confidence_note,
            sources=["BIA_Export.csv", "Backup_Catalog.csv"],
        ))

    if not exposures:
        return [_insufficient(process_id, "aucune violation de RPO constatee sur les sauvegardes disponibles")]

    exposures.sort(key=lambda e: -e.estimated_loss_eur)
    return exposures[:top_n]
