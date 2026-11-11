"""Google Trends: CSV parsing, window stitching, automatic fallback and database cache."""
from datetime import date

import pandas as pd
import pytest

from volcano.models import SearchTrend
from volcano.services.search_trends import SearchTrendService
from volcano.shared.epi import week_of
from volcano.sources import DataSourceError
from volcano.sources.trends import CsvTrendsSource, TrendsSource

GOOGLE_CSV = """Categoría: Todas las categorías

Semana,fiebre: (Nariño),dengue: (Nariño)
2025-01-05,54,<1
2025-01-12,61,3
"""

LONG_CSV = """term,week_start,interest,region,is_simulated
gripa,2025-01-05,40,CO-NAR,0
gripa,2025-01-12,45,CO-NAR,1
"""

LEGACY_LONG_CSV = """termino,fecha_semana,indice,region,es_simulado
tos,2025-01-05,12,CO-NAR,0
"""


def test_parses_a_google_export():
    rows = CsvTrendsSource.parse(GOOGLE_CSV)
    assert len(rows) == 4
    dengue = [r for r in rows if r["term"] == "dengue"]
    assert dengue[0]["interest"] == 0.5  # "<1" means very low interest
    assert (dengue[0]["year"], dengue[0]["epi_week"]) == week_of(date(2025, 1, 5))


def test_parses_the_long_format_and_flags_simulated_rows():
    rows = CsvTrendsSource.parse(LONG_CSV)
    assert [r["is_simulated"] for r in rows] == [False, True]
    assert rows[1]["source"] == "simulated"


def test_parses_the_legacy_spanish_long_format():
    rows = CsvTrendsSource.parse(LEGACY_LONG_CSV)
    assert rows[0]["term"] == "tos" and rows[0]["interest"] == 12


def test_csv_without_a_header_fails():
    with pytest.raises(DataSourceError):
        CsvTrendsSource.parse("hola\nmundo")


def test_windows_are_shorter_than_five_years_and_overlap():
    w = TrendsSource.windows(date(2019, 1, 1), date(2026, 10, 1))
    assert len(w) == 2
    assert w[-1][0] == date(2019, 1, 1)
    assert w[1][1] > w[0][0]  # consecutive windows overlap
    assert all((end - start).days <= 1800 for start, end in w)


def test_stitching_rescales_by_the_overlap():
    recent = {date(2024, 1, 7): 50.0, date(2024, 1, 14): 100.0}
    older = {date(2023, 12, 31): 10.0, date(2024, 1, 7): 25.0, date(2024, 1, 14): 50.0}  # ×0.5 scale
    joined = TrendsSource.stitch([recent, older])
    assert joined[date(2024, 1, 14)] == 100
    assert joined[date(2023, 12, 31)] == pytest.approx(20)


class _FakeClient:
    def build_payload(self, terms, geo, timeframe):
        self.term = terms[0]

    def interest_over_time(self):
        idx = pd.to_datetime(["2025-01-05", "2025-01-12", "2025-01-19"])
        return pd.DataFrame({self.term: [30, 60, 90], "isPartial": [False, False, True]}, index=idx)


def test_pytrends_drops_the_partial_week():
    s = TrendsSource(client_factory=_FakeClient, pause=0)
    rows = s.fetch(terms=["Fiebre"], region="CO-NAR", since=date(2025, 1, 1), until=date(2025, 1, 20))
    assert len(rows) == 2 and s.last_source == "pytrends"
    assert rows[-1]["interest"] == 100  # renormalized to the period's maximum
    assert rows[0]["term"] == "fiebre"


def _blocked_client():
    raise RuntimeError("HTTP 429 Too Many Requests")


def test_csv_fallback_when_google_blocks(tmp_path):
    (tmp_path / "multiTimeline.csv").write_text(GOOGLE_CSV, encoding="utf-8")
    s = TrendsSource(fallback=CsvTrendsSource(tmp_path), client_factory=_blocked_client, pause=0)
    rows = s.fetch(terms=["fiebre"], region="CO-NAR", since=date(2024, 12, 1))
    assert s.last_source == "csv"
    assert {r["interest"] for r in rows} == {54.0, 61.0}


def test_service_stores_in_the_database_then_uses_the_cache(db, tmp_path):
    today = date.today()
    csv = "term,week_start,interest\n" + "\n".join(
        f"{t},{(today - pd.Timedelta(days=7 * k)).isoformat()},{10 + k}" for t in
        ("gripa", "tos", "fiebre", "dolor de garganta", "diarrea", "dengue", "ceniza volcán") for k in range(1, 6))
    (tmp_path / "fallback.csv").write_text(csv, encoding="utf-8")
    source = TrendsSource(fallback=CsvTrendsSource(tmp_path), client_factory=_blocked_client, pause=0)
    service = SearchTrendService(db, source=source)
    r1 = service.sync()
    assert r1.source == "csv" and r1.saved_rows > 0
    assert db.query(SearchTrend).filter_by(term="gripa").count() == 5
    r2 = service.sync()
    assert r2.source == "cache" and r2.saved_rows == 0


def test_sync_requires_admin(client, citizen_headers):
    assert client.post("/api/v1/data/trends/sync", headers=citizen_headers).status_code == 403
