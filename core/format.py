"""Petits helpers de formatage partagés (convention française : espace comme séparateur de milliers)."""


def eur(value: float) -> str:
    return f"{value:,.0f} €".replace(",", " ")
