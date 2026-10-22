"""Estructuras de datos y número de consultas: evitan regresiones de rendimiento (N+1)."""
from contextlib import contextmanager
from datetime import date

from sqlalchemy import event

from app.db.session import engine
from app.models import CasoOficial, Enfermedad, Municipio, RegistroClima
from app.repositories.repos import RegistroClimaRepository


@contextmanager
def contar_consultas():
    contador = {"n": 0}

    def _contar(*_):
        contador["n"] += 1

    event.listen(engine, "before_cursor_execute", _contar)
    try:
        yield contador
    finally:
        event.remove(engine, "before_cursor_execute", _contar)


def test_upsert_generico_inserta_y_actualiza_con_una_consulta_de_lectura(db):
    repo = RegistroClimaRepository(db)
    filas = [{"municipio_id": 1, "fecha": date(2018, 1, d), "temp_media_c": 12.0} for d in (1, 2, 3)]
    clave = ("municipio_id", "fecha")
    alcance = [RegistroClima.fecha.in_([f["fecha"] for f in filas])]
    assert repo.upsert(filas, clave, alcance) == (3, 0)
    filas[0]["temp_media_c"] = 15.5
    with contar_consultas() as c:
        assert repo.upsert(filas, clave, alcance) == (0, 3)
    # 1 SELECT de existentes + escrituras del commit; nunca una lectura por fila
    selects = c["n"]
    assert selects <= 3
    assert db.query(RegistroClima).filter_by(municipio_id=1, fecha=date(2018, 1, 1)).one().temp_media_c == 15.5


def test_riesgo_por_municipio_no_hace_una_consulta_por_municipio(client, db):
    if db.query(CasoOficial).count() == 0:  # esta prueba puede correr sola: crea una serie mínima
        for m in db.query(Municipio):
            for e in db.query(Enfermedad):
                db.add_all(CasoOficial(municipio_id=m.id, enfermedad_id=e.id, anio=2014, semana_epi=s, casos=s % 5)
                           for s in range(1, 20))
        db.commit()
    with contar_consultas() as c:
        r = client.get("/api/v1/dashboard/riesgo-municipios")
    assert r.status_code == 200
    municipios, enfermedades = len(r.json()), 4
    # Antes: ~3 consultas por (municipio × enfermedad). Ahora: unas pocas por enfermedad.
    assert c["n"] < municipios * enfermedades
