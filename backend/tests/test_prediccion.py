"""Modelo predictivo: sin fuga de datos, comparación contra la línea base, intervalos,
explicabilidad y endpoints del semáforo predictivo."""
import math

import numpy as np
import pandas as pd
import pytest

from app.core.epi import iterar_semanas
from app.ml.dataset import FEATURES, GRUPOS, ConstructorDataset
from app.ml.entrenador import DatosInsuficientesError, Entrenador, mae
from app.ml.explicador import contribuciones
from app.ml.modelos import BosqueAleatorio, PromedioMovil
from app.models import CasoOficial, Enfermedad, ModeloEntrenado, Municipio, Prediccion
from app.services.prediccion_service import PrediccionService

SEMANAS = list(iterar_semanas((2023, 1), (2026, 20)))


@pytest.fixture(scope="module")
def eda_con_casos():
    """Serie sintética de EDA para 2 municipios: estacionalidad + ruido (3,4 años de semanas)."""
    from app.db.session import SessionLocal

    rng = np.random.default_rng(0)
    with SessionLocal() as db:
        eda = db.query(Enfermedad).filter_by(codigo="EDA").one()
        if db.query(CasoOficial).filter_by(enfermedad_id=eda.id).count() == 0:
            for codigo, base in (("52001", 60), ("52683", 4)):
                m = db.query(Municipio).filter_by(codigo_divipola=codigo).one()
                for i, (a, s) in enumerate(SEMANAS):
                    lam = base * (1 + 0.4 * math.sin(2 * math.pi * s / 52)) * (1 + 0.002 * i)
                    db.add(CasoOficial(municipio_id=m.id, enfermedad_id=eda.id, anio=a, semana_epi=s,
                                       casos=int(rng.poisson(lam)), es_simulado=True))
            db.commit()
        return eda.id


def test_dataset_sin_fuga_de_datos(db, eda_con_casos):
    """Cambiar los casos FUTUROS no puede cambiar las variables de la semana t."""
    eda = db.get(Enfermedad, eda_con_casos)
    df = ConstructorDataset(db).construir(eda)
    fila = df[(df["anio"] == 2025) & (df["semana_epi"] == 10)].iloc[0]
    futuros = db.query(CasoOficial).filter(CasoOficial.enfermedad_id == eda.id, CasoOficial.anio == 2025,
                                           CasoOficial.semana_epi.between(11, 14)).all()
    originales = [c.casos for c in futuros]
    for c in futuros:
        c.casos += 500
    db.commit()
    try:
        df2 = ConstructorDataset(db).construir(eda)
        misma = (df2["municipio_id"] == fila["municipio_id"]) & (df2["anio"] == 2025) & (df2["semana_epi"] == 10)
        fila2 = df2[misma].iloc[0]
        pd.testing.assert_series_equal(fila[FEATURES], fila2[FEATURES], check_names=False)
        assert fila2["y_h1"] == fila["y_h1"] + 500  # el objetivo sí cambia: es el futuro
    finally:
        for c, v in zip(futuros, originales, strict=True):
            c.casos = v
        db.commit()


def test_todas_las_variables_tienen_grupo():
    assert len(FEATURES) == len(set(FEATURES)) == sum(len(v) for v in GRUPOS.values())


def test_promedio_movil_es_la_linea_base():
    X = pd.DataFrame({"y_ma4": [np.log1p(10.0), np.log1p(0.0)]})
    assert PromedioMovil().predecir(X) == pytest.approx([10.0, 0.0])


def test_datos_insuficientes():
    with pytest.raises(DatosInsuficientesError):
        Entrenador().entrenar(pd.DataFrame())


def test_modelo_aprende_una_senal_que_la_base_no_ve():
    """Si los casos futuros dependen de las búsquedas, el bosque debe ganarle al promedio móvil."""
    rng = np.random.default_rng(1)
    n = 400
    X = pd.DataFrame({f: rng.normal(size=n) for f in FEATURES})
    X["y_ma4"] = np.log1p(20.0)
    y = 20 * np.exp(0.8 * X["busq_l0"])
    m = BosqueAleatorio().ajustar(X.iloc[:300], y.iloc[:300])
    assert mae(y.iloc[300:], m.predecir(X.iloc[300:])) < 0.6 * mae(y.iloc[300:], PromedioMovil().predecir(X.iloc[300:]))
    _, contrib = contribuciones(m, X.iloc[[350]], X.median().to_dict())
    assert max(contrib, key=lambda g: abs(contrib[g])) == "Búsquedas en internet"


def test_entrenar_guardar_y_predecir(db, eda_con_casos):
    servicio = PrediccionService(db, entrenador=Entrenador(semanas_prueba=26, repeticiones_permutacion=1))
    modelos, errores = servicio.entrenar(eda_con_casos)
    assert not errores and len(modelos) == 1
    m = modelos[0]
    assert m.activo and m.artefacto and m.algoritmo in ("Random Forest", "Gradient Boosting")
    assert m.mae_base > 0 and m.mae_modelo > 0 and m.rmse_modelo >= m.mae_modelo
    assert sum(m.importancias["grupos"].values()) == pytest.approx(100, abs=0.5)

    preds = db.query(Prediccion).filter_by(modelo_id=m.id).all()
    assert len(preds) == 2 * 4  # 2 municipios × 4 semanas
    for p in preds:
        assert p.limite_inferior <= p.casos_esperados <= p.limite_superior
        assert p.nivel_riesgo in ("VERDE", "AMARILLO", "NARANJA", "ROJO")

    # Reentrenar desactiva el modelo anterior y libera su binario
    modelos2, _ = servicio.entrenar(eda_con_casos)
    db.refresh(m)
    assert not m.activo and m.artefacto is None and modelos2[0].activo
    assert db.query(ModeloEntrenado).filter_by(enfermedad_id=eda_con_casos).count() == 2


def test_endpoints_de_prediccion(client, eda_con_casos):
    pasto = 1
    r = client.get("/api/v1/dashboard/prediccion", params={"municipio_id": pasto, "enfermedad_id": eda_con_casos})
    assert r.status_code == 200, r.text
    datos = r.json()
    assert [p["horizonte"] for p in datos["puntos"]] == [1, 2, 3, 4]
    assert datos["modelo"]["mae_base"] is not None and len(datos["backtest"]) > 0

    r = client.get("/api/v1/dashboard/explicacion", params={"municipio_id": pasto, "enfermedad_id": eda_con_casos})
    assert r.status_code == 200, r.text
    assert {f["grupo"] for f in r.json()["factores"]} == set(GRUPOS)

    historial = client.get("/api/v1/modelo/historial", params={"enfermedad_id": eda_con_casos}).json()
    assert historial[0]["activo"] and historial[0]["mejora_mae_pct"] is not None


def test_reentrenar_solo_admin(client, ciudadano_headers):
    assert client.post("/api/v1/modelo/reentrenar", headers=ciudadano_headers).status_code == 403
    assert client.get("/api/v1/modelo/estado").status_code == 401
