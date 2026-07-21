"""
Acces aux tables normalisees consommees par les autres tools.

Deux sources possibles:
- par defaut, les CSV NovaRetail livres avec le repo (data/*.csv) ;
- ou un jeu de donnees uploade par l'utilisateur dans l'app (n'importe quel
  nom de fichier / n'importe quelles colonnes), deja classe/normalise par
  `tools.schema_mapping.classify_and_normalize` et pousse ici via
  `set_active_tables`.

Le reste du code (graph_builder, categorize, anomaly_checks, risk_calc)
appelle toujours `load_all()` sans argument - il n'a pas besoin de savoir
d'ou viennent les donnees.
"""
from pathlib import Path
from functools import lru_cache
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

_FILES = [
    "AD_Groups_Export",
    "API_Catalog",
    "Application_Dependencies",
    "BIA_Export",
    "Backup_Catalog",
    "CMDB_Export",
    "Cyber_Vault_Catalog",
    "DNS_Export",
    "Data_Classification",
    "Database_Inventory",
    "External_Partners",
    "IAM_Service_Accounts",
    "Impact_Assessment",
    "Incident_Timeline",
    "Infrastructure_Dependencies",
    "Kubernetes_Inventory",
    "Monitoring_Alerts",
    "Network_Flows",
    "Process_to_Applications_Map",
    "Ticket_Extract",
    "VMware_Inventory",
    "Vulnerabilities_Extract",
]

# Reperer temporel par defaut, utilise pour tous les calculs d'ecart RPO sur
# le jeu d'exemple NovaRetail. Source: Incident_Timeline.csv - "SEV1
# ransomware declared / Crisis cell activated". Peut etre remplace par
# set_incident_time() quand un autre jeu de donnees est charge.
_DEFAULT_INCIDENT_DECLARED_AT = pd.Timestamp("2026-06-08 08:15")

_active_tables: dict[str, pd.DataFrame] | None = None
_active_incident_time: pd.Timestamp | None = None


@lru_cache(maxsize=1)
def _load_default_from_disk() -> dict[str, pd.DataFrame]:
    tables = {}
    for name in _FILES:
        path = DATA_DIR / f"{name}.csv"
        df = pd.read_csv(path, encoding="utf-8-sig")
        df.columns = [c.strip() for c in df.columns]
        tables[name] = df
    return tables


def set_active_tables(tables: dict[str, pd.DataFrame]) -> None:
    """Bascule le moteur sur un jeu de donnees uploade (deja classe par role)."""
    global _active_tables
    _active_tables = tables


def clear_active_tables() -> None:
    """Revient au jeu d'exemple NovaRetail livre avec le repo."""
    global _active_tables, _active_incident_time
    _active_tables = None
    _active_incident_time = None


def set_incident_time(ts: pd.Timestamp) -> None:
    global _active_incident_time
    _active_incident_time = ts


def load_all() -> dict[str, pd.DataFrame]:
    if _active_tables is not None:
        return _active_tables
    return _load_default_from_disk()


def get_incident_time() -> pd.Timestamp:
    if _active_incident_time is not None:
        return _active_incident_time
    return _DEFAULT_INCIDENT_DECLARED_AT


# Conserve pour compatibilite avec le code existant qui importe la constante
# directement (elle refletera toujours le jeu d'exemple NovaRetail; utiliser
# get_incident_time() pour un jeu de donnees uploade).
INCIDENT_DECLARED_AT = _DEFAULT_INCIDENT_DECLARED_AT
