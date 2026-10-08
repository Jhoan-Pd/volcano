"""SIVIGILA (Socrata): consulta SoQL, adaptación de filas, paginación y reemplazo de datos simulados."""
import httpx
import pytest

from app.fuentes import FuenteDatosError
from app.fuentes.sivigila import SivigilaFuente
from app.models import CasoOficial, Enfermedad, Municipio
from app.services.sivigila_service import SivigilaService

RESPUESTA = [
    {"cod_eve": "210", "cod_mun_o": "52001", "ano": "2021", "semana": "5", "casos": "2"},
    {"cod_eve": "220", "cod_mun_o": "52001", "ano": "2021", "semana": "5", "casos": "1"},
    {"cod_eve": "210", "cod_mun_o": "52683", "ano": "2021", "semana": "30", "casos": "4"},
    {"cod_eve": "210", "cod_mun_o": "52835", "ano": "2021", "semana": "8", "casos": "9"},  # Tumaco: fuera de la zona
    {"cod_eve": "210", "cod_mun_o": "52001", "ano": "2021"},  # incompleta: se descarta
]


def _cliente(respuestas: list, vistos: list):
    def manejador(request: httpx.Request) -> httpx.Response:
        vistos.append(dict(request.url.params))
        return httpx.Response(200, json=respuestas.pop(0) if respuestas else [])
    return httpx.Client(transport=httpx.MockTransport(manejador))


def test_consulta_soql_agrega_en_el_servidor():
    q = SivigilaFuente.consulta(["210", "220"], "52", 2020)
    assert "cod_eve in('210','220')" in q["$where"] and "cod_dpto_o='52'" in q["$where"]
    assert "sum(conteo)" in q["$select"] and q["$group"].startswith("cod_eve")
    with pytest.raises(ValueError):
        SivigilaFuente.consulta(["21'0 OR 1=1"], "52", 2020)  # evita inyección en la consulta SoQL


def test_adapta_y_descarta_filas_incompletas():
    vistos: list = []
    f = SivigilaFuente(cliente=_cliente([list(RESPUESTA)], vistos), app_token="")
    filas = f.obtener(codigos_evento=["210", "220"], desde_anio=2020)
    assert len(filas) == 4
    assert filas[0] == {"cod_eve": "210", "cod_divipola": "52001", "anio": 2021, "semana_epi": 5, "casos": 2}
    assert vistos[0]["$offset"] == "0"


def test_error_http_se_convierte_en_error_de_fuente():
    cliente = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400, text="bad query")))
    with pytest.raises(FuenteDatosError):
        SivigilaFuente(cliente=cliente).obtener(codigos_evento=["210"])


def test_servicio_reemplaza_simulados_y_completa_ceros(db):
    dengue = db.query(Enfermedad).filter_by(codigo="DENGUE").one()
    pasto = db.query(Municipio).filter_by(codigo_divipola="52001").one()
    db.add(CasoOficial(municipio_id=pasto.id, enfermedad_id=dengue.id, anio=2021, semana_epi=5, casos=0,
                       fuente="SIVIGILA (simulado)", es_simulado=True))
    db.commit()

    vistos: list = []
    servicio = SivigilaService(db, fuente=SivigilaFuente(cliente=_cliente([list(RESPUESTA)], vistos)))
    r = servicio.sincronizar(desde_anio=2020)
    assert r.enfermedades == ["DENGUE"] and r.anios_cubiertos == [2021]

    c = db.query(CasoOficial).filter_by(municipio_id=pasto.id, enfermedad_id=dengue.id, anio=2021, semana_epi=5).one()
    assert c.casos == 3 and c.es_simulado is False  # 210 + 220 sumados, dato oficial
    semanas = db.query(CasoOficial).filter_by(municipio_id=pasto.id, enfermedad_id=dengue.id, anio=2021).count()
    assert semanas == 52  # 2021 tiene 52 semanas epidemiológicas; las ausentes quedan en 0
    assert db.query(CasoOficial).filter_by(enfermedad_id=dengue.id, anio=2021, casos=9).count() == 0  # Tumaco no


def test_sincronizar_sivigila_requiere_admin(client, ciudadano_headers):
    assert client.post("/api/v1/datos/sincronizar/sivigila", headers=ciudadano_headers).status_code == 403
