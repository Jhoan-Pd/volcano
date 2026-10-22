"""Puente REST → gRPC: JSON (unary), SSE (server streaming), carga de filas (client streaming)
y WebSocket (bidireccional), con el servidor gRPC real de las pruebas."""
import json

import pytest

from app.main import app
from app.models import Municipio
from app.motor.cliente import ClienteMotor, cliente_motor
from app.services.entrenamiento import control
from tests.conftest import TOKEN_MOTOR

URL = "/api/v1/motor"


@pytest.fixture
def motor_api(motor_grpc):
    app.dependency_overrides[cliente_motor] = lambda: ClienteMotor(f"127.0.0.1:{motor_grpc.puerto}", TOKEN_MOTOR)
    yield
    app.dependency_overrides.pop(cliente_motor, None)


@pytest.fixture
def motor_apagado():
    app.dependency_overrides[cliente_motor] = lambda: ClienteMotor("127.0.0.1:1", TOKEN_MOTOR, timeout_s=2)
    yield
    app.dependency_overrides.pop(cliente_motor, None)


def _eventos_sse(lineas) -> list[tuple[str, dict]]:
    eventos, nombre = [], "message"
    for linea in lineas:
        if linea.startswith("event: "):
            nombre = linea.removeprefix("event: ")
        elif linea.startswith("data: "):
            eventos.append((nombre, json.loads(linea.removeprefix("data: "))))
            nombre = "message"
    return eventos


def test_estado_y_pronostico(client, db, motor_api, ira_entrenada):
    e = client.get(f"{URL}/estado").json()
    assert e["disponible"] and e["latencia_ms"] is not None

    pasto = db.query(Municipio).filter_by(codigo_divipola="52001").one().id
    r = client.get(f"{URL}/pronostico", params={"municipio_id": pasto, "enfermedad_id": ira_entrenada})
    assert r.status_code == 200, r.text
    datos = r.json()
    assert [p["horizonte"] for p in datos["puntos"]] == [1, 2, 3, 4]
    assert datos["puntos"][0]["nivel"] in ("VERDE", "AMARILLO", "NARANJA", "ROJO")

    r = client.get(f"{URL}/pronostico", params={"municipio_id": 9999, "enfermedad_id": ira_entrenada})
    assert r.status_code == 404 and r.json()["error"]["codigo"] == "NO_ENCONTRADO"


def test_motor_apagado_responde_503_sin_tumbar_la_api(client, motor_apagado):
    assert client.get(f"{URL}/estado").json()["disponible"] is False
    r = client.get(f"{URL}/pronostico", params={"municipio_id": 1, "enfermedad_id": 1})
    assert r.status_code == 503 and r.json()["error"]["codigo"] == "NO_DISPONIBLE"
    assert client.get("/health").status_code == 200


def test_entrenar_por_sse_solo_admin(client, motor_api, ira_entrenada, admin_headers, ciudadano_headers):
    assert client.post(f"{URL}/entrenar", headers=ciudadano_headers).status_code == 403
    control.reiniciar()
    with client.stream("POST", f"{URL}/entrenar", params={"enfermedad_id": ira_entrenada},
                       headers=admin_headers) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        eventos = _eventos_sse(r.iter_lines())
    assert {n for n, _ in eventos} == {"progreso"}
    assert eventos[0][1]["etapa"] == "INICIO" and eventos[-1][1]["etapa"] == "FIN"
    assert eventos[-1][1]["porcentaje"] == 100


def test_entrenar_en_curso_es_409_antes_de_abrir_el_stream(client, motor_api, admin_headers):
    control.iniciar()
    try:
        r = client.post(f"{URL}/entrenar", headers=admin_headers)
        assert r.status_code == 409 and r.json()["error"]["codigo"] == "CONFLICTO"
    finally:
        control.reiniciar()


def test_alertas_en_vivo_responde_sse(client, motor_apagado):
    # Con el motor apagado el stream se abre y avisa con un evento «error» (EventSource reintenta solo)
    with client.stream("GET", f"{URL}/alertas/eventos") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        eventos = _eventos_sse(r.iter_lines())
    assert eventos == [("error", {"mensaje": eventos[0][1]["mensaje"], "codigo": "NO_DISPONIBLE"})]


def test_carga_de_reportes_por_client_streaming(client, motor_api, farmacia_headers, ciudadano_headers):
    cuerpo = {"filas": [{"fila": 2, "anio": 2024, "semana_epi": 5, "categoria": "ANTIGRIPALES", "unidades": 10},
                        {"fila": 3, "anio": 2024, "semana_epi": 5, "categoria": "NADA", "unidades": 10}]}
    assert client.post(f"{URL}/farmacia/carga", json=cuerpo, headers=ciudadano_headers).status_code == 403
    r = client.post(f"{URL}/farmacia/carga", json=cuerpo, headers=farmacia_headers)
    assert r.status_code == 200, r.text
    resumen = r.json()
    assert resumen["filas_recibidas"] == 2 and resumen["filas_rechazadas"] == 1
    assert resumen["semanas_rechazadas"] == 1  # semana fuera de la ventana de 8 semanas de la farmacia
    assert client.post(f"{URL}/farmacia/carga", json={"filas": []}, headers=farmacia_headers).status_code == 422


def test_simulador_por_websocket(client, db, motor_api, ira_entrenada):
    pasto = db.query(Municipio).filter_by(codigo_divipola="52001").one().id
    with client.websocket_connect(f"{URL}/simulador") as ws:
        ws.send_json({"id": "a", "municipio_id": pasto, "enfermedad_id": ira_entrenada, "cambio_lluvia_pct": 80})
        r = ws.receive_json()
        assert r["id"] == "a" and r["error"] is None and len(r["escenario"]) == 4 and r["resumen"]

        ws.send_json({"id": "b", "municipio_id": "no-es-numero"})  # validación en la API
        assert ws.receive_json() == {"id": "b", "error": ws_error_esperado()}

        ws.send_json({"id": "c", "municipio_id": pasto, "enfermedad_id": ira_entrenada, "delta_temperatura_c": 99})
        assert "delta_temperatura_c" in ws.receive_json()["error"]  # validación en el motor


def ws_error_esperado() -> str:
    return "Input should be a valid integer, unable to parse string as an integer"
