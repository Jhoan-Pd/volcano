"""Pharmacy module: weekly report rules, role permissions and sales index."""
import pytest

from volcano.models import Municipality, Pharmacy, User
from volcano.shared.epi import last_complete_week, shift
from volcano.sources.pharmacy import compute_index

URL = "/api/v1/pharmacy"


@pytest.fixture(scope="module")
def demo_pharmacy():
    from volcano.db.session import SessionLocal

    with SessionLocal() as db:
        user = db.query(User).filter_by(email="farmacia@demo.co").one()
        p = db.query(Pharmacy).filter_by(user_id=user.id).first()
        if p is None:
            pasto = db.query(Municipality).filter_by(divipola_code="52001").one()
            p = Pharmacy(name="Droguería Test", tax_id="900000001-1", municipality_id=pasto.id, user_id=user.id)
            db.add(p)
            db.commit()
        return p.id


def _body(year, week, **extra):
    return {"year": year, "epi_week": week, **extra,
            "items": [{"category": "COLD_FLU", "units": 120}, {"category": "FACE_MASKS", "units": 40}]}


def test_my_pharmacy_lists_reportable_weeks(client, pharmacy_headers, demo_pharmacy):
    r = client.get(f"{URL}/me", headers=pharmacy_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id"] == demo_pharmacy and len(data["reportable_weeks"]) == 8
    first = data["reportable_weeks"][0]
    assert (first["year"], first["epi_week"]) == last_complete_week()


def test_create_edit_and_delete_a_report(client, pharmacy_headers, demo_pharmacy):
    y, w = last_complete_week()
    r = client.post(f"{URL}/reports", json=_body(y, w), headers=pharmacy_headers)
    assert r.status_code == 201, r.text
    assert r.json()["total_units"] == 160 and r.json()["reported_by"] == "Farmacia Demo Centro"

    # The same week cannot be created twice
    assert client.post(f"{URL}/reports", json=_body(y, w), headers=pharmacy_headers).status_code == 409

    r = client.put(f"{URL}/reports/{y}/{w}", headers=pharmacy_headers,
                   json={"items": [{"category": "COLD_FLU", "units": 150}]})
    assert r.status_code == 200 and r.json()["total_units"] == 150

    history = client.get(f"{URL}/reports", headers=pharmacy_headers).json()
    assert history[0]["epi_week"] == w and history[0]["editable"] is True

    assert client.delete(f"{URL}/reports/{y}/{w}", headers=pharmacy_headers).status_code == 204
    assert client.get(f"{URL}/reports/{y}/{w}", headers=pharmacy_headers).status_code == 404


def test_legacy_spanish_category_is_still_accepted(client, pharmacy_headers, demo_pharmacy):
    y, w = shift(*last_complete_week(), -1)
    body = {"year": y, "epi_week": w, "items": [{"category": "ANTIGRIPALES", "units": 7}]}
    r = client.post(f"{URL}/reports", json=body, headers=pharmacy_headers)
    assert r.status_code == 201, r.text
    assert r.json()["items"] == [{"category": "COLD_FLU", "units": 7}]
    client.delete(f"{URL}/reports/{y}/{w}", headers=pharmacy_headers)


def test_form_validation(client, pharmacy_headers, demo_pharmacy):
    y, w = last_complete_week()
    repeated = {"year": y, "epi_week": w, "items": [{"category": "FACE_MASKS", "units": 1}] * 2}
    assert client.post(f"{URL}/reports", json=repeated, headers=pharmacy_headers).status_code == 422
    negative = {"year": y, "epi_week": w, "items": [{"category": "FACE_MASKS", "units": -5}]}
    assert client.post(f"{URL}/reports", json=negative, headers=pharmacy_headers).status_code == 422
    no_week_53 = {"year": 2025, "epi_week": 53, "items": [{"category": "FACE_MASKS", "units": 1}]}
    assert client.post(f"{URL}/reports", json=no_week_53, headers=pharmacy_headers).status_code == 422


def test_future_or_too_old_weeks_are_rejected(client, pharmacy_headers, demo_pharmacy):
    future = shift(*last_complete_week(), 2)
    r = client.post(f"{URL}/reports", json=_body(*future), headers=pharmacy_headers)
    assert r.status_code == 422 and "terminadas" in r.json()["error"]["message"]
    old = shift(*last_complete_week(), -20)
    r = client.post(f"{URL}/reports", json=_body(*old), headers=pharmacy_headers)
    assert r.status_code == 422 and "últimas 8 semanas" in r.json()["error"]["message"]


def test_admin_reports_old_weeks_naming_the_pharmacy(client, admin_headers, demo_pharmacy):
    old = shift(*last_complete_week(), -20)
    # Missing pharmacy_id: the ADMIN must say which pharmacy
    assert client.post(f"{URL}/reports", json=_body(*old), headers=admin_headers).status_code == 422
    r = client.post(f"{URL}/reports", json=_body(*old, pharmacy_id=demo_pharmacy), headers=admin_headers)
    assert r.status_code == 201, r.text


def test_citizen_has_no_access(client, citizen_headers):
    assert client.get(f"{URL}/me", headers=citizen_headers).status_code == 403
    assert client.get(f"{URL}/me").status_code == 401


def test_index_compares_with_the_previous_weeks():
    rows = []
    for week in range(1, 11):
        units = 100 if week < 10 else 150  # +50 % in week 10
        rows += [{"municipality_id": 1, "pharmacy_id": p, "year": 2025, "epi_week": week,
                  "category": "COLD_FLU", "units": units} for p in (1, 2)]
    # In week 10 only one pharmacy reports: the index is computed per reporting pharmacy
    rows = [r for r in rows if not (r["epi_week"] == 10 and r["pharmacy_id"] == 2)]
    index = {r["epi_week"]: r for r in compute_index(rows)}
    assert index[10]["reporting_pharmacies"] == 1 and index[10]["sales_index"] == pytest.approx(150.0)
    assert index[2]["sales_index"] is None  # not enough history (min. 4 weeks)
    assert index[6]["sales_index"] == pytest.approx(100.0)
