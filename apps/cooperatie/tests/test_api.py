import pytest
from fastapi.testclient import TestClient
from apps.cooperatie.main import app
from apps.cooperatie.config import settings
from apps.cooperatie import auth


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_api_contacts.db")
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


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_page(client):
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "DEN HEUVEL" in response.text
    assert "Parkeerterrein &amp; Vakken" in response.text
    assert "Bezoekersregistratie" in response.text



def test_auth_redirect_when_not_logged_in():
    # Nieuwe ongeauthenticeerde client zonder sessie
    unauthed = TestClient(app)
    res = unauthed.get("/contacten", follow_redirects=False)
    assert res.status_code == 303
    assert "/login" in res.headers["location"]


def test_contacten_page_empty(client):
    response = client.get("/contacten")
    assert response.status_code == 200
    assert "Geen contacten in het systeem" in response.text


def test_create_and_view_contact(client):
    payload = {
        "index_nummer": "301",
        "bestemming": "Woning",
        "adres_appartementsrecht": "Molenwerf 30-A",
        "naam": "Test Bewoner",
        "postadres": "Molenwerf 30-A",
        "telefoonnummer": "06-11223344",
        "telefoonnummer_2": "06-99887766",
        "telefoonnummer_3": "06-55443322",
        "email": "test@bewoner.nl",
        "email_2": "werk@bewoner.nl",
        "email_3": "extra@bewoner.nl",
        "noodcontact_1_naam": "Contact Persoon 1",
        "noodcontact_1_telefoon": "06-12121212",
        "noodcontact_1_email": "nood1@bewoner.nl",
        "noodcontact_2_naam": "Contact Persoon 2",
        "noodcontact_2_telefoon": "06-34343434",
        "noodcontact_2_email": "nood2@bewoner.nl",
        "etage": "3",
        "minder_mobiel": 1,
        "huisdieren": "1 hond",
        "intercom_naam": "Bewoner",
        "notities": "Test notitie"
    }
    response = client.post("/contacten/nieuw", data=payload, follow_redirects=True)
    assert response.status_code == 200
    assert "Test Bewoner" in response.text
    assert "301" in response.text

    list_res = client.get("/contacten")
    assert "Test Bewoner" in list_res.text
    assert "Molenwerf 30-A" in list_res.text
    assert "Contact Persoon 1" in list_res.text


def test_csv_upload_flow(client):
    header = (
        b"Index nummer,Bestemming,Adres appartementsrecht,Naam,Postadres,"
        b"Telefoonnummer,Telefoonnummer 2,Telefoonnummer 3,Email,Email 2,Email 3\n"
    )
    row = b"401,Woning,Molenwerf 40,Upload Bewoner,Molenwerf 40,0699999999,0688888888,,upload@test.nl,,\n"
    csv_bytes = header + row

    response = client.post(
        "/importeren",
        files={"file": ("test.csv", csv_bytes, "text/csv")}
    )
    assert response.status_code == 200
    assert "Nieuw Toegevoegd" in response.text
    assert "Upload Bewoner" in response.text


def test_reset_endpoint(client):
    payload = {
        "index_nummer": "501",
        "bestemming": "Woning",
        "adres_appartementsrecht": "Molenwerf 50",
        "naam": "Te Wissen Bewoner",
        "telefoonnummer": "0612345678",
        "email": "wissen@test.nl"
    }
    client.post("/contacten/nieuw", data=payload)
    assert "Te Wissen Bewoner" in client.get("/contacten").text

    res = client.post("/contacten/reset", follow_redirects=True)
    assert res.status_code == 200
    assert "Database succesvol gereset" in res.text
    assert "Te Wissen Bewoner" not in res.text
