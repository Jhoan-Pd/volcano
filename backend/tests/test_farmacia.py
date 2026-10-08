"""Módulo de farmacias: reglas del reporte semanal, permisos por rol e índice de ventas."""
import pandas as pd
import pytest

from app.core.epi import desplazar, ultima_semana_completa
from app.fuentes.farmacia import FarmaciaFuente
from app.models import Farmacia, Municipio, Usuario

URL = "/api/v1/farmacia"


@pytest.fixture(scope="module")
def farmacia_demo():
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        usuario = db.query(Usuario).filter_by(email="farmacia@demo.co").one()
        f = db.query(Farmacia).filter_by(usuario_id=usuario.id).first()
        if f is None:
            pasto = db.query(Municipio).filter_by(codigo_divipola="52001").one()
            f = Farmacia(nombre="Droguería Test", nit="900000001-1", municipio_id=pasto.id, usuario_id=usuario.id)
            db.add(f)
            db.commit()
        return f.id


def _cuerpo(anio, semana, **extra):
    return {"anio": anio, "semana_epi": semana, **extra,
            "items": [{"categoria": "ANTIGRIPALES", "unidades": 120}, {"categoria": "TAPABOCAS", "unidades": 40}]}


def test_mi_farmacia_lista_semanas_reportables(client, farmacia_headers, farmacia_demo):
    r = client.get(f"{URL}/mi-farmacia", headers=farmacia_headers)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["id"] == farmacia_demo and len(datos["semanas_reportables"]) == 8
    assert (datos["semanas_reportables"][0]["anio"], datos["semanas_reportables"][0]["semana_epi"]) == ultima_semana_completa()


def test_crear_editar_y_eliminar_reporte(client, farmacia_headers, farmacia_demo):
    a, s = ultima_semana_completa()
    r = client.post(f"{URL}/reportes", json=_cuerpo(a, s), headers=farmacia_headers)
    assert r.status_code == 201, r.text
    assert r.json()["total_unidades"] == 160 and r.json()["reportado_por"] == "Farmacia Demo Centro"

    # La misma semana no se puede crear dos veces
    assert client.post(f"{URL}/reportes", json=_cuerpo(a, s), headers=farmacia_headers).status_code == 409

    r = client.put(f"{URL}/reportes/{a}/{s}", headers=farmacia_headers,
                   json={"items": [{"categoria": "ANTIGRIPALES", "unidades": 150}]})
    assert r.status_code == 200 and r.json()["total_unidades"] == 150

    historial = client.get(f"{URL}/reportes", headers=farmacia_headers).json()
    assert historial[0]["semana_epi"] == s and historial[0]["editable"] is True

    assert client.delete(f"{URL}/reportes/{a}/{s}", headers=farmacia_headers).status_code == 204
    assert client.get(f"{URL}/reportes/{a}/{s}", headers=farmacia_headers).status_code == 404


def test_validaciones_del_formulario(client, farmacia_headers, farmacia_demo):
    a, s = ultima_semana_completa()
    repetida = {"anio": a, "semana_epi": s, "items": [{"categoria": "TAPABOCAS", "unidades": 1}] * 2}
    assert client.post(f"{URL}/reportes", json=repetida, headers=farmacia_headers).status_code == 422
    negativa = {"anio": a, "semana_epi": s, "items": [{"categoria": "TAPABOCAS", "unidades": -5}]}
    assert client.post(f"{URL}/reportes", json=negativa, headers=farmacia_headers).status_code == 422
    sin_semana_53 = {"anio": 2025, "semana_epi": 53, "items": [{"categoria": "TAPABOCAS", "unidades": 1}]}
    assert client.post(f"{URL}/reportes", json=sin_semana_53, headers=farmacia_headers).status_code == 422


def test_semana_futura_o_muy_antigua_rechazada(client, farmacia_headers, farmacia_demo):
    futura = desplazar(*ultima_semana_completa(), 2)
    r = client.post(f"{URL}/reportes", json=_cuerpo(*futura), headers=farmacia_headers)
    assert r.status_code == 422 and "terminadas" in r.json()["error"]["mensaje"]
    vieja = desplazar(*ultima_semana_completa(), -20)
    r = client.post(f"{URL}/reportes", json=_cuerpo(*vieja), headers=farmacia_headers)
    assert r.status_code == 422 and "últimas 8 semanas" in r.json()["error"]["mensaje"]


def test_admin_reporta_semanas_antiguas_indicando_farmacia(client, admin_headers, farmacia_demo):
    vieja = desplazar(*ultima_semana_completa(), -20)
    assert client.post(f"{URL}/reportes", json=_cuerpo(*vieja), headers=admin_headers).status_code == 422  # falta farmacia_id
    r = client.post(f"{URL}/reportes", json=_cuerpo(*vieja, farmacia_id=farmacia_demo), headers=admin_headers)
    assert r.status_code == 201, r.text


def test_ciudadano_no_accede(client, ciudadano_headers):
    assert client.get(f"{URL}/mi-farmacia", headers=ciudadano_headers).status_code == 403
    assert client.get(f"{URL}/mi-farmacia").status_code == 401


def test_indice_compara_con_las_semanas_anteriores():
    filas = []
    for semana in range(1, 11):
        unidades = 100 if semana < 10 else 150  # +50 % en la semana 10
        filas += [{"municipio_id": 1, "farmacia_id": f, "anio": 2025, "semana_epi": semana,
                   "categoria": "ANTIGRIPALES", "unidades": unidades} for f in (1, 2)]
    # En la semana 10 solo reporta una farmacia: el índice se calcula por farmacia que reporta
    filas = [f for f in filas if not (f["semana_epi"] == 10 and f["farmacia_id"] == 2)]
    g = FarmaciaFuente.calcular_indice(pd.DataFrame(filas))
    ultima = g[g["semana_epi"] == 10].iloc[0]
    assert ultima["farmacias_reportando"] == 1 and ultima["indice"] == pytest.approx(150.0)
    assert pd.isna(g[g["semana_epi"] == 2].iloc[0]["indice"])  # sin suficiente historia (mín. 4 semanas)
