"""Alertas tempranas: generación, idempotencia, cierre, correo y permisos."""
import json

import httpx
import pytest

from app.core.config import settings
from app.core.epi import iterar_semanas
from app.models import Alerta, CasoOficial, Enfermedad, Municipio
from app.notificaciones.correo import NotificadorCorreo, ResendNotificador
from app.services.alerta_service import AlertaService

SEMANAS = list(iterar_semanas((2021, 1), (2026, 20)))


class CorreoFalso(NotificadorCorreo):
    def __init__(self):
        self.enviados = []

    def enviar(self, destinatarios, asunto, html_cuerpo):
        self.enviados.append((destinatarios, asunto, html_cuerpo))
        return True


@pytest.fixture(scope="module")
def brote_dengue():
    """Dengue en Consacá: 2 casos por semana y un salto a 30 en la última semana."""
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        dengue = db.query(Enfermedad).filter_by(codigo="DENGUE").one()
        consaca = db.query(Municipio).filter_by(codigo_divipola="52207").one()
        for a, s in SEMANAS:
            db.merge(CasoOficial(municipio_id=consaca.id, enfermedad_id=dengue.id, anio=a, semana_epi=s,
                                 casos=30 if (a, s) == SEMANAS[-1] else 2, es_simulado=True))
        db.commit()
        return consaca.id, dengue.id


def _mias(db, brote):
    mid, eid = brote
    return db.query(Alerta).filter_by(municipio_id=mid, enfermedad_id=eid, origen="OBSERVADO").all()


def test_alerta_observada_se_crea_una_vez_y_se_notifica(db, brote_dengue, monkeypatch):
    monkeypatch.setattr(settings, "ALERTAS_EMAIL_DESTINO", "salud@test.co")
    correo = CorreoFalso()
    r = AlertaService(db, notificador=correo).evaluar()
    alertas = _mias(db, brote_dengue)
    assert len(alertas) == 1 and alertas[0].activa and alertas[0].nivel_riesgo == "ROJO"
    assert "30 casos" in alertas[0].mensaje and alertas[0].notificada_email
    assert r.nuevas >= 1 and len(correo.enviados) == 1
    assert correo.enviados[0][0] == ["salud@test.co"] and "Consacá" in correo.enviados[0][2]

    # Evaluar otra vez no duplica ni reenvía
    AlertaService(db, notificador=correo).evaluar()
    assert len(_mias(db, brote_dengue)) == 1 and len(correo.enviados) == 1


def test_alerta_cerrada_por_admin_no_se_reabre(client, admin_headers, db, brote_dengue):
    a = _mias(db, brote_dengue)[0]
    r = client.patch(f"/api/v1/alertas/{a.id}/cerrar", headers=admin_headers)
    assert r.status_code == 200 and r.json()["activa"] is False
    AlertaService(db, notificador=CorreoFalso()).evaluar()
    db.expire_all()
    alertas = _mias(db, brote_dengue)
    assert len(alertas) == 1 and not alertas[0].activa


def test_alerta_se_cierra_sola_si_el_riesgo_baja(db, brote_dengue):
    mid, eid = brote_dengue
    a = _mias(db, brote_dengue)[0]
    a.activa, a.cerrada_en = True, None
    a.nivel_riesgo = "NARANJA"
    db.commit()
    caso = db.query(CasoOficial).filter_by(municipio_id=mid, enfermedad_id=eid, anio=2026, semana_epi=20).one()
    caso.casos = 2
    db.commit()
    try:
        r = AlertaService(db, notificador=CorreoFalso()).evaluar()
        db.expire_all()
        assert r.cerradas >= 1 and not _mias(db, brote_dengue)[0].activa
    finally:
        caso.casos = 30
        db.commit()


def test_endpoints_y_permisos(client, admin_headers, ciudadano_headers):
    assert client.get("/api/v1/alertas/activas").status_code == 200  # público (banner)
    assert client.get("/api/v1/alertas", headers=ciudadano_headers).status_code == 403
    r = client.get("/api/v1/alertas", headers=admin_headers, params={"activa": False})
    assert r.status_code == 200 and r.json()["total"] >= 1
    assert client.post("/api/v1/alertas/evaluar", headers=admin_headers,
                       params={"enviar_correo": False}).status_code == 200
    assert client.patch("/api/v1/alertas/999999/cerrar", headers=admin_headers).status_code == 404


def test_adaptador_resend():
    peticiones = []

    def responder(req: httpx.Request):
        peticiones.append(req)
        return httpx.Response(200, json={"id": "abc"}) if len(peticiones) == 1 else httpx.Response(422)

    n = ResendNotificador("re_test", "Predictor <a@b.co>", url="https://api.resend.test/emails",
                          cliente=httpx.Client(transport=httpx.MockTransport(responder)))
    assert n.enviar(["x@y.co"], "Asunto", "<p>hola</p>") is True
    cuerpo = json.loads(peticiones[0].content)
    assert peticiones[0].headers["Authorization"] == "Bearer re_test"
    assert cuerpo == {"from": "Predictor <a@b.co>", "to": ["x@y.co"], "subject": "Asunto", "html": "<p>hola</p>"}
    assert n.enviar(["x@y.co"], "Asunto", "<p>hola</p>") is False  # error del proveedor: no rompe nada
    assert n.enviar([], "Asunto", "x") is False


def test_ciudadanos_reciben_solo_las_alertas_de_su_municipio(db, brote_dengue, monkeypatch):
    from app.core.security import hash_password
    from app.models import Rol, Usuario

    mid, eid = brote_dengue
    rol = db.query(Rol).filter_by(nombre="CIUDADANO").one()
    db.add(Usuario(nombre="Vecina de Consacá", email="vecina@consaca.co", password_hash=hash_password("Clave1234"),
                   rol_id=rol.id, municipio_id=mid))
    db.commit()
    monkeypatch.setattr(settings, "ALERTAS_EMAIL_DESTINO", "")
    monkeypatch.setattr(settings, "ALERTAS_A_CIUDADANOS", True)
    a = _mias(db, brote_dengue)[0]
    a.activa, a.cerrada_en, a.notificada_email, a.nivel_riesgo = True, None, False, "ROJO"
    db.commit()
    correo = CorreoFalso()
    AlertaService(db, notificador=correo).notificar()
    para_vecina = [e for e in correo.enviados if e[0] == ["vecina@consaca.co"]]
    assert len(para_vecina) == 1 and "Consacá" in para_vecina[0][2]
    assert all("Pasto" not in e[2] or e[0] != ["vecina@consaca.co"] for e in correo.enviados)
    db.refresh(a)
    assert a.notificada_email
