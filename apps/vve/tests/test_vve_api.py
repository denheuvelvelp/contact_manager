import pytest
from fastapi.testclient import TestClient
from apps.vve.main import app
from apps.vve.config import settings
from apps.vve import auth


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_api_vve.db")
    monkeypatch.setattr(settings, "sqlite_db_path", test_db_path)
    monkeypatch.setattr(settings, "use_firestore", False)
    monkeypatch.setattr(settings, "firestore_project_id", "")


@pytest.fixture
def client(monkeypatch):
    # Simuleer een geverifieerde @denheuvelvelp.nl gebruiker voor testcases
    monkeypatch.setattr(
        auth,
        "get_current_user",
        lambda req: {"email": "huismeester@denheuvelvelp.nl", "name": "Huismeester"}
    )
    return TestClient(app)


def test_vve_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_vve_dashboard_page(client):
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "DEN HEUVEL" in res.text
    assert "Parkeerterrein &amp; Garageboxen" in res.text
    assert "Bezoekersregistratie" in res.text



def test_vve_auth_redirect_when_not_logged_in():
    unauthed = TestClient(app)
    res = unauthed.get("/contacten", follow_redirects=False)
    assert res.status_code == 303
    assert "/login" in res.headers["location"]


def test_vve_empty_list(client):
    res = client.get("/contacten")
    assert res.status_code == 200
    assert "Geen VvE-leden gevonden" in res.text


def test_create_and_filter_vve_contact(client):
    payload = {
        "index_nummer": "B-10",
        "bestemming": "Bedrijfsruimte",
        "adres_appartementsrecht": "Molenwerf 10",
        "naam": "Bakkerij BV",
        "bedrijfsnaam": "Bakkerij BV",
        "contactpersoon_zakelijk": "Dhr. Bakker",
        "type_lid": "Bedrijf / Commercieel",
        "breukdeel": "25/1000",
        "garageboxnummers": "G-01, G-02",
        "telefoonnummer": "020-1234567",
        "email": "info@bakkerij.nl",
        "is_externe_eigenaar": 1,
        "correspondentieadres_extern": "Dorpsplein 1, 1000 AA Amsterdam"
    }
    res = client.post("/contacten/nieuw", data=payload, follow_redirects=True)
    assert res.status_code == 200
    assert "Bakkerij BV" in res.text
    assert "25/1000" in res.text

    list_res = client.get("/contacten")
    assert "Bakkerij BV" in list_res.text
    assert "G-01, G-02" in list_res.text
    assert "Bedrijf" in list_res.text
    assert "Elders wonend" in list_res.text

    filter_res = client.get("/contacten?type=Bedrijf%20%2F%20Commercieel")
    assert "Bakkerij BV" in filter_res.text

    woning_res = client.get("/contacten?type=Woningeigenaar")
    assert "Bakkerij BV" not in woning_res.text


def test_vve_reset_endpoint(client):
    payload = {
        "index_nummer": "G-99",
        "bestemming": "Garage",
        "adres_appartementsrecht": "Molenwerf G-99",
        "naam": "Garage Eigenaar"
    }
    client.post("/contacten/nieuw", data=payload)
    assert "Garage Eigenaar" in client.get("/contacten").text

    res = client.post("/contacten/reset", follow_redirects=True)
    assert res.status_code == 200
    assert "VvE-database succesvol gereset" in res.text
    assert "Garage Eigenaar" not in res.text
