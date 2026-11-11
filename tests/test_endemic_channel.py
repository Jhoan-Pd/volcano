"""Traffic light (endemic channel)."""
from volcano.models.enums import RiskLevel
from volcano.services import risk
from volcano.shared.epi import weeks_in_year


def test_thresholds_from_percentiles():
    t = risk.compute_thresholds(list(range(1, 21)), 50, 75, 90)
    assert t.yellow == 10.5 and t.orange == 15.25 and t.red == 18.1


def test_classification_by_zone():
    t = risk.ChannelThresholds(yellow=10, orange=15, red=20)
    assert risk.classify(8, t) == RiskLevel.GREEN
    assert risk.classify(12, t) == RiskLevel.YELLOW
    assert risk.classify(17, t) == RiskLevel.ORANGE
    assert risk.classify(25, t) == RiskLevel.RED


def test_minimum_floor_avoids_false_alarms():
    # dengue in Pasto: history almost always at zero
    t = risk.compute_thresholds([0] * 14 + [1], 50, 75, 90)
    assert risk.classify(1, t) == RiskLevel.GREEN
    assert risk.classify(risk.MIN_ALERT_CASES, t) == RiskLevel.RED


def test_without_enough_history_it_is_green():
    assert risk.compute_thresholds([5, 6], 50, 75, 90) is None
    assert risk.classify(100, None) == RiskLevel.GREEN


def test_reference_weeks_handle_week_53():
    assert weeks_in_year(2020) == 53
    pairs = risk.reference_weeks(2026, 53)
    assert len(pairs) == 15
    assert (2021, 52) in pairs  # 2021 has no week 53 -> week 52 is used
    assert all(y < 2026 or (y == 2026 and w == 1) for y, w in pairs)


def test_worst_level_and_spanish_labels():
    assert RiskLevel.worst(["GREEN", "ORANGE", "YELLOW"]) == RiskLevel.ORANGE
    assert RiskLevel.worst([]) == RiskLevel.GREEN
    assert RiskLevel.RED.rank > RiskLevel.ORANGE.rank > RiskLevel.GREEN.rank
    assert [level.label_es for level in RiskLevel] == ["Bajo", "Moderado", "Alto", "Muy alto"]
