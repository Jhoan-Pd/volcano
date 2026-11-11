"""CSV and PDF reports."""
import csv
import io


def _rows(content: bytes) -> list[list[str]]:
    text = content.decode("utf-8")
    assert text.startswith("﻿")  # BOM for Excel
    return list(csv.reader(io.StringIO(text.lstrip("﻿"))))


def test_cases_csv_with_filters(client):
    r = client.get("/api/v1/reports/cases.csv", params={"municipality_id": 1, "since_year": 2000})
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"] and r.headers["content-type"].startswith("text/csv")
    assert 'filename="casos-' in r.headers["content-disposition"]  # file names stay Spanish
    rows = _rows(r.content)
    assert rows[0][:3] == ["divipola_code", "municipality", "disease"]
    assert all(row[0] == "52001" for row in rows[1:])


def test_predictions_and_alerts_csv(client):
    assert _rows(client.get("/api/v1/reports/predictions.csv").content)[0][6] == "horizon_weeks"
    assert _rows(client.get("/api/v1/reports/alerts.csv").content)[0][5] == "risk_level"


def test_summary_pdf(client):
    r = client.get("/api/v1/reports/summary.pdf", params={"municipality_id": 1})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert "reporte-riesgo-pasto" in r.headers["content-disposition"]


def test_pdf_of_an_unknown_municipality(client):
    assert client.get("/api/v1/reports/summary.pdf", params={"municipality_id": 9999}).status_code == 404
