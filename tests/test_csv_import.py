"""CSV upload from the admin panel."""
from volcano.models import OfficialCase, VolcanicEvent


def _upload(client, headers, kind, text):
    return client.post(f"/api/v1/data/import/{kind}", headers=headers,
                       files={"file": (f"{kind}.csv", text.encode("utf-8"), "text/csv")})


def test_cases_insert_then_update(client, admin_headers, db):
    csv = "divipola_code,disease,year,epi_week,cases\n52001,IRA,2019,10,77\n52001,IRA,2019,11,80\n"
    r = _upload(client, admin_headers, "cases", csv)
    assert r.status_code == 200, r.text
    assert r.json()["inserted"] == 2 and r.json()["errors"] == []
    r = _upload(client, admin_headers, "cases", csv.replace(",77", ",99"))
    assert r.json()["updated"] == 2 and r.json()["inserted"] == 0
    c = db.query(OfficialCase).filter_by(year=2019, epi_week=10).one()
    assert c.cases == 99 and c.source == "CSV" and not c.is_simulated


def test_legacy_spanish_headers_are_accepted(client, admin_headers):
    csv = "cod_divipola,enfermedad,anio,semana_epi,casos\n52001,IRA,2019,14,12\n"
    r = _upload(client, admin_headers, "cases", csv)
    assert r.status_code == 200 and r.json()["inserted"] == 1, r.text


def test_invalid_rows_are_reported_with_their_line(client, admin_headers):
    csv = ("divipola_code;disease;year;epi_week;cases\n"  # ; separator (Excel in Spanish)
           "52001;IRA;2019;12;5\n99999;IRA;2019;12;5\n52001;XYZ;2019;12;5\n52001;IRA;2019;60;5\n52001;IRA;2019;13;-1\n")
    data = _upload(client, admin_headers, "cases", csv).json()
    assert data["rows_read"] == 5 and data["inserted"] == 1
    assert [e["row"] for e in data["errors"]] == [3, 4, 5, 6]


def test_missing_columns_and_unknown_kind(client, admin_headers):
    r = _upload(client, admin_headers, "cases", "municipality,cases\nPasto,3\n")
    assert r.status_code == 422 and "Faltan columnas" in r.json()["error"]["message"]
    assert _upload(client, admin_headers, "other", "a\n1\n").status_code == 422


def test_events_validate_ash_falls(client, admin_headers, db):
    csv = ("event_type,activity_level,start_date,divipola_code,ash_intensity,so2_tons_per_day,description\n"
           "ASH_FALL,YELLOW,2019-03-01,52207,2,,prueba\nCAIDA_CENIZA,AMARILLO,2019-03-02,,0,,sin municipio\n")
    r = _upload(client, admin_headers, "events", csv)
    assert r.json()["inserted"] == 1 and len(r.json()["errors"]) == 1
    assert db.query(VolcanicEvent).filter_by(description="prueba").count() == 1


def test_trends_and_weather(client, admin_headers):
    r = _upload(client, admin_headers, "trends", "term,week_start,interest\nfiebre,2019-01-06,40\ntos,2019-01-06,140\n")
    assert r.json()["inserted"] == 1 and r.json()["errors"][0]["row"] == 3
    r = _upload(client, admin_headers, "weather",
                "divipola_code,date,temp_max_c,temp_min_c,temp_mean_c,precipitation_mm,relative_humidity_pct\n"
                "52001,2019-01-01,19,8,13,2.5,85\n")
    assert r.json()["inserted"] == 1


def test_import_and_status_are_admin_only(client, citizen_headers, admin_headers):
    assert _upload(client, citizen_headers, "cases", "x\n").status_code == 403
    assert client.get("/api/v1/data/status", headers=citizen_headers).status_code == 403
    status = client.get("/api/v1/data/status", headers=admin_headers).json()
    assert {s["table"] for s in status["sources"]} >= {"official_cases", "weather_records", "predictions"}
