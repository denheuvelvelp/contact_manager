import pytest
from apps.cooperatie.database import SQLiteStore
from apps.cooperatie.importer import import_cooperatie_csv

CSV_HEADER = "Index nummer,Bestemming,Adres appartementsrecht,Naam,Postadres,Telefoonnummer," \
             "Telefoonnummer 2,Telefoonnummer 3,Email,Email 2,Email 3\n"


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_coop.db"
    return SQLiteStore(str(db_file))


def test_import_first_time(test_db):
    csv_content = CSV_HEADER + (
        "101,Woning,Molenwerf 12-A,J. Jansen,Molenwerf 12-A Amsterdam,0612345678,0698765432,,jansen@test.nl,nood1@test.nl,\n"
        "102,Woning,Molenwerf 12-B,M. de Vries,Molenwerf 12-B Amsterdam,0623456789,,,devries@test.nl,,\n"
    )
    result = import_cooperatie_csv(csv_content.encode("utf-8"), test_db)
    assert result["success"] is True
    assert result["added"] == 2
    assert result["skipped"] == 0
    assert result["errors"] == 0

    contacts = test_db.list_all()
    assert len(contacts) == 2
    assert contacts[0].index_nummer == "101"
    assert contacts[0].naam == "J. Jansen"
    assert contacts[0].telefoonnummer_2 == "0698765432"
    assert contacts[0].email_2 == "nood1@test.nl"


def test_deduplication_keeps_existing_untouched(test_db):
    """
    CRUCIALE REGEL:
    Alle contacten die al bestaan moeten met rust gelaten worden.
    Alleen nieuwe contacten mogen worden toegevoegd.
    """
    csv_eerste_keer = CSV_HEADER + (
        "101,Woning,Molenwerf 12-A,J. Jansen,Molenwerf 12-A Amsterdam,0612345678,,,jansen@test.nl,,\n"
    )
    res1 = import_cooperatie_csv(csv_eerste_keer.encode("utf-8"), test_db)
    assert res1["added"] == 1

    # Handmatig een noodnummer toevoegen aan Jansen in de database
    existing_jansen = test_db.find_existing("101", "Molenwerf 12-A")
    test_db.update(existing_jansen.id, existing_jansen.model_copy(update={"noodcontactpersoon_1": "Oom Henk"}))

    # Tweede week import van Rebo: Jansen staat er weer in, plus een nieuwe bewoner (102 Bakker)
    csv_tweede_week = CSV_HEADER + (
        "101,Woning,Molenwerf 12-A,J. Jansen OVERSCHRIJVEN?,Molenwerf 12-A,00000000,,,gewijzigd@test.nl,,\n"
        "102,Woning,Molenwerf 12-B,K. Bakker,Molenwerf 12-B,0633333333,,,bakker@test.nl,,\n"
    )
    res2 = import_cooperatie_csv(csv_tweede_week.encode("utf-8"), test_db)
    assert res2["added"] == 1
    assert res2["skipped"] == 1  # Jansen moet zijn overgeslagen!

    # Verifieer dat Jansen NIET is overschreven en Oom Henk bewaard is gebleven
    jansen_after = test_db.find_existing("101", "Molenwerf 12-A")
    assert jansen_after.naam == "J. Jansen"  # Niet overschreven door "J. Jansen OVERSCHRIJVEN?"
    assert jansen_after.noodcontactpersoon_1 == "Oom Henk"  # Bewaard gebleven!

    # Verifieer dat Bakker wel is toegevoegd
    bakker = test_db.find_existing("102", "Molenwerf 12-B")
    assert bakker is not None
    assert bakker.naam == "K. Bakker"


def test_semicolon_excel_format(test_db):
    """Test Nederlandse Excel CSV export met puntkomma's (;)."""
    csv_semicolon = (
        "Index nummer;Bestemming;Adres appartementsrecht;Naam;Postadres;Telefoonnummer;Telefoonnummer 2;"
        "Telefoonnummer 3;Email;Email 2;Email 3\n"
        "201;Woning;Molenwerf 20;Mevr. A. Dijk;Molenwerf 20;0611111111;0622222222;0633333333;"
        "a.dijk@test.nl;nood1@test.nl;nood2@test.nl\n"
    )
    res = import_cooperatie_csv(csv_semicolon.encode("utf-8"), test_db)
    assert res["success"] is True
    assert res["added"] == 1
    assert res["delimiter"] == ";"
