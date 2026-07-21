"""Petits helpers de formatage partages (convention francaise: espace comme separateur de milliers)."""


def eur(value: float) -> str:
    return f"{value:,.0f} €".replace(",", " ")
