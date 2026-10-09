"""Reportes CSV y PDF."""
import csv
import io


def _filas(contenido: bytes) -> list[list[str]]:
    texto = contenido.decode("utf-8")
    assert texto.startswith("﻿")  # BOM para Excel
    return list(csv.reader(io.StringIO(texto.lstrip("﻿"))))


def test_casos_csv_con_filtros(client):
    r = client.get("/api/v1/reportes/casos.csv", params={"municipio_id": 1, "desde_anio": 2000})
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"] and r.headers["content-type"].startswith("text/csv")
    filas = _filas(r.content)
    assert filas[0][:3] == ["cod_divipola", "municipio", "enfermedad"]
    assert all(f[0] == "52001" for f in filas[1:])


def test_predicciones_y_alertas_csv(client):
    assert _filas(client.get("/api/v1/reportes/predicciones.csv").content)[0][6] == "horizonte_semanas"
    assert _filas(client.get("/api/v1/reportes/alertas.csv").content)[0][5] == "nivel"


def test_resumen_pdf(client):
    r = client.get("/api/v1/reportes/resumen.pdf", params={"municipio_id": 1})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")
    assert "reporte-riesgo-pasto" in r.headers["content-disposition"]


def test_pdf_municipio_inexistente(client):
    assert client.get("/api/v1/reportes/resumen.pdf", params={"municipio_id": 9999}).status_code == 404
