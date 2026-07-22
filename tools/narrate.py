"""
Traduction déterministe (sans LLM) d'une étape technique du plan de
reconstruction en phrase compréhensible par un non-informaticien.
Un gabarit par catégorie humaine + un mot sur la confiance de la sauvegarde.

C'est un tool, pas un agent : aucun appel LLM ici. C'est le chemin
principal utilisé par translator_agent en secours si Qwen est indisponible.
"""
from tools.restore_plan import RestoreStep

HUMAN_NAME = {
    "AD01": "l'annuaire des employés (principal)", "AD02": "l'annuaire des employés (secours)",
    "IAM-SSO": "le système de connexion unique",
    "DNS01": "le carnet d'adresses interne (DNS principal)", "DNS02": "le carnet d'adresses interne (DNS secours)",
    "NTP01": "l'horloge réseau", "FW-EDGE-01": "le pare-feu",
    "VPN-PAYMENT": "le tunnel sécurisé vers la banque",
    "PKI01": "les certificats de sécurité (PKI)",
    "SECRETS-VAULT": "le coffre-fort des mots de passe applicatifs",
    "CYBER-VAULT": "le coffre-fort de secours isolé",
    "VCENTER01": "le gestionnaire des serveurs virtuels", "ESX-CLUSTER-PROD01": "les serveurs physiques",
    "K8S-PRD": "la plateforme applicative (cloud)",
    "VM-ERP01": "un serveur de l'ERP", "VM-ERP02": "un second serveur de l'ERP",
    "VM-DBERP01": "le serveur de la base ERP", "VM-WMS01": "le serveur entrepôt",
    "VM-MQ01": "le serveur de messages internes",
    "ERPDB": "la base de données ERP (prix, stock)", "ORDERDB": "la base des commandes clients",
    "WMSDB": "la base de l'entrepôt", "DWH": "l'entrepôt de données (reporting)",
    "SAP-ERP": "le logiciel de gestion (ERP)", "ECOM-WEB": "le site web de commandes",
    "ORDER-MGT": "le service qui orchestre les commandes", "REDIS-CART": "le panier d'achat en mémoire",
    "CDN-PUBLIC": "le réseau de diffusion du site", "API-GW": "la porte d'entrée des services (API)",
    "PAY-ADAPTER": "le module de paiement",
    "WMS": "le logiciel d'entrepôt", "TMS": "le logiciel de transport",
    "MQ-BROKER": "la file de messages entre systèmes",
    "CRM-SFDC": "l'outil de support client", "MDM-CUSTOMER": "le référentiel clients",
    "BI-REPORT": "le reporting", "PIM": "le catalogue produits", "POS-STORE": "les caisses magasin",
    "SMTP01": "l'envoi d'emails", "SIEM-XDR": "la supervision de sécurité",
    "BACKUP-ORCH": "l'orchestrateur de sauvegardes",
}

# Le "pourquoi" precis d'un statut rouge - voir tools/graph_builder.py.
# icone, libelle court (badge), explication longue (pour l'infobulle du
# graphe et le detail du plan). Distinct du risque de redemarrage
# (risk_level, decide par tools/decision_risk.py) : ceci decrit L'ETAT DE
# L'ACTIF, pas le risque de la decision de le relancer maintenant.
STATUS_KIND_HUMAN = {
    "COMPROMIS": (
        "🛑", "Compromis",
        "Cet actif est déclaré compromis par l'évaluation d'impact : il ne fonctionne plus normalement et ne "
        "doit pas être remis en service tel quel, sous peine de rejouer l'attaque.",
    ),
    "RESTAURATION_RISQUEE": (
        "🔴", "Risqué à redémarrer",
        "Rien n'indique que cet actif est compromis en lui-même, mais la sauvegarde ou le coffre disponible "
        "pour le restaurer n'est pas fiable : le redémarrer maintenant est un pari, pas une certitude.",
    ),
    "A_VERIFIER": (
        "🟠", "À vérifier",
        "Une sauvegarde existe mais un point n'a pas été confirmé (RPO en limite, intégrité jamais testée) : "
        "à valider avant de faire confiance au redémarrage.",
    ),
    "NON_DOCUMENTE": (
        "⚪", "Non documenté",
        "Cet actif n'apparaît pas dans la CMDB fournie : son état réel n'est pas connu, à vérifier manuellement "
        "avant toute action.",
    ),
    "FIABLE": (
        "🟢", "Fiable",
        "Sauvegarde documentée, à jour et sans anomalie détectée dans le corpus fourni.",
    ),
}

# Ordre du pire au meilleur, pour choisir le statut le plus grave d'un groupe.
STATUS_KIND_SEVERITY = ["COMPROMIS", "RESTAURATION_RISQUEE", "A_VERIFIER", "NON_DOCUMENTE", "FIABLE"]


def human_name(node: str) -> str:
    return HUMAN_NAME.get(node, node)


def status_kind_human(status_kind: str) -> tuple[str, str, str]:
    """(icône, libellé court, explication longue) pour un status_kind."""
    return STATUS_KIND_HUMAN.get(status_kind, ("⚪", "Statut inconnu", "Aucune information disponible."))


def explain_step(step: RestoreStep) -> str:
    name = human_name(step.node)
    icon, _, _ = status_kind_human(getattr(step, "status_kind", "FIABLE"))
    dependents = [d for d in step.dependents if d != "P01"]
    if dependents:
        blocks = ", ".join(human_name(d) for d in dependents[:2])
        why = f"tant que ce n'est pas fait, {blocks} ne peut pas repartir"
    else:
        why = "c'est la dernière brique de la chaîne pour redémarrer la boutique"
    return f"{icon} Remettre en service **{name}** — {why}."


def category_status_color(nodes_in_category: list[RestoreStep]) -> str:
    """Pire status_kind parmi les noeuds d'une catégorie -> icône représentative.
    Utilise status_kind (pourquoi c'est rouge) plutôt que la confiance brute,
    pour que "compromis" et "risqué à redémarrer" restent visuellement distincts."""
    present = {getattr(n, "status_kind", "FIABLE") for n in nodes_in_category}
    for kind in STATUS_KIND_SEVERITY:
        if kind in present:
            return status_kind_human(kind)[0]
    return "🟢"
