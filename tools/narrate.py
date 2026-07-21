"""
Traduction deterministe (sans LLM) d'une etape technique du plan de
reconstruction en phrase comprehensible par un non-informaticien.
Un gabarit par categorie humaine + un mot sur la confiance de la sauvegarde.

C'est un tool, pas un agent: aucun appel LLM ici. C'est le chemin
principal utilise par translator_agent en secours si Qwen est indisponible.
"""
from tools.restore_plan import RestoreStep

HUMAN_NAME = {
    "AD01": "l'annuaire des employes (principal)", "AD02": "l'annuaire des employes (secours)",
    "IAM-SSO": "le systeme de connexion unique",
    "DNS01": "le carnet d'adresses interne (DNS principal)", "DNS02": "le carnet d'adresses interne (DNS secours)",
    "NTP01": "l'horloge reseau", "FW-EDGE-01": "le pare-feu",
    "VPN-PAYMENT": "le tunnel securise vers la banque",
    "PKI01": "les certificats de securite (PKI)",
    "SECRETS-VAULT": "le coffre-fort des mots de passe applicatifs",
    "CYBER-VAULT": "le coffre-fort de secours isole",
    "VCENTER01": "le gestionnaire des serveurs virtuels", "ESX-CLUSTER-PROD01": "les serveurs physiques",
    "K8S-PRD": "la plateforme applicative (cloud)",
    "VM-ERP01": "un serveur de l'ERP", "VM-ERP02": "un second serveur de l'ERP",
    "VM-DBERP01": "le serveur de la base ERP", "VM-WMS01": "le serveur entrepot",
    "VM-MQ01": "le serveur de messages internes",
    "ERPDB": "la base de donnees ERP (prix, stock)", "ORDERDB": "la base des commandes clients",
    "WMSDB": "la base de l'entrepot", "DWH": "l'entrepot de donnees (reporting)",
    "SAP-ERP": "le logiciel de gestion (ERP)", "ECOM-WEB": "le site web de commandes",
    "ORDER-MGT": "le service qui orchestre les commandes", "REDIS-CART": "le panier d'achat en memoire",
    "CDN-PUBLIC": "le reseau de diffusion du site", "API-GW": "la porte d'entree des services (API)",
    "PAY-ADAPTER": "le module de paiement",
    "WMS": "le logiciel d'entrepot", "TMS": "le logiciel de transport",
    "MQ-BROKER": "la file de messages entre systemes",
    "CRM-SFDC": "l'outil de support client", "MDM-CUSTOMER": "le referentiel clients",
    "BI-REPORT": "le reporting", "PIM": "le catalogue produits", "POS-STORE": "les caisses magasin",
    "SMTP01": "l'envoi d'emails", "SIEM-XDR": "la supervision de securite",
    "BACKUP-ORCH": "l'orchestrateur de sauvegardes",
}

CONFIDENCE_HUMAN = {
    "SUR": ("🟢", "sauvegarde fiable"),
    "INCERTAIN": ("🟠", "sauvegarde a verifier avant de faire confiance"),
    "DANGER": ("🔴", "sauvegarde a risque, ne pas restaurer sans validation"),
    "INCONNU": ("⚪", "situation non documentee, a verifier manuellement"),
}


def human_name(node: str) -> str:
    return HUMAN_NAME.get(node, node)


def explain_step(step: RestoreStep) -> str:
    name = human_name(step.node)
    icon, conf_phrase = CONFIDENCE_HUMAN.get(step.confidence, ("⚪", "statut inconnu"))
    dependents = [d for d in step.dependents if d != "P01"]
    if dependents:
        blocks = ", ".join(human_name(d) for d in dependents[:2])
        why = f"tant que ce n'est pas fait, {blocks} ne peut pas repartir"
    else:
        why = "c'est la derniere brique de la chaine pour redemarrer la boutique"
    return f"{icon} Remettre en service **{name}** — {why} ({conf_phrase})."


def category_status_color(nodes_in_category: list[RestoreStep]) -> str:
    """Pire statut de confiance parmi les noeuds d'une categorie -> couleur feu tricolore."""
    if any(n.confidence == "DANGER" for n in nodes_in_category):
        return "🔴"
    if any(n.confidence in ("INCERTAIN", "INCONNU") for n in nodes_in_category):
        return "🟠"
    return "🟢"
