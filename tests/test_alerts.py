"""Early alerts: creation, idempotence, closing, e-mail and permissions."""
import json

import httpx
import pytest

from volcano.models import Alert, Disease, Municipality, OfficialCase
from volcano.notifications.email import EmailNotifier, ResendNotifier
from volcano.services.alerts import AlertService
from volcano.shared.config import settings
from volcano.shared.epi import iter_weeks

WEEKS = list(iter_weeks((2021, 1), (2026, 20)))


class FakeEmail(EmailNotifier):
    def __init__(self):
        self.sent = []

    def send(self, recipients, subject, html_body):
        self.sent.append((recipients, subject, html_body))
        return True


@pytest.fixture(scope="module")
def dengue_outbreak():
    """Dengue in Consacá: 2 cases a week and a jump to 30 in the last week."""
    from volcano.db.session import SessionLocal

    with SessionLocal() as db:
        dengue = db.query(Disease).filter_by(code="DENGUE").one()
        consaca = db.query(Municipality).filter_by(divipola_code="52207").one()
        for y, w in WEEKS:
            db.merge(OfficialCase(municipality_id=consaca.id, disease_id=dengue.id, year=y, epi_week=w,
                                  cases=30 if (y, w) == WEEKS[-1] else 2, is_simulated=True))
        db.commit()
        return consaca.id, dengue.id


def _mine(db, outbreak):
    mid, did = outbreak
    return db.query(Alert).filter_by(municipality_id=mid, disease_id=did, origin="OBSERVED").all()


def test_observed_alert_is_created_once_and_notified(db, dengue_outbreak, monkeypatch):
    monkeypatch.setattr(settings, "ALERT_EMAIL_RECIPIENTS", "salud@test.co")
    email = FakeEmail()
    r = AlertService(db, notifier=email).evaluate()
    alerts = _mine(db, dengue_outbreak)
    assert len(alerts) == 1 and alerts[0].active and alerts[0].risk_level == "RED"
    assert "30 casos" in alerts[0].message and alerts[0].email_notified
    assert r.new >= 1 and len(email.sent) == 1
    assert email.sent[0][0] == ["salud@test.co"] and "Consacá" in email.sent[0][2]

    # Evaluating again neither duplicates nor resends
    AlertService(db, notifier=email).evaluate()
    assert len(_mine(db, dengue_outbreak)) == 1 and len(email.sent) == 1


def test_alert_closed_by_admin_does_not_reopen(client, admin_headers, db, dengue_outbreak):
    a = _mine(db, dengue_outbreak)[0]
    r = client.patch(f"/api/v1/alerts/{a.id}/close", headers=admin_headers)
    assert r.status_code == 200 and r.json()["active"] is False
    AlertService(db, notifier=FakeEmail()).evaluate()
    db.expire_all()
    alerts = _mine(db, dengue_outbreak)
    assert len(alerts) == 1 and not alerts[0].active


def test_alert_closes_by_itself_when_the_risk_drops(db, dengue_outbreak):
    mid, did = dengue_outbreak
    a = _mine(db, dengue_outbreak)[0]
    a.active, a.closed_at, a.risk_level = True, None, "ORANGE"
    db.commit()
    case = db.query(OfficialCase).filter_by(municipality_id=mid, disease_id=did, year=2026, epi_week=20).one()
    case.cases = 2
    db.commit()
    try:
        r = AlertService(db, notifier=FakeEmail()).evaluate()
        db.expire_all()
        assert r.closed >= 1 and not _mine(db, dengue_outbreak)[0].active
    finally:
        case.cases = 30
        db.commit()


def test_endpoints_and_permissions(client, admin_headers, citizen_headers):
    assert client.get("/api/v1/alerts/active").status_code == 200  # public (banner)
    assert client.get("/api/v1/alerts", headers=citizen_headers).status_code == 403
    r = client.get("/api/v1/alerts", headers=admin_headers, params={"active": False})
    assert r.status_code == 200 and r.json()["total"] >= 1
    r = client.post("/api/v1/alerts/evaluate", headers=admin_headers, params={"send_email": False})
    assert r.status_code == 200
    assert client.patch("/api/v1/alerts/999999/close", headers=admin_headers).status_code == 404


def test_resend_adapter():
    requests = []

    def respond(req: httpx.Request):
        requests.append(req)
        return httpx.Response(200, json={"id": "abc"}) if len(requests) == 1 else httpx.Response(422)

    n = ResendNotifier("re_test", "Predictor <a@b.co>", url="https://api.resend.test/emails",
                       client=httpx.Client(transport=httpx.MockTransport(respond)))
    assert n.send(["x@y.co"], "Asunto", "<p>hola</p>") is True
    body = json.loads(requests[0].content)
    assert requests[0].headers["Authorization"] == "Bearer re_test"
    assert body == {"from": "Predictor <a@b.co>", "to": ["x@y.co"], "subject": "Asunto", "html": "<p>hola</p>"}
    assert n.send(["x@y.co"], "Asunto", "<p>hola</p>") is False  # provider error: nothing breaks
    assert n.send([], "Asunto", "x") is False


def test_citizens_only_get_their_municipality_alerts(db, dengue_outbreak, monkeypatch):
    from volcano.models import Role, User
    from volcano.shared.security import hash_password

    mid, _ = dengue_outbreak
    role = db.query(Role).filter_by(name="CITIZEN").one()
    db.add(User(name="Vecina de Consacá", email="vecina@consaca.co", password_hash=hash_password("Clave1234"),
                role_id=role.id, municipality_id=mid))
    db.commit()
    monkeypatch.setattr(settings, "ALERT_EMAIL_RECIPIENTS", "")
    monkeypatch.setattr(settings, "ALERTS_TO_CITIZENS", True)
    a = _mine(db, dengue_outbreak)[0]
    a.active, a.closed_at, a.email_notified, a.risk_level = True, None, False, "RED"
    db.commit()
    email = FakeEmail()
    AlertService(db, notifier=email).notify()
    to_neighbour = [e for e in email.sent if e[0] == ["vecina@consaca.co"]]
    assert len(to_neighbour) == 1 and "Consacá" in to_neighbour[0][2]
    assert all("Pasto" not in e[2] or e[0] != ["vecina@consaca.co"] for e in email.sent)
    db.refresh(a)
    assert a.email_notified


def test_public_alert_search_with_filters(client, db):
    consaca = db.query(Municipality).filter_by(divipola_code="52207").one()
    dengue = db.query(Disease).filter_by(code="DENGUE").one()
    for week, level, active in ((40, "RED", True), (41, "ORANGE", False)):
        db.add(Alert(municipality_id=consaca.id, disease_id=dengue.id, year=2019, epi_week=week, risk_level=level,
                     origin="OBSERVED", message=f"Búsqueda zancudo S{week}", active=active))
    db.commit()
    try:
        url = "/api/v1/alerts/search"
        r = client.get(url, params={"q": "zancudo"})  # no token: it is public
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 2 and r.json()["items"][0]["epi_week"] == 41  # newest first
        assert client.get(url, params={"q": "zancudo", "level": "RED"}).json()["total"] == 1
        assert client.get(url, params={"q": "zancudo", "active": False}).json()["items"][0]["risk_level"] == "ORANGE"
        assert client.get(url, params={"q": "consac", "municipality_id": consaca.id}).json()["total"] >= 2
        assert client.get(url, params={"level": "BLUE"}).status_code == 422
    finally:
        db.query(Alert).filter(Alert.year == 2019, Alert.message.like("Búsqueda zancudo%")).delete()
        db.commit()
