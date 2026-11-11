"""Closed catalogues. Stored as text (portable between SQLite and PostgreSQL) and validated
with these enums in the Pydantic schemas. The Spanish labels shown in the UI live here too,
next to the value they describe, so reports and e-mails use the same wording as the frontend.
"""
from enum import StrEnum


class RoleName(StrEnum):
    ADMIN = "ADMIN"
    PHARMACY = "PHARMACY"
    CITIZEN = "CITIZEN"


class RiskLevel(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"

    @property
    def rank(self) -> int:
        """Position on the scale (0 = green … 3 = red), so levels can be compared."""
        return list(RiskLevel).index(self)

    @property
    def label_es(self) -> str:
        return _RISK_LABELS_ES[self]

    @property
    def is_alert(self) -> bool:
        """High or very high: the levels that raise an early alert."""
        return self.rank >= RiskLevel.ORANGE.rank

    @classmethod
    def worst(cls, levels) -> "RiskLevel":
        """Highest level in a collection (GREEN when empty). Accepts enums or strings."""
        return max((cls(level) for level in levels), key=lambda level: level.rank, default=cls.GREEN)


_RISK_LABELS_ES = {RiskLevel.GREEN: "Bajo", RiskLevel.YELLOW: "Moderado", RiskLevel.ORANGE: "Alto",
                   RiskLevel.RED: "Muy alto"}


class AlertOrigin(StrEnum):
    OBSERVED = "OBSERVED"    # last week's cases are already above the threshold
    PREDICTED = "PREDICTED"  # the model expects it within the next 4 weeks


class VolcanoLevel(StrEnum):
    # Alert scale of the Colombian Geological Service (SGC)
    GREEN = "GREEN"    # active volcano, stable behaviour
    YELLOW = "YELLOW"  # changes in the activity
    ORANGE = "ORANGE"  # eruption likely within days or weeks
    RED = "RED"        # eruption imminent or under way


class VolcanicEventType(StrEnum):
    BULLETIN = "BULLETIN"          # weekly SGC bulletin (activity level)
    ASH_FALL = "ASH_FALL"          # ash fall reported in a municipality
    GAS_EMISSION = "GAS_EMISSION"
    EARTHQUAKE = "EARTHQUAKE"


class ProductCategory(StrEnum):
    COLD_FLU = "COLD_FLU"
    ANTIPYRETICS = "ANTIPYRETICS"
    ORAL_REHYDRATION = "ORAL_REHYDRATION"
    INHALERS = "INHALERS"
    FACE_MASKS = "FACE_MASKS"
    REPELLENTS = "REPELLENTS"

    @property
    def label_es(self) -> str:
        return _CATEGORY_LABELS_ES[self]


_CATEGORY_LABELS_ES = {
    ProductCategory.COLD_FLU: "antigripales", ProductCategory.ANTIPYRETICS: "antipiréticos",
    ProductCategory.ORAL_REHYDRATION: "sales de rehidratación", ProductCategory.INHALERS: "inhaladores",
    ProductCategory.FACE_MASKS: "tapabocas", ProductCategory.REPELLENTS: "repelentes",
}

# Values written before the code moved to English. CSV uploads and the schema migration use
# them to translate old data, so pharmacies can keep uploading their existing templates.
LEGACY_VALUES: dict[type[StrEnum], dict[str, str]] = {
    RoleName: {"FARMACIA": "PHARMACY", "CIUDADANO": "CITIZEN"},
    RiskLevel: {"VERDE": "GREEN", "AMARILLO": "YELLOW", "NARANJA": "ORANGE", "ROJO": "RED"},
    AlertOrigin: {"OBSERVADO": "OBSERVED", "PREDICHO": "PREDICTED"},
    VolcanoLevel: {"VERDE": "GREEN", "AMARILLO": "YELLOW", "NARANJA": "ORANGE", "ROJO": "RED"},
    VolcanicEventType: {"BOLETIN": "BULLETIN", "CAIDA_CENIZA": "ASH_FALL", "EMISION_GASES": "GAS_EMISSION",
                        "SISMO": "EARTHQUAKE"},
    ProductCategory: {"ANTIGRIPALES": "COLD_FLU", "ANTIPIRETICOS": "ANTIPYRETICS",
                      "SALES_REHIDRATACION": "ORAL_REHYDRATION", "INHALADORES": "INHALERS",
                      "TAPABOCAS": "FACE_MASKS", "REPELENTES": "REPELLENTS"},
}


def parse_enum[E: StrEnum](enum: type[E], raw: str) -> E:
    """Parse a value that may still use the legacy Spanish spelling. Raises ValueError."""
    value = raw.strip().upper()
    return enum(LEGACY_VALUES.get(enum, {}).get(value, value))
