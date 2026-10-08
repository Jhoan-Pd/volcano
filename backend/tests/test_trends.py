"""Google Trends: parseo de CSV, empalme de ventanas, respaldo automático y caché en BD."""
from datetime import date

import pandas as pd
import pytest

from app.core.epi import semana_de
from app.fuentes import FuenteDatosError
from app.fuentes.trends import CsvTrendsFuente, TrendsFuente
from app.models import TendenciaBusqueda
from app.services.tendencia_service import TendenciaService

CSV_GOOGLE = """Categoría: Todas las categorías

Semana,fiebre: (Nariño),dengue: (Nariño)
2025-01-05,54,<1
2025-01-12,61,3
"""

CSV_LARGO = """termino,fecha_semana,indice,region,es_simulado
gripa,2025-01-05,40,CO-NAR,0
gripa,2025-01-12,45,CO-NAR,1
"""


def test_parsea_exportacion_de_google():
    filas = CsvTrendsFuente.parsear(CSV_GOOGLE)
    assert len(filas) == 4
    dengue = [f for f in filas if f["termino"] == "dengue"]
    assert dengue[0]["indice"] == 0.5  # "<1" se interpreta como interés muy bajo
    assert (dengue[0]["anio"], dengue[0]["semana_epi"]) == semana_de(date(2025, 1, 5))


def test_parsea_formato_largo_y_marca_simulados():
    filas = CsvTrendsFuente.parsear(CSV_LARGO)
    assert [f["es_simulado"] for f in filas] == [False, True]
    assert filas[1]["fuente"] == "simulado"


def test_csv_sin_encabezado_falla():
    with pytest.raises(FuenteDatosError):
        CsvTrendsFuente.parsear("hola\nmundo")


def test_ventanas_menores_a_cinco_anios_con_solape():
    v = TrendsFuente.ventanas(date(2019, 1, 1), date(2026, 10, 1))
    assert len(v) == 2
    assert v[-1][0] == date(2019, 1, 1)
    assert v[1][1] > v[0][0]  # hay solape entre ventanas consecutivas
    assert all((fin - ini).days <= 1800 for ini, fin in v)


def test_empalme_reescala_por_el_solape():
    reciente = {date(2024, 1, 7): 50.0, date(2024, 1, 14): 100.0}
    antigua = {date(2023, 12, 31): 10.0, date(2024, 1, 7): 25.0, date(2024, 1, 14): 50.0}  # escala x0,5
    unida = TrendsFuente.empalmar([reciente, antigua])
    assert unida[date(2024, 1, 14)] == 100
    assert unida[date(2023, 12, 31)] == pytest.approx(20)


class _ClienteFalso:
    def build_payload(self, terminos, geo, timeframe):
        self.termino = terminos[0]

    def interest_over_time(self):
        idx = pd.to_datetime(["2025-01-05", "2025-01-12", "2025-01-19"])
        return pd.DataFrame({self.termino: [30, 60, 90], "isPartial": [False, False, True]}, index=idx)


def test_pytrends_descarta_semana_parcial():
    f = TrendsFuente(cliente_factory=_ClienteFalso, pausa=0)
    filas = f.obtener(terminos=["Fiebre"], region="CO-NAR", desde=date(2025, 1, 1), hasta=date(2025, 1, 20))
    assert len(filas) == 2 and f.ultima_fuente == "pytrends"
    assert filas[-1]["indice"] == 100  # renormalizado al máximo del periodo
    assert filas[0]["termino"] == "fiebre"


def _cliente_bloqueado():
    raise RuntimeError("HTTP 429 Too Many Requests")


def test_respaldo_csv_si_google_bloquea(tmp_path):
    (tmp_path / "multiTimeline.csv").write_text(CSV_GOOGLE, encoding="utf-8")
    f = TrendsFuente(respaldo=CsvTrendsFuente(tmp_path), cliente_factory=_cliente_bloqueado, pausa=0)
    filas = f.obtener(terminos=["fiebre"], region="CO-NAR", desde=date(2024, 12, 1))
    assert f.ultima_fuente == "csv"
    assert {r["indice"] for r in filas} == {54.0, 61.0}


def test_servicio_guarda_en_bd_y_luego_usa_cache(db, tmp_path):
    hoy = date.today()
    csv = "termino,fecha_semana,indice\n" + "\n".join(
        f"{t},{(hoy - pd.Timedelta(days=7 * k)).isoformat()},{10 + k}" for t in
        ("gripa", "tos", "fiebre", "dolor de garganta", "diarrea", "dengue", "ceniza volcán") for k in range(1, 6))
    (tmp_path / "respaldo.csv").write_text(csv, encoding="utf-8")
    fuente = TrendsFuente(respaldo=CsvTrendsFuente(tmp_path), cliente_factory=_cliente_bloqueado, pausa=0)
    servicio = TendenciaService(db, fuente=fuente)
    r1 = servicio.sincronizar()
    assert r1.fuente == "csv" and r1.registros_guardados > 0
    assert db.query(TendenciaBusqueda).filter_by(termino="gripa").count() == 5
    r2 = servicio.sincronizar()
    assert r2.fuente == "cache" and r2.registros_guardados == 0


def test_sincronizar_requiere_admin(client, ciudadano_headers):
    assert client.post("/api/v1/datos/sincronizar/tendencias", headers=ciudadano_headers).status_code == 403
