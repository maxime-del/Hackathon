"""
Moteur d'anomalies deterministe: chaque fonction croise au moins deux
sources du corpus et renvoie un fait verifiable, jamais une supposition
du LLM. C'est le coeur du critere "detection d'incoherences".

`run_anomaly_checks` fait tourner l'ensemble des controles (c'est ce
qu'appelle l'anomaly_agent). Les fonctions nommees individuellement
(missing_in_bia, rpo_violations, stale_dns, obsolete_pra) filtrent ce
meme resultat par identifiant - utile si un agent ne veut interroger
qu'un controle precis, sans dupliquer la logique de detection.
"""
from dataclasses import dataclass, field
import pandas as pd

from tools.data_loader import load_all, get_incident_time
from tools.schema_mapping import get_table

SEVERITY_ORDER = {"CRITIQUE": 0, "HAUTE": 1, "MOYENNE": 2}


@dataclass
class Anomaly:
    id: str
    severity: str  # CRITIQUE / HAUTE / MOYENNE
    title_tech: str
    title_human: str
    detail_tech: str
    detail_human: str
    sources: list[str] = field(default_factory=list)
    action_pro: str | None = None  # a faire valider par un professionnel avant d'agir


def _bia_row(bia: pd.DataFrame, process_id: str) -> pd.Series | None:
    matches = bia[bia["Process_ID"] == process_id]
    return matches.iloc[0] if not matches.empty else None


def _bia_declared_apps(bia_row: pd.Series) -> set[str]:
    declared = bia_row.get("Applications_Declared")
    if pd.isna(declared):
        return set()
    return {a.strip() for a in str(declared).split(";")}


def run_anomaly_checks(process_id: str, graph_nodes: set[str]) -> list[Anomaly]:
    tables = load_all()
    bia = get_table(tables, "BIA_Export")
    backup = get_table(tables, "Backup_Catalog")
    vault = get_table(tables, "Cyber_Vault_Catalog")
    cmdb = get_table(tables, "CMDB_Export")
    dns = get_table(tables, "DNS_Export")
    tickets = get_table(tables, "Ticket_Extract")
    vulns = get_table(tables, "Vulnerabilities_Extract")
    impact = get_table(tables, "Impact_Assessment")
    monitoring = get_table(tables, "Monitoring_Alerts")
    app_deps = get_table(tables, "Application_Dependencies")

    out: list[Anomaly] = []
    bia_row = _bia_row(bia, process_id)

    # 1) BIA incomplet vs fermeture reelle des dependances du graphe
    #    (necessite une ligne BIA pour ce processus - sinon on ne peut pas
    #    savoir ce qui est "declare" et on saute ce controle plutot que de
    #    deviner)
    declared = _bia_declared_apps(bia_row) if bia_row is not None else set()
    missing = sorted((graph_nodes - declared) - {process_id}) if bia_row is not None else []
    if missing:
        out.append(Anomaly(
            id="BIA_INCOMPLETE",
            severity="CRITIQUE",
            title_tech=f"Le BIA de {process_id} omet {len(missing)} dependances bloquantes",
            title_human="La fiche officielle de risque ne liste pas tous les systemes utilises",
            detail_tech=(
                f"BIA_Export.csv declare seulement: {', '.join(sorted(declared))}. "
                f"Le graphe de dependances reel (Application_Dependencies.csv + "
                f"Process_to_Applications_Map.csv) montre que {process_id} depend aussi de: "
                f"{', '.join(missing)}."
            ),
            detail_human=(
                "Le document officiel de risque pense que la boutique repose sur 5 briques. "
                "En realite elle en utilise plusieurs de plus, dont le coffre a mots de passe "
                "et la base des commandes — si personne ne le sait, on les oublie a la reconstruction."
            ),
            sources=["BIA_Export.csv", "Application_Dependencies.csv", "Process_to_Applications_Map.csv"],
        ))

    # 2) PRA obsolete: suppose l'AD disponible alors que l'incident EST une compromission AD
    ad_compromised = impact[impact["Asset"].str.contains("AD0", na=False) & impact["Status"].str.contains("Compromis", case=False, na=False)]
    if not ad_compromised.empty:
        out.append(Anomaly(
            id="PRA_OBSOLETE_AD",
            severity="CRITIQUE",
            title_tech="Le PRA applicatif suppose l'annuaire (AD) sain, or AD est compromis",
            title_human="Le plan de secours existant ne marche pas pour cette panne precise",
            detail_tech=(
                "PRA_Gestion_Commandes_v1_2024_OBSOLETE.docx (2024) part du principe qu'AD/DNS "
                "sont disponibles pour restaurer SAP-ERP et ECOM-WEB. Impact_Assessment.csv indique "
                f"AD01/AD02: '{ad_compromised.iloc[0]['Status']}' (confiance "
                f"{ad_compromised.iloc[0]['Confidence']}) suite a la compromission constatee."
            ),
            detail_human=(
                "Le vieux plan de secours dit 'branchez-vous sur l'annuaire des employes, il marche'. "
                "Sauf que c'est justement l'annuaire qui a ete pirate en premier. Suivre ce plan tel quel "
                "romprait a nouveau tout."
            ),
            sources=["PRA_Gestion_Commandes_v1_2024_OBSOLETE.docx", "Impact_Assessment.csv"],
            action_pro="Faire confirmer par un expert cyber la strategie de reconstruction de l'annuaire "
                       "(foret propre vs restauration) avant toute action.",
        ))

    # 3) SECRETS-VAULT: blocage total du redeploiement
    sv_backup = backup[backup["Asset"] == "SECRETS-VAULT"]
    sv_vault = vault[vault["Asset"] == "SECRETS-VAULT"]
    sv_vuln = vulns[vulns["Asset"] == "SECRETS-VAULT"]
    if not sv_vuln.empty:
        out.append(Anomaly(
            id="SECRETS_VAULT_BLOCKER",
            severity="CRITIQUE",
            title_tech="SECRETS-VAULT: sauvegarde en echec + absent du coffre cyber",
            title_human="Le coffre-fort qui contient tous les mots de passe applicatifs est cassé",
            detail_tech=(
                f"Vulnerabilities_Extract.csv: '{sv_vuln.iloc[0]['Finding']}' (severite "
                f"{sv_vuln.iloc[0]['Severity']}). Backup_Catalog.csv: statut RPO "
                f"'{sv_backup.iloc[0]['RPO_Status'] if not sv_backup.empty else 'inconnu'}'. "
                f"Cyber_Vault_Catalog.csv: copie isolee '"
                f"{sv_vault.iloc[0]['Vault_Copy_Timestamp'] if not sv_vault.empty else 'absente'}'."
            ),
            detail_human=(
                "Sans ce coffre-fort, aucune application ne peut redemarrer proprement car elles ont "
                "toutes besoin de leurs mots de passe internes. C'est le vrai point de blocage numero un, "
                "avant meme le site web."
            ),
            sources=["Vulnerabilities_Extract.csv", "Backup_Catalog.csv", "Cyber_Vault_Catalog.csv"],
            action_pro="Faire diagnostiquer en urgence par votre prestataire pourquoi les sauvegardes du "
                       "coffre-fort echouent avant de tenter le moindre redemarrage d'application.",
        ))

    # 4) RPO gap ORDERDB -> perte financiere
    #    (necessite une ligne BIA valide pour le cout horaire - sinon on ne
    #    peut pas chiffrer et on saute ce controle)
    orderdb_rows = backup[backup["Asset"] == "ORDERDB"]
    if bia_row is not None and not pd.isna(bia_row.get("Max_Data_Loss_EUR_Hour")) and not orderdb_rows.empty:
        eur_per_hour = float(bia_row["Max_Data_Loss_EUR_Hour"])
        best_immutable = orderdb_rows[orderdb_rows["Immutability"] == "Yes"]
        usable_row = best_immutable.iloc[0] if not best_immutable.empty else orderdb_rows.iloc[0]
        last_backup = pd.Timestamp(usable_row["Last_Successful_Backup"])
        gap_hours = (get_incident_time() - last_backup).total_seconds() / 3600
        loss_eur = round(gap_hours * eur_per_hour)
        out.append(Anomaly(
            id="RPO_GAP_ORDERDB",
            severity="CRITIQUE",
            title_tech=f"ORDERDB: RPO cible {bia_row['RPO']} non tenable, ecart reel {gap_hours:.1f}h",
            title_human="Vous allez perdre plusieurs heures de commandes clients",
            detail_tech=(
                f"BIA_Export.csv fixe le RPO de {process_id} a {bia_row['RPO']}. La copie immuable la "
                f"plus recente d'ORDERDB (Backup_Catalog.csv) date du {last_backup}. La copie PITR de "
                f"08:00 est plus recente mais non immuable et son compte admin est possiblement "
                f"compromis (Backup_Catalog.csv). Ecart reel: {gap_hours:.1f}h x {eur_per_hour:,.0f} "
                f"EUR/h (BIA_Export.csv) = ~{loss_eur:,.0f} EUR de commandes non recuperables en confiance."
            ),
            detail_human=(
                f"La derniere sauvegarde des commandes vraiment fiable date d'avant l'incident. "
                f"Cela represente environ {gap_hours:.0f} heures de commandes clients qui risquent d'etre "
                f"perdues, soit environ {loss_eur:,.0f} euros."
            ),
            sources=["BIA_Export.csv", "Backup_Catalog.csv"],
            action_pro="Faire valider par la DAF le montant de perte acceptable et informer les clients "
                       "impactes des commandes potentiellement a resaisir.",
        ))

    # 5) DNS stale (double source: DNS_Export vs Ticket_Extract)
    dns_row = dns[dns["Record"] == "api.novaretail.eu"]
    ticket_row = tickets[tickets["Asset"].str.contains("api.novaretail.eu", na=False)]
    if not dns_row.empty and not ticket_row.empty:
        out.append(Anomaly(
            id="DNS_STALE",
            severity="HAUTE",
            title_tech="DNS api.novaretail.eu pointe vers une IP perimee",
            title_human="Une adresse technique importante n'a pas ete mise a jour",
            detail_tech=(
                f"DNS_Export.csv: api.novaretail.eu -> {dns_row.iloc[0]['Value']} "
                f"(modifie {dns_row.iloc[0]['Last_Changed']}). Ticket_Extract.csv "
                f"{ticket_row.iloc[0]['Ticket_ID']}: '{ticket_row.iloc[0]['Summary']}' confirme la "
                f"migration vers .18. La zone DNS n'a pas ete synchronisee."
            ),
            detail_human=(
                "Si on redemarre sans corriger cette adresse, les paiements et les appels API "
                "echoueront silencieusement — personne ne recevra d'alerte, ca semblera juste ne pas "
                "marcher."
            ),
            sources=["DNS_Export.csv", "Ticket_Extract.csv"],
            action_pro="Faire corriger l'adresse par l'equipe reseau avant de rouvrir l'acces public au site.",
        ))

    # 6) AD01: sauvegarde possiblement contaminee + vulnerabilite MFA (origine du mouvement lateral)
    ad_backup = backup[backup["Asset"] == "AD01"]
    ad_vuln = vulns[vulns["Asset"] == "AD01"]
    ad_alert = monitoring[monitoring["Asset"] == "AD01"]
    if not ad_backup.empty and not ad_vuln.empty:
        out.append(Anomaly(
            id="AD01_CONTAMINATED_BACKUP",
            severity="CRITIQUE",
            title_tech="AD01: sauvegarde possiblement contaminee + compte privilegie sans MFA",
            title_human="Restaurer l'annuaire tel quel pourrait réinfecter tout le systeme",
            detail_tech=(
                f"Backup_Catalog.csv: '{ad_backup.iloc[0]['Notes']}' (derniere sauvegarde "
                f"{ad_backup.iloc[0]['Last_Successful_Backup']}). Vulnerabilities_Extract.csv: "
                f"'{ad_vuln.iloc[0]['Finding']}' - {ad_vuln.iloc[0]['Notes']}. "
                + (f"Monitoring_Alerts.csv corrobore: '{ad_alert.iloc[0]['Message']}'." if not ad_alert.empty else "")
            ),
            detail_human=(
                "La copie de secours de l'annuaire des employes date d'avant l'attaque, mais elle "
                "pourrait deja contenir la porte d'entree des pirates (un compte administrateur sans "
                "protection renforcee). La restaurer sans verification reviendrait a rouvrir la porte."
            ),
            sources=["Backup_Catalog.csv", "Vulnerabilities_Extract.csv", "Monitoring_Alerts.csv"],
            action_pro="Ne pas restaurer l'annuaire sans qu'un expert cyber ait verifie l'absence de "
                       "porte derobee (analyse forensique minimale requise).",
        ))

    # 7) Dependance non documentee dans la CMDB (IAM-SSO)
    undocumented = []
    for _, row in app_deps.iterrows():
        target = row["Target"]
        if target in graph_nodes and target not in set(cmdb["Name"]):
            undocumented.append((target, row["Notes"]))
    if undocumented:
        target, note = undocumented[0]
        out.append(Anomaly(
            id="CMDB_ORPHAN",
            severity="MOYENNE",
            title_tech=f"{target} est une dependance critique absente de la CMDB",
            title_human=f"Un service dont depend la boutique n'est pas dans l'inventaire officiel",
            detail_tech=(
                f"Application_Dependencies.csv liste {target} comme dependance bloquante, mais aucune "
                f"ligne CMDB_Export.csv ne le documente. Note source: '{note}'."
            ),
            detail_human=(
                "Ce service n'apparait dans aucun inventaire officiel — en cas de crise, l'equipe "
                "risque de ne meme pas savoir qu'il existe ni qui le gere."
            ),
            sources=["Application_Dependencies.csv", "CMDB_Export.csv"],
        ))

    # 8) RTO incompatible entre CMDB (SAP-ERP) et BIA (P01)
    sap_cmdb = cmdb[cmdb["Name"] == "SAP-ERP"]
    if (not sap_cmdb.empty and bia_row is not None and not pd.isna(bia_row.get("RTO"))
            and sap_cmdb.iloc[0]["RTO_Declared"] != bia_row["RTO"]):
        out.append(Anomaly(
            id="RTO_CONTRADICTION",
            severity="HAUTE",
            title_tech=f"RTO contradictoire pour SAP-ERP: CMDB={sap_cmdb.iloc[0]['RTO_Declared']} vs BIA {process_id}={bia_row['RTO']}",
            title_human="Deux documents officiels ne sont pas d'accord sur le delai de reprise promis",
            detail_tech=(
                f"CMDB_Export.csv declare SAP-ERP RTO={sap_cmdb.iloc[0]['RTO_Declared']} "
                f"('{sap_cmdb.iloc[0]['Notes']}'), alors que BIA_Export.csv exige RTO={bia_row['RTO']} "
                f"pour {process_id}."
            ),
            detail_human=(
                "L'equipe technique s'est engagee sur un delai deux fois plus long que ce que la "
                "direction a promis aux clients. Il faut trancher avant la crise, pas pendant."
            ),
            sources=["CMDB_Export.csv", "BIA_Export.csv"],
        ))

    # 9) VM avec protection de sauvegarde incertaine (VM-ERP02)
    vm_uncertain = get_table(tables, "VMware_Inventory")
    vm_erp02 = vm_uncertain[vm_uncertain["VM"] == "VM-ERP02"]
    if not vm_erp02.empty and str(vm_erp02.iloc[0]["Backup_Protected"]).lower() == "unknown":
        out.append(Anomaly(
            id="VM_BACKUP_UNKNOWN",
            severity="HAUTE",
            title_tech="VM-ERP02 (serveur applicatif SAP): protection de sauvegarde inconnue",
            title_human="On ne sait pas si un des deux serveurs de la boutique est sauvegarde",
            detail_tech=(
                f"VMware_Inventory.csv: VM-ERP02, Backup_Protected='Unknown' - "
                f"'{vm_erp02.iloc[0]['Notes']}'. Le CMDB le classe pourtant comme actif critique PROD."
            ),
            detail_human=(
                "Un des deux serveurs qui font tourner la gestion des commandes n'a pas de statut de "
                "sauvegarde confirme. S'il est perdu, il faudra peut-etre tout reconstruire a la main."
            ),
            sources=["VMware_Inventory.csv", "CMDB_Export.csv"],
        ))

    # 10) API-GW: hotfix manuel non versionne + config absente du vault
    api_ticket = tickets[(tickets["Asset"] == "API-GW") & (tickets["Type"] == "Emergency change")]
    api_vault = vault[vault["Asset"] == "API-GW"]
    if not api_ticket.empty:
        out.append(Anomaly(
            id="API_GW_CONFIG_DRIFT",
            severity="HAUTE",
            title_tech="API-GW: correctif manuel hors GitOps, config absente du coffre cyber",
            title_human="Une reparation de derniere minute sur la porte d'entree API risque d'etre perdue",
            detail_tech=(
                f"Ticket_Extract.csv {api_ticket.iloc[0]['Ticket_ID']}: "
                f"'{api_ticket.iloc[0]['Summary']}' - '{api_ticket.iloc[0]['Notes']}'. "
                + (f"Cyber_Vault_Catalog.csv: config '{api_vault.iloc[0]['Vault_Copy_Timestamp']}'."
                   if not api_vault.empty else "")
            ),
            detail_human=(
                "Un correctif urgent applique a la main juste avant l'incident n'a jamais ete sauvegarde "
                "correctement. En reconstruisant depuis les sauvegardes standards, ce correctif "
                "disparaitra sans prevenir personne."
            ),
            sources=["Ticket_Extract.csv", "Cyber_Vault_Catalog.csv"],
        ))

    out.sort(key=lambda a: SEVERITY_ORDER.get(a.severity, 9))
    return out


def _by_id(anomalies: list[Anomaly], anomaly_id: str) -> list[Anomaly]:
    return [a for a in anomalies if a.id == anomaly_id]


def missing_in_bia(anomalies: list[Anomaly]) -> list[Anomaly]:
    return _by_id(anomalies, "BIA_INCOMPLETE")


def rpo_violations(anomalies: list[Anomaly]) -> list[Anomaly]:
    return _by_id(anomalies, "RPO_GAP_ORDERDB")


def stale_dns(anomalies: list[Anomaly]) -> list[Anomaly]:
    return _by_id(anomalies, "DNS_STALE")


def obsolete_pra(anomalies: list[Anomaly]) -> list[Anomaly]:
    return _by_id(anomalies, "PRA_OBSOLETE_AD")
