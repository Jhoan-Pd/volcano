"""Shared text helpers and enum parsing."""
import pytest

from volcano.models import Disease
from volcano.models.enums import ProductCategory, RiskLevel, VolcanicEventType, parse_enum
from volcano.shared.text import format_number_es, split_list


@pytest.mark.parametrize(("text", "expected"), [
    ("fiebre, Dengue ,, tos ", ["fiebre", "Dengue", "tos"]),
    ("", []),
    (None, []),
])
def test_split_list(text, expected):
    assert split_list(text) == expected


def test_split_list_normalizes():
    assert split_list("a ,b", str.upper) == ["A", "B"]


@pytest.mark.parametrize(("value", "decimals", "thousands", "expected"), [
    (118.45, 1, False, "118,5"),
    (1234.5, 0, True, "1.234"),
    (1234567.891, 2, True, "1.234.567,89"),
    (0, 1, False, "0,0"),
    (None, 1, False, "—"),
])
def test_format_number_es(value, decimals, thousands, expected):
    assert format_number_es(value, decimals, thousands) == expected


def test_disease_list_properties():
    d = Disease(code="X", name="X", search_terms="Fiebre, TOS", sivigila_codes="210, 220",
                pharmacy_categories="cold_flu,REPELLENTS", recommendations="Uno\n\n  Dos  \n")
    assert d.search_term_list == ["fiebre", "tos"]
    assert d.sivigila_code_list == ["210", "220"]
    assert d.pharmacy_category_list == ["COLD_FLU", "REPELLENTS"]
    assert d.recommendation_list == ["Uno", "Dos"]


def test_parse_enum_accepts_legacy_spanish_values():
    assert parse_enum(ProductCategory, "antigripales ") == ProductCategory.COLD_FLU
    assert parse_enum(VolcanicEventType, "CAIDA_CENIZA") == VolcanicEventType.ASH_FALL
    assert parse_enum(RiskLevel, "orange") == RiskLevel.ORANGE
    with pytest.raises(ValueError):
        parse_enum(ProductCategory, "VITAMINAS")
