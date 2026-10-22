import pytest
from fastapi.testclient import TestClient
from apps.cooperatie.main import app
from apps.cooperatie.config import settings
from apps.cooperatie.database import get_db
from apps.cooperatie.models import ContactCreate
from apps.cooperatie import auth


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_cooperatie_ml.db")
    monkeypatch.setattr(settings, "sqlite_db_path", test_db_path)
    monkeypatch.setattr(settings, "use_firestore", False)
    monkeypatch.setattr(settings, "firestore_project_id", "")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        auth,
        "get_current_user",
        lambda req: {"email": "huismeester@denheuvelvelp.nl", "name": "Huismeester"}
    )
    return TestClient(app)


def test_mailinglijsten_overview_empty(client):
    response = client.get("/mailinglijsten")
    assert response.status_code == 200
    assert "Mailinglijsten Beheer" in response.text
    assert "Er zijn nog geen mailinglijsten aangemaakt" in response.text


def test_create_and_manage_mailinglijst(client):
    db = get_db()
    # Maak 2 testcontacten aan
    c1 = db.create(ContactCreate(
        index_nummer="101",
        adres_appartementsrecht="Den Heuvel 101",
        naam="Jan Jansen",
        email="jan@example.com"
    ))
    c2 = db.create(ContactCreate(
        index_nummer="102",
        adres_appartementsrecht="Den Heuvel 102",
        naam="Piet Pietersen",
        email="piet@example.com"
    ))

    # 1. Maak nieuwe mailinglijst aan via POST
    res_create = client.post(
        "/mailinglijsten/nieuw",
        data={
            "naam": "Bewoners Algemeen",
            "email_prefix": "bewoners",
            "omschrijving": "Algemene mailinglijst voor alle bewoners"
        },
        follow_redirects=True
    )
    assert res_create.status_code == 200
    assert "Bewoners Algemeen" in res_create.text
    assert "bewoners@denheuvelvelp.nl" in res_create.text

    # Controleer database
    lijsten = db.list_mailinglijsten()
    assert len(lijsten) == 1
    ml = lijsten[0]
    assert ml.naam == "Bewoners Algemeen"
    assert ml.email_groep == "bewoners@denheuvelvelp.nl"
    assert len(ml.leden) == 0

    # 2. Voeg contacten toe aan lijst
    res_add = client.post(
        f"/mailinglijsten/{ml.id}/leden/toevoegen",
        data={"contact_ids": [c1.id, c2.id]},
        follow_redirects=True
    )
    assert res_add.status_code == 200
    assert "2 bewoner(s) toegevoegd" in res_add.text

    updated_ml = db.get_mailinglijst(ml.id)
    assert len(updated_ml.leden) == 2
    assert c1.id in updated_ml.leden
    assert c2.id in updated_ml.leden

    # 3. Synchroniseer naar Google Workspace (simulatiemodus)
    res_sync = client.post(
        f"/mailinglijsten/{ml.id}/sync-google",
        follow_redirects=True
    )
    assert res_sync.status_code == 200
    synced_ml = db.get_mailinglijst(ml.id)
    assert "Simulatie" in synced_ml.sync_status or "Gesynchroniseerd" in synced_ml.sync_status
    assert synced_ml.laatst_gesynchroniseerd != ""

    # 4. Verwijder één lid
    res_rem = client.post(
        f"/mailinglijsten/{ml.id}/leden/verwijderen",
        data={"contact_id": c1.id},
        follow_redirects=True
    )
    assert res_rem.status_code == 200
    ml_after_rem = db.get_mailinglijst(ml.id)
    assert len(ml_after_rem.leden) == 1
    assert c1.id not in ml_after_rem.leden
    assert c2.id in ml_after_rem.leden

    # 5. Verwijder de gehele mailinglijst
    res_del = client.post(
        f"/mailinglijsten/{ml.id}/verwijderen",
        follow_redirects=True
    )
    assert res_del.status_code == 200
    assert "Mailinglijst verwijderd" in res_del.text
    assert len(db.list_mailinglijsten()) == 0
