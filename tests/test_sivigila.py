"""SIVIGILA (Socrata): SoQL query, row adaptation, pagination and replacement of simulated data."""
import httpx
import pytest

from volcano.models import Disease, Municipality, OfficialCase
from volcano.services.sivigila import SivigilaService
from volcano.sources import DataSourceError
from volcano.sources.sivigila import SivigilaSource

RESPONSE = [
    {"cod_eve": "210", "cod_mun_o": "52001", "ano": "2021", "semana": "5", "casos": "2"},
    {"cod_eve": "220", "cod_mun_o": "52001", "ano": "2021", "semana": "5", "casos": "1"},
    {"cod_eve": "210", "cod_mun_o": "52683", "ano": "2021", "semana": "30", "casos": "4"},
    {"cod_eve": "210", "cod_mun_o": "52835", "ano": "2021", "semana": "8", "casos": "9"},  # Tumaco: outside the area
    {"cod_eve": "210", "cod_mun_o": "52001", "ano": "2021"},  # incomplete: dropped
]


def _client(responses: list, seen: list):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(dict(request.url.params))
        return httpx.Response(200, json=responses.pop(0) if responses else [])
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_soql_query_aggregates_on_the_server():
    q = SivigilaSource.build_query(["210", "220"], "52", 2020)
    assert "cod_eve in('210','220')" in q["$where"] and "cod_dpto_o='52'" in q["$where"]
    assert "sum(conteo)" in q["$select"] and q["$group"].startswith("cod_eve")
    with pytest.raises(ValueError):
        SivigilaSource.build_query(["21'0 OR 1=1"], "52", 2020)  # prevents SoQL injection


def test_adapts_and_drops_incomplete_rows():
    seen: list = []
    s = SivigilaSource(client=_client([list(RESPONSE)], seen), app_token="")
    rows = s.fetch(event_codes=["210", "220"], since_year=2020)
    assert len(rows) == 4
    assert rows[0] == {"event_code": "210", "divipola_code": "52001", "year": 2021, "epi_week": 5, "cases": 2}
    assert seen[0]["$offset"] == "0"


def test_http_error_becomes_a_source_error():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400, text="bad query")))
    with pytest.raises(DataSourceError):
        SivigilaSource(client=client).fetch(event_codes=["210"])


def test_service_replaces_simulated_data_and_fills_zeros(db):
    dengue = db.query(Disease).filter_by(code="DENGUE").one()
    pasto = db.query(Municipality).filter_by(divipola_code="52001").one()
    db.add(OfficialCase(municipality_id=pasto.id, disease_id=dengue.id, year=2021, epi_week=5, cases=0,
                        source="SIVIGILA (simulated)", is_simulated=True))
    db.commit()

    seen: list = []
    service = SivigilaService(db, source=SivigilaSource(client=_client([list(RESPONSE)], seen)))
    r = service.sync(since_year=2020)
    assert r.diseases == ["DENGUE"] and r.years_covered == [2021]

    c = db.query(OfficialCase).filter_by(municipality_id=pasto.id, disease_id=dengue.id, year=2021, epi_week=5).one()
    assert c.cases == 3 and c.is_simulated is False  # 210 + 220 added up, official data
    weeks = db.query(OfficialCase).filter_by(municipality_id=pasto.id, disease_id=dengue.id, year=2021).count()
    assert weeks == 52  # 2021 has 52 epidemiological weeks; the missing ones are stored as 0
    assert db.query(OfficialCase).filter_by(disease_id=dengue.id, year=2021, cases=9).count() == 0  # not Tumaco


def test_sivigila_sync_requires_admin(client, citizen_headers):
    assert client.post("/api/v1/data/sivigila/sync", headers=citizen_headers).status_code == 403
