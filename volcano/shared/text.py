"""Text helpers shared by services, reports and explanations."""
from collections.abc import Callable


def split_list(text: str | None, normalize: Callable[[str], str] = str.strip) -> list[str]:
    """«a, b,,c » → ["a", "b", "c"]. `normalize` is applied to each already-trimmed item."""
    return [normalize(p.strip()) for p in (text or "").split(",") if p.strip()]


def format_number_es(value: float | None, decimals: int = 1, thousands: bool = False) -> str:
    """Number in the Colombian convention: decimal comma and, optionally, dot thousands separator.

    format_number_es(118.45) → "118,5" · format_number_es(1234.5, 0, thousands=True) → "1.235" · None → "—"
    """
    if value is None:
        return "—"
    text = f"{value:,.{decimals}f}" if thousands else f"{value:.{decimals}f}"
    return text.translate(str.maketrans({",": ".", ".": ","}))
