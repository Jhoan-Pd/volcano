"""Pruebas del semáforo (canal endémico). En la Fase 2 se suman las del modelo predictivo."""
from app.core.epi import semanas_del_anio
from app.models.enums import NivelRiesgo
from app.services import riesgo_service as rs


def test_umbrales_por_percentiles():
    u = rs.calcular_umbrales(list(range(1, 21)), 50, 75, 90)
    assert u.amarillo == 10.5 and u.naranja == 15.25 and u.rojo == 18.1


def test_clasificacion_por_zona():
    u = rs.UmbralesCanal(amarillo=10, naranja=15, rojo=20)
    assert rs.clasificar(8, u) == NivelRiesgo.VERDE
    assert rs.clasificar(12, u) == NivelRiesgo.AMARILLO
    assert rs.clasificar(17, u) == NivelRiesgo.NARANJA
    assert rs.clasificar(25, u) == NivelRiesgo.ROJO


def test_piso_minimo_evita_falsas_alarmas():
    # dengue en Pasto: historial casi siempre en cero
    u = rs.calcular_umbrales([0] * 14 + [1], 50, 75, 90)
    assert rs.clasificar(1, u) == NivelRiesgo.VERDE
    assert rs.clasificar(rs.MIN_CASOS_ALERTA, u) == NivelRiesgo.ROJO


def test_sin_historia_suficiente_es_verde():
    assert rs.calcular_umbrales([5, 6], 50, 75, 90) is None
    assert rs.clasificar(100, None) == NivelRiesgo.VERDE


def test_semanas_referencia_maneja_semana_53():
    assert semanas_del_anio(2020) == 53
    pares = rs.semanas_referencia(2026, 53)
    assert len(pares) == 15
    assert (2021, 52) in pares  # 2021 no tiene semana 53 -> se usa la 52
    assert all(a < 2026 or (a == 2026 and s == 1) for a, s in pares)


def test_nivel_maximo():
    assert rs.nivel_maximo(["VERDE", "NARANJA", "AMARILLO"]) == "NARANJA"
    assert rs.nivel_maximo([]) == "VERDE"
