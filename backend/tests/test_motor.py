"""Motor de predicción gRPC: los cuatro tipos de RPC contra un servidor real en un puerto libre."""
import time

import grpc
import pytest
from grpc_health.v1 import health_pb2, health_pb2_grpc

from app.ml.escenarios import Ajustes, aplicar
from app.models import Alerta, Enfermedad, Farmacia, Municipio, Prediccion, ReporteFarmacia, Usuario
from app.motor.protos import prediccion_pb2 as pb
from app.services.entrenamiento import control
from tests.conftest import TOKEN_MOTOR

META = (("authorization", f"Bearer {TOKEN_MOTOR}"),)


def _ids(db, ira_id):
    pasto = db.query(Municipio).filter_by(codigo_divipola="52001").one().id
    return pasto, ira_id


# ── Seguridad y salud ────────────────────────────────────────────────────────
def test_sin_token_responde_unauthenticated(stub):
    with pytest.raises(grpc.RpcError) as exc:
        stub.Estado(pb.Vacio())
    assert exc.value.code() == grpc.StatusCode.UNAUTHENTICATED
    with pytest.raises(grpc.RpcError) as exc:
        stub.Estado(pb.Vacio(), metadata=(("authorization", "Bearer otro"),))
    assert exc.value.code() == grpc.StatusCode.UNAUTHENTICATED


def test_chequeo_de_salud_estandar_sin_token(motor_grpc):
    with grpc.insecure_channel(f"127.0.0.1:{motor_grpc.puerto}") as canal:
        r = health_pb2_grpc.HealthStub(canal).Check(
            health_pb2.HealthCheckRequest(service="predictor.motor.v1.MotorPrediccion"))
    assert r.status == health_pb2.HealthCheckResponse.SERVING


# ── Unary ────────────────────────────────────────────────────────────────────
def test_estado(stub):
    e = stub.Estado(pb.Vacio(), metadata=META)
    assert e.version and e.activo_desde_s >= 0 and e.rpcs_atendidas >= 1 and not e.entrenando


def test_predecir_coincide_con_lo_guardado_y_usa_la_cache(stub, db, ira_entrenada):
    pasto, ira = _ids(db, ira_entrenada)
    p = stub.Predecir(pb.SolicitudPrediccion(municipio_id=pasto, enfermedad_id=ira), metadata=META)
    assert [x.horizonte for x in p.puntos] == [1, 2, 3, 4]
    assert p.municipio == "Pasto" and p.algoritmo and p.semana_base
    for x in p.puntos:
        assert x.limite_inferior <= x.casos_esperados <= x.limite_superior
        assert x.nivel != pb.NIVEL_DESCONOCIDO

    # Mismo cálculo que el servicio que guarda las predicciones (Pronosticador compartido)
    guardadas = {g.horizonte: g.casos_esperados for g in db.query(Prediccion).filter_by(
        modelo_id=p.modelo_id, municipio_id=pasto)}
    assert {x.horizonte: x.casos_esperados for x in p.puntos} == guardadas

    otra = stub.Predecir(pb.SolicitudPrediccion(municipio_id=pasto, enfermedad_id=ira), metadata=META)
    assert otra.desde_cache and otra.duracion_ms < p.duracion_ms + 50


def test_predecir_sin_modelo_o_municipio_es_not_found(stub, db, ira_entrenada):
    sin_modelo = db.query(Enfermedad).filter_by(codigo="RESP_CENIZA").one().id
    with pytest.raises(grpc.RpcError) as exc:
        stub.Predecir(pb.SolicitudPrediccion(municipio_id=1, enfermedad_id=sin_modelo), metadata=META)
    assert exc.value.code() == grpc.StatusCode.NOT_FOUND and "modelo" in exc.value.details()
    with pytest.raises(grpc.RpcError) as exc:
        stub.Predecir(pb.SolicitudPrediccion(municipio_id=9999, enfermedad_id=ira_entrenada), metadata=META)
    assert exc.value.code() == grpc.StatusCode.NOT_FOUND


# ── Bidirectional ────────────────────────────────────────────────────────────
def test_aplicar_escenario_no_modifica_la_entrada():
    import pandas as pd

    X = pd.DataFrame([{"temp_l0": 14.0, "temp_l2": None, "temp_l4_6": 13.0, "lluvia_l0": 10.0, "lluvia_l1": 5.0,
                       "lluvia_l2_6": 8.0, "busq_l0": 50.0, "busq_var": 1.0, "farm_l0": None, "ceniza_l0_1": 0.0}])
    tipicos = {"temp_l2": 15.0, "farm_l0": 100.0}
    X2 = aplicar(X, Ajustes(delta_temperatura_c=2, cambio_lluvia_pct=50, cambio_farmacias_pct=20, ceniza=True),
                 tipicos)
    assert X.loc[0, "temp_l0"] == 14.0 and pd.isna(X.loc[0, "farm_l0"])  # la original queda igual
    assert X2.loc[0, "temp_l0"] == 16.0 and X2.loc[0, "temp_l2"] == 17.0  # vacío → típico + 2
    assert X2.loc[0, "lluvia_l0"] == 15.0 and X2.loc[0, "farm_l0"] == 120.0 and X2.loc[0, "ceniza_l0_1"] == 2
    assert X2.loc[0, "busq_l0"] == 50.0  # lo que no se pidió no cambia
    assert Ajustes(delta_temperatura_c=9).errores() and not Ajustes(cambio_lluvia_pct=-100).errores()


def test_simular_escenarios_es_una_conversacion(stub, db, ira_entrenada):
    pasto, ira = _ids(db, ira_entrenada)
    enviados = [
        pb.Escenario(id="base", municipio_id=pasto, enfermedad_id=ira),
        pb.Escenario(id="mas-busquedas", municipio_id=pasto, enfermedad_id=ira, cambio_busquedas_pct=200,
                     cambio_lluvia_pct=100, delta_temperatura_c=3),
        pb.Escenario(id="invalido", municipio_id=pasto, enfermedad_id=ira, delta_temperatura_c=40),
        pb.Escenario(id="sin-datos", municipio_id=9999, enfermedad_id=ira),
        pb.Escenario(id="otra-vez", municipio_id=pasto, enfermedad_id=ira, ceniza=True),
    ]
    respuestas = list(stub.SimularEscenarios(iter(enviados), metadata=META))

    assert [r.id for r in respuestas] == [e.id for e in enviados]  # una respuesta por escenario, en orden
    base, cambio, invalido, sin_datos, ultimo = respuestas
    assert not base.error and base.variacion_pct == 0
    assert [p.casos_esperados for p in base.escenario] == [p.casos_esperados for p in base.base]
    assert not cambio.error and len(cambio.escenario) == 4 and "°C" in cambio.resumen
    assert [p.casos_esperados for p in cambio.base] == [p.casos_esperados for p in base.base]
    assert "delta_temperatura_c" in invalido.error and not invalido.escenario  # el stream sigue vivo
    assert sin_datos.error and not ultimo.error and "ceniza" in ultimo.resumen


# ── Server streaming ─────────────────────────────────────────────────────────
def test_entrenar_transmite_el_avance_y_no_admite_dos_a_la_vez(stub, ira_entrenada):
    control.reiniciar()
    stream = stub.Entrenar(pb.SolicitudEntrenamiento(enfermedad_id=ira_entrenada), metadata=META)
    primero = next(stream)
    assert primero.etapa == pb.ProgresoEntrenamiento.INICIO

    with pytest.raises(grpc.RpcError) as exc:  # mientras corre, un segundo pedido se rechaza
        next(stub.Entrenar(pb.SolicitudEntrenamiento(enfermedad_id=ira_entrenada), metadata=META))
    assert exc.value.code() == grpc.StatusCode.ABORTED

    resto = list(stream)
    etapas = [pb.ProgresoEntrenamiento.Etapa.Name(m.etapa) for m in [primero, *resto]]
    porcentajes = [m.porcentaje for m in [primero, *resto]]
    assert etapas[-1] == "FIN" and {"DATASET", "CANDIDATO", "MODELO_LISTO", "ALERTAS"} <= set(etapas)
    assert porcentajes == sorted(porcentajes) and porcentajes[-1] == 100
    assert any(m.HasField("mae_base") for m in resto)
    assert not control.estado().en_curso


def test_seguir_alertas_envia_las_activas_y_luego_los_cambios(stub, db, ira_entrenada):
    consaca = db.query(Municipio).filter_by(codigo_divipola="52207").one().id

    def alerta(semana: int, nivel: str = "NARANJA") -> Alerta:
        a = Alerta(municipio_id=consaca, enfermedad_id=ira_entrenada, anio=2020, semana_epi=semana,
                   nivel_riesgo=nivel, origen="OBSERVADO", mensaje=f"Prueba S{semana}", activa=True)
        db.add(a)
        db.commit()
        return a

    previa = alerta(1)
    stream = stub.SeguirAlertas(pb.FiltroAlertas(municipio_id=consaca), metadata=META, timeout=20)
    try:
        inicial = next(stream)
        assert inicial.tipo == pb.EventoAlerta.ACTIVA and inicial.alerta.municipio_id == consaca

        nueva = alerta(2, "ROJO")
        evento = next(e for e in stream if e.alerta.id == nueva.id)
        assert evento.tipo == pb.EventoAlerta.NUEVA and evento.alerta.nivel == pb.ROJO

        previa.activa = False
        db.commit()
        evento = next(e for e in stream if e.alerta.id == previa.id)
        assert evento.tipo == pb.EventoAlerta.CERRADA
    finally:
        stream.cancel()
        db.query(Alerta).filter(Alerta.anio == 2020, Alerta.municipio_id == consaca).delete()
        db.commit()


def test_cancelar_el_stream_libera_la_suscripcion(stub, motor_grpc):
    difusor = motor_grpc.servicer.difusor
    stream = stub.SeguirAlertas(pb.FiltroAlertas(), metadata=META)
    stream.initial_metadata()  # espera a que la RPC esté abierta
    time.sleep(0.3)
    assert difusor.suscriptores >= 1
    stream.cancel()
    for _ in range(30):
        if difusor.suscriptores == 0:
            break
        time.sleep(0.1)
    assert difusor.suscriptores == 0


# ── Client streaming ─────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def farmacia_grpc():
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        f = db.query(Farmacia).filter_by(nit="900000999-9").first()
        if f is None:
            pasto = db.query(Municipio).filter_by(codigo_divipola="52001").one()
            f = Farmacia(nombre="Droguería gRPC", nit="900000999-9", municipio_id=pasto.id)
            db.add(f)
            db.commit()
        yield f.id
        db.query(ReporteFarmacia).filter_by(farmacia_id=f.id).delete()
        db.commit()


def _actor(db, email: str) -> tuple[tuple[str, str], ...]:
    return (*META, ("x-actor-id", str(db.query(Usuario).filter_by(email=email).one().id)))


def test_cargar_reportes_valida_cada_fila_y_agrupa_por_semana(stub, db, farmacia_grpc):
    filas = [
        pb.FilaReporteFarmacia(fila=2, farmacia_id=farmacia_grpc, anio=2024, semana_epi=10, categoria="ANTIGRIPALES",
                               unidades=120),
        pb.FilaReporteFarmacia(fila=3, farmacia_id=farmacia_grpc, anio=2024, semana_epi=10, categoria="tapabocas",
                               unidades=40),
        pb.FilaReporteFarmacia(fila=4, farmacia_id=farmacia_grpc, anio=2024, semana_epi=11, categoria="ANTIGRIPALES",
                               unidades=90),
        pb.FilaReporteFarmacia(fila=5, farmacia_id=farmacia_grpc, anio=2024, semana_epi=11, categoria="JARABES",
                               unidades=5),
        pb.FilaReporteFarmacia(fila=6, farmacia_id=farmacia_grpc, anio=2024, semana_epi=11, categoria="ANTIGRIPALES",
                               unidades=7),
        pb.FilaReporteFarmacia(fila=7, farmacia_id=farmacia_grpc, anio=2024, semana_epi=54, categoria="ANTIGRIPALES",
                               unidades=1),
    ]
    r = stub.CargarReportesFarmacia(iter(filas), metadata=_actor(db, "admin@test.co"))
    assert (r.filas_recibidas, r.filas_rechazadas) == (6, 3)
    assert (r.semanas_creadas, r.semanas_actualizadas, r.semanas_rechazadas) == (2, 0, 0)
    assert {e.fila for e in r.errores} == {5, 6, 7}
    unidades = {(x.semana_epi, x.categoria): x.unidades
                for x in db.query(ReporteFarmacia).filter_by(farmacia_id=farmacia_grpc, anio=2024)}
    assert unidades == {(10, "ANTIGRIPALES"): 120, (10, "TAPABOCAS"): 40, (11, "ANTIGRIPALES"): 90}

    # Cargar otra vez la misma semana la reemplaza
    r = stub.CargarReportesFarmacia(iter(filas[:1]), metadata=_actor(db, "admin@test.co"))
    assert (r.semanas_creadas, r.semanas_actualizadas) == (0, 1)


def test_cargar_reportes_aplica_las_reglas_de_la_farmacia(stub, db, farmacia_grpc):
    # Una FARMACIA no puede cargar semanas viejas ni reportar por otra farmacia
    filas = [pb.FilaReporteFarmacia(fila=2, anio=2024, semana_epi=5, categoria="ANTIGRIPALES", unidades=3),
             pb.FilaReporteFarmacia(fila=3, farmacia_id=farmacia_grpc, anio=2024, semana_epi=6,
                                    categoria="ANTIGRIPALES", unidades=3)]
    r = stub.CargarReportesFarmacia(iter(filas), metadata=_actor(db, "farmacia@demo.co"))
    assert r.semanas_rechazadas == 2 and r.semanas_creadas == 0
    mensajes = " ".join(e.mensaje for e in r.errores)
    assert "8 semanas" in mensajes or "asignado" in mensajes

    with pytest.raises(grpc.RpcError) as exc:  # sin x-actor-id
        stub.CargarReportesFarmacia(iter(filas), metadata=META)
    assert exc.value.code() == grpc.StatusCode.PERMISSION_DENIED
