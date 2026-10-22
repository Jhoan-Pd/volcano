"""Utilidades de texto compartidas por servicios, reportes y explicaciones.

Antes cada módulo tenía su propia copia de estas funciones (separar listas por coma,
escribir números con coma decimal); ahora hay una sola implementación probada.
"""
from collections.abc import Callable


def separar_lista(texto: str | None, normalizar: Callable[[str], str] = str.strip) -> list[str]:
    """«a, b,,c » → ["a", "b", "c"]. `normalizar` se aplica a cada elemento ya sin espacios."""
    return [normalizar(p.strip()) for p in (texto or "").split(",") if p.strip()]


def numero_es(valor: float | None, decimales: int = 1, miles: bool = False) -> str:
    """Número con la convención colombiana: coma decimal y, opcionalmente, punto de miles.

    numero_es(118.45) → "118,5" · numero_es(1234.5, 0, miles=True) → "1.235" · None → "—"
    """
    if valor is None:
        return "—"
    texto = f"{valor:,.{decimales}f}" if miles else f"{valor:.{decimales}f}"
    return texto.translate(str.maketrans({",": ".", ".": ","}))
