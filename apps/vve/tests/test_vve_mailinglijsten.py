import pytest
from fastapi.testclient import TestClient
from apps.vve.main import app
from apps.vve.config import settings
from apps.vve.database import get_vve_db
from apps.vve.models import VveContactCreate, VveMailinglijstCreate
from apps.vve import auth


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_vve_ml.db")
    monkeypatch.setattr(settings, "sqlite_db_path", test_db_path)
    monkeypatch.setattr(settings, "use_firestore", False)
    monkeypatch.setattr(settings, "firestore_project_id", "")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        auth,
        "get_current_user",
        lambda req: {"email": "huismeester@denheuvelvelp.nl", "name": "VvE Huismeester"}
    )
    return TestClient(app)


def test_vve_mailinglijsten_overview_empty(client):
    response = client.get("/mailinglijsten")
    assert response.status_code == 200
    assert "Mailinglijsten Beheer" in response.text
    assert "Er zijn nog geen VvE mailinglijsten aangemaakt" in response.text


def test_vve_create_and_manage_mailinglijst(client):
    db = get_vve_db()
    # Maak 3 verschillende contacten aan: woning, bedrijf, garagebox (>=501)
    woning = db.create(VveContactCreate(
        index_nummer="101",
        adres_appartementsrecht="Den Heuvel 101",
        naam="Karel de Grote",
        email="karel@example.com",
        type_lid="Woningeigenaar"
    ))
    bedrijf = db.create(VveContactCreate(
        index_nummer="B-01",
        adres_appartementsrecht="Den Heuvel 1",
        naam="Bakkerij Jansen",
        email="info@bakkerijjansen.nl",
        type_lid="Bedrijf / Commercieel",
        bedrijfsnaam="Bakkerij Jansen B.V."
    ))
    garage = db.create(VveContactCreate(
        index_nummer="G-501",
        adres_appartementsrecht="Den Heuvel 501",
        naam="Dhr. Garagebox",
        email="garage501@example.com",
        type_lid="Garageboxhouder",
        garageboxnummers="501"
    ))

    # 1. Maak handmatig een specifieke mailinglijst voor Garages
    res_create = client.post(
        "/mailinglijsten/nieuw",
        data={
            "naam": "Garageboxhouders",
            "email_prefix": "garages",
            "omschrijving": "Mailinglijst uitsluitend voor houders van een garagebox"
        },
        follow_redirects=True
    )
    assert res_create.status_code == 200
    assert "Garageboxhouders" in res_create.text
    assert "garages@denheuvelvelp.nl" in res_create.text

    lijsten = db.list_mailinglijsten()
    assert len(lijsten) == 1
    ml = lijsten[0]
    assert ml.naam == "Garageboxhouders"
    assert ml.email_groep == "garages@denheuvelvelp.nl"

    # 2. Voeg handmatig alleen de garageboxhouder toe
    res_add = client.post(
        f"/mailinglijsten/{ml.id}/leden/toevoegen",
        data={"contact_ids": [garage.id]},
        follow_redirects=True
    )
    assert res_add.status_code == 200
    assert "1 lid/leden toegevoegd" in res_add.text

    updated_ml = db.get_mailinglijst(ml.id)
    assert len(updated_ml.leden) == 1
    assert garage.id in updated_ml.leden
    assert woning.id not in updated_ml.leden
    assert bedrijf.id not in updated_ml.leden

    # 3. Synchroniseer naar Google Workspace
    res_sync = client.post(
        f"/mailinglijsten/{ml.id}/sync-google",
        follow_redirects=True
    )
    assert res_sync.status_code == 200
    synced_ml = db.get_mailinglijst(ml.id)
    assert "Simulatie" in synced_ml.sync_status or "Gesynchroniseerd" in synced_ml.sync_status
    assert synced_ml.laatst_gesynchroniseerd != ""

    # 4. Verwijder lid
    res_rem = client.post(
        f"/mailinglijsten/{ml.id}/leden/verwijderen",
        data={"contact_id": garage.id},
        follow_redirects=True
    )
    assert res_rem.status_code == 200
    ml_after_rem = db.get_mailinglijst(ml.id)
    assert len(ml_after_rem.leden) == 0

    # 5. Verwijder mailinglijst
    res_del = client.post(
        f"/mailinglijsten/{ml.id}/verwijderen",
        follow_redirects=True
    )
    assert res_del.status_code == 200
    assert len(db.list_mailinglijsten()) == 0


def test_vve_mailinglijst_edge_cases(client):
    db = get_vve_db()
    c = db.create(VveContactCreate(
        index_nummer="201",
        adres_appartementsrecht="Den Heuvel 201",
        naam="Test Eigenaar",
        email="primair@example.com",
        email_2="tweede@example.com"
    ))

    ml = db.create_mailinglijst(VveMailinglijstCreate(
        naam="Bestuur & Commissies",
        email_groep="bestuur@denheuvelvelp.nl",
        omschrijving="Test"
    ))

    # Geen selectie doorgeven
    res_empty = client.post(
        f"/mailinglijsten/{ml.id}/leden/toevoegen",
        data={},
        follow_redirects=True
    )
    assert res_empty.status_code == 200
    assert "Geen leden geselecteerd" in res_empty.text

    # Toevoegen
    client.post(
        f"/mailinglijsten/{ml.id}/leden/toevoegen",
        data={"contact_ids": [c.id]},
        follow_redirects=True
    )

    # Nogmaals toevoegen mag niet dupliceren
    client.post(
        f"/mailinglijsten/{ml.id}/leden/toevoegen",
        data={"contact_ids": [c.id]},
        follow_redirects=True
    )
    ml_check = db.get_mailinglijst(ml.id)
    assert len(ml_check.leden) == 1

    # Niet-bestaande lijst geeft 404
    res_404 = client.get("/mailinglijsten/onbekend-id/leden")
    assert res_404.status_code == 404

