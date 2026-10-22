import csv
import io
from typing import Dict, Any, List
from .models import VveContactCreate

EXPECTED_COLUMNS = [
    "Index nummer",
    "Bestemming",
    "Adres appartementsrecht",
    "Naam",
    "Postadres",
    "Telefoonnummer",
    "Telefoonnummer 2",
    "Telefoonnummer 3",
    "Email",
    "Email 2",
    "Email 3"
]


def detect_dialect_and_encoding(raw_bytes: bytes):
    encodings = ["utf-8-sig", "utf-8", "cp1252", "iso-8859-1"]
    text = None
    used_encoding = "utf-8"

    for enc in encodings:
        try:
            text = raw_bytes.decode(enc)
            used_encoding = enc
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        text = raw_bytes.decode("utf-8", errors="replace")

    first_line = text.splitlines()[0] if text.splitlines() else ""
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","

    return text, delimiter, used_encoding


def clean_cell(val: Any) -> str:
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none", "null"):
        return ""
    return s


def import_vve_csv(file_bytes: bytes, db) -> Dict[str, Any]:
    """
    Importeert het CSV-bestand van Rebo voor de Vereniging van Eigenaren (VvE).

    CRUCIALE REGEL:
    Alle eigenaren/leden die al bestaan (op basis van 'Index nummer' of 'Adres appartementsrecht')
    worden met rust gelaten. Uitsluitend nieuwe contacten worden toegevoegd.
    """
    text, delimiter, encoding = detect_dialect_and_encoding(file_bytes)

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return {
            "success": False,
            "message": "Het geüploade bestand is leeg.",
            "total": 0,
            "added": 0,
            "skipped": 0,
            "errors": 0,
            "details": []
        }

    header_row = [clean_cell(c) for c in rows[0]]
    header_map = {col.lower().strip(): idx for idx, col in enumerate(header_row)}

    index_col_idx = header_map.get("index nummer")
    adres_col_idx = header_map.get("adres appartementsrecht")
    naam_col_idx = header_map.get("naam")

    if index_col_idx is None and adres_col_idx is None and naam_col_idx is None:
        return {
            "success": False,
            "message": f"Kon de vereiste kolommen niet vinden. Gevonden headers: {', '.join(header_row[:6])}...",
            "total": 0,
            "added": 0,
            "skipped": 0,
            "errors": 1,
            "details": []
        }

    def get_val(row_data: List[str], col_name: str) -> str:
        idx = header_map.get(col_name.lower())
        if idx is not None and idx < len(row_data):
            return clean_cell(row_data[idx])
        return ""

    added = 0
    skipped = 0
    errors = 0
    details = []

    for row_idx, row in enumerate(rows[1:], start=2):
        if not any(row):
            continue

        index_nummer = get_val(row, "Index nummer")
        bestemming = get_val(row, "Bestemming")
        adres = get_val(row, "Adres appartementsrecht")
        naam = get_val(row, "Naam")
        postadres = get_val(row, "Postadres")

        if not (index_nummer or adres or naam):
            continue

        existing = db.find_existing(index_nummer=index_nummer, adres=adres)
        if existing:
            skipped += 1
            details.append({
                "regel": row_idx,
                "index_nummer": index_nummer or existing.index_nummer,
                "naam": existing.naam,
                "adres": existing.adres_appartementsrecht,
                "status": "OVERGESLAGEN",
                "toelichting": f"Bestaat al in VvE-administratie (ID: {existing.id[:8]}...). Niet gewijzigd."
            })
            continue

        # Slimme classificatie van het type VvE-lid
        bestemming_lower = bestemming.lower()
        if any(g in bestemming_lower for g in ("garage", "parkeer", "box", "stalling")):
            type_lid = "Garageboxhouder"
            bedrijfsnaam = ""
        elif any(b in bestemming_lower for b in ("bedrijf", "commercieel", "kantoor", "winkel", "praktijk", "horeca")):
            type_lid = "Bedrijf / Commercieel"
            bedrijfsnaam = naam
        else:
            type_lid = "Woningeigenaar"
            bedrijfsnaam = ""

        # Slimme detectie externe eigenaar:
        # Als het postadres verschilt van het adres van het appartementsrecht, woont eigenaar waarschijnlijk elders
        is_extern = False
        correspondentie = ""
        if postadres and adres:
            clean_p = "".join(postadres.lower().split())
            clean_a = "".join(adres.lower().split())
            if clean_a not in clean_p and clean_p not in clean_a:
                is_extern = True
                correspondentie = postadres

        try:
            contact_data = VveContactCreate(
                index_nummer=index_nummer or f"AUTO-{row_idx}",
                bestemming=bestemming or "Woning",
                adres_appartementsrecht=adres or f"Adres onbekend (regel {row_idx})",
                naam=naam or "Onbekende eigenaar",
                postadres=postadres,
                telefoonnummer=get_val(row, "Telefoonnummer"),
                telefoonnummer_2=get_val(row, "Telefoonnummer 2"),
                telefoonnummer_3=get_val(row, "Telefoonnummer 3"),
                email=get_val(row, "Email"),
                email_2=get_val(row, "Email 2"),
                email_3=get_val(row, "Email 3"),
                correspondentieadres_extern=correspondentie,
                is_externe_eigenaar=is_extern,
                garageboxnummers="",
                breukdeel="",
                type_lid=type_lid,
                bedrijfsnaam=bedrijfsnaam,
                contactpersoon_zakelijk=""
            )
            created = db.create(contact_data)
            added += 1
            details.append({
                "regel": row_idx,
                "index_nummer": created.index_nummer,
                "naam": created.naam,
                "adres": created.adres_appartementsrecht,
                "status": "TOEGEVOEGD",
                "toelichting": f"Nieuw VvE-lid opgeslagen ({created.type_lid})."
            })
        except Exception as e:
            errors += 1
            details.append({
                "regel": row_idx,
                "index_nummer": index_nummer,
                "naam": naam,
                "adres": adres,
                "status": "FOUT",
                "toelichting": f"Fout bij opslaan: {str(e)}"
            })

    return {
        "success": True,
        "total_rows": len(rows) - 1,
        "added": added,
        "skipped": skipped,
        "errors": errors,
        "encoding": encoding,
        "delimiter": delimiter,
        "details": details
    }
