import pytest
from apps.vve.database import VveSQLiteStore
from apps.vve.importer import import_vve_csv

CSV_HEADER = (
    "Index nummer,Bestemming,Adres appartementsrecht,Naam,Postadres,Telefoonnummer,"
    "Telefoonnummer 2,Telefoonnummer 3,Email,Email 2,Email 3\n"
)


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_vve.db"
    return VveSQLiteStore(str(db_file))


def test_vve_import_first_time(test_db):
    row1 = "A-01,Woning,Molenwerf 12-A,J. Jansen,Molenwerf 12-A Amsterdam,0612345678,,,jansen@test.nl,,\n"
    row2 = "B-01,Bedrijfsruimte,Molenwerf 10,Fysio BV,Molenwerf 10,0205558899,,,info@fysio.nl,,\n"
    row3 = "G-01,Garagebox,Molenwerf G-01,Dhr. Visser,Kerkstraat 5 Utrecht,0655555555,,,visser@test.nl,,\n"
    csv_content = CSV_HEADER + row1 + row2 + row3

    res = import_vve_csv(csv_content.encode("utf-8"), test_db)
    assert res["success"] is True
    assert res["added"] == 3
    assert res["skipped"] == 0

    contacts = test_db.list_all()
    assert len(contacts) == 3

    # Check woning
    woning = test_db.find_existing("A-01", "Molenwerf 12-A")
    assert woning.type_lid == "Woningeigenaar"
    assert woning.is_externe_eigenaar is False

    # Check bedrijf
    bedrijf = test_db.find_existing("B-01", "Molenwerf 10")
    assert bedrijf.type_lid == "Bedrijf / Commercieel"

    # Check garage en extern wonend
    garage = test_db.find_existing("G-01", "Molenwerf G-01")
    assert garage.type_lid == "Garageboxhouder"
    assert garage.is_externe_eigenaar is True  # Postadres is in Utrecht!
    assert "Utrecht" in garage.correspondentieadres_extern


def test_vve_deduplication_keeps_existing_untouched(test_db):
    csv1 = CSV_HEADER + "A-01,Woning,Molenwerf 12-A,Originele Eigenaar,Molenwerf 12-A,0611111111,,,,,\n"
    import_vve_csv(csv1.encode("utf-8"), test_db)

    # Voeg handmatig breukdeel en garageboxnummer toe
    orig = test_db.find_existing("A-01", "Molenwerf 12-A")
    test_db.update(orig.id, orig.model_copy(update={
        "breukdeel": "15/1000",
        "garageboxnummers": "G-05"
    }))

    # Import week 2 met dezelfde regel (gewijzigde naam) en 1 nieuwe garage
    csv2 = CSV_HEADER + (
        "A-01,Woning,Molenwerf 12-A,GEWIJZIGD?,Molenwerf 12-A,0000000,,,,,\n"
        "G-02,Garagebox,Molenwerf G-02,Nieuwe Eigenaar,Molenwerf G-02,0622222222,,,,,\n"
    )
    res2 = import_vve_csv(csv2.encode("utf-8"), test_db)
    assert res2["added"] == 1
    assert res2["skipped"] == 1

    # Verifieer dat A-01 NIET is gewijzigd en breukdeel/garage bewaard zijn gebleven
    check_orig = test_db.find_existing("A-01", "Molenwerf 12-A")
    assert check_orig.naam == "Originele Eigenaar"
    assert check_orig.breukdeel == "15/1000"
    assert check_orig.garageboxnummers == "G-05"


def test_garagebox_extraction_den_heuvel_501(test_db):
    """
    Test dat een adres zoals 'Den Heuvel 501' automatisch wordt herkend als
    garageboxhouder en dat '501' direct in het veld garageboxnummers wordt geplaatst.
    """
    csv = CSV_HEADER + "501,Garage,Den Heuvel 501,Mevr. Van Garagen,Den Heuvel 12,0612345678,,,,,\n"
    res = import_vve_csv(csv.encode("utf-8"), test_db)
    assert res["success"] is True
    assert res["added"] == 1

    garage = test_db.find_existing("501", "Den Heuvel 501")
    assert garage is not None
    assert garage.type_lid == "Garageboxhouder"
    assert garage.garageboxnummers == "501"


def test_vve_reset_all(test_db):
    csv = CSV_HEADER + "A-01,Woning,Molenwerf 12-A,Eigenaar,Molenwerf 12-A,0611111111,,,,,\n"
    import_vve_csv(csv.encode("utf-8"), test_db)
    assert len(test_db.list_all()) == 1

    count = test_db.reset_all()
    assert count == 1
    assert len(test_db.list_all()) == 0

