import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Any
from .config import settings
from .models import Contact, ContactCreate, ContactUpdate, Mailinglijst, MailinglijstCreate, MailinglijstUpdate

# Initialiseer Firestore indien geconfigureerd
firestore_client = None
if settings.use_firestore or settings.firestore_project_id:
    try:
        from google.cloud import firestore
        if settings.firestore_project_id:
            firestore_client = firestore.Client(project=settings.firestore_project_id)
        else:
            firestore_client = firestore.Client()
        print(f"[Database] Verbonden met Google Cloud Firestore (Collectie: {settings.firestore_collection})")
    except Exception as e:
        print(f"[Database] Waarschuwing: Kon Firestore niet initialiseren ({e}). Terugval naar lokale SQLite opslag.")
        firestore_client = None


class SQLiteStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contacten (
                    id TEXT PRIMARY KEY,
                    index_nummer TEXT NOT NULL,
                    bestemming TEXT,
                    adres_appartementsrecht TEXT NOT NULL,
                    naam TEXT NOT NULL,
                    postadres TEXT,
                    telefoonnummer TEXT,
                    telefoonnummer_2 TEXT,
                    telefoonnummer_3 TEXT,
                    email TEXT,
                    email_2 TEXT,
                    email_3 TEXT,
                    noodcontact_1_naam TEXT,
                    noodcontact_1_telefoon TEXT,
                    noodcontact_1_email TEXT,
                    noodcontact_2_naam TEXT,
                    noodcontact_2_telefoon TEXT,
                    noodcontact_2_email TEXT,
                    etage TEXT,
                    minder_mobiel INTEGER DEFAULT 0,
                    huisdieren TEXT,
                    intercom_naam TEXT,
                    notities TEXT,
                    aangemaakt_op TEXT NOT NULL,
                    bijgewerkt_op TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_index_nummer ON contacten (index_nummer)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_adres ON contacten (adres_appartementsrecht)")

            # Mailinglijsten tabel
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cooperatie_mailinglijsten (
                    id TEXT PRIMARY KEY,
                    naam TEXT NOT NULL,
                    email_groep TEXT NOT NULL,
                    omschrijving TEXT,
                    leden TEXT,
                    google_group_id TEXT,
                    aangemaakt_op TEXT NOT NULL,
                    bijgewerkt_op TEXT NOT NULL,
                    laatst_gesynchroniseerd TEXT,
                    sync_status TEXT DEFAULT 'Niet gesynchroniseerd'
                )
            """)
            conn.commit()

    def _row_to_contact(self, row: sqlite3.Row) -> Contact:
        data = dict(row)
        data["minder_mobiel"] = bool(data.get("minder_mobiel", 0))
        return Contact(**data)

    def list_all(self, search: Optional[str] = None, minder_mobiel_only: bool = False) -> List[Contact]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM contacten WHERE 1=1"
            params: List[Any] = []

            if minder_mobiel_only:
                query += " AND minder_mobiel = 1"

            if search:
                query += (
                    " AND (index_nummer LIKE ? OR naam LIKE ? OR adres_appartementsrecht LIKE ?"
                    " OR telefoonnummer LIKE ? OR telefoonnummer_2 LIKE ? OR telefoonnummer_3 LIKE ?"
                    " OR email LIKE ? OR email_2 LIKE ? OR email_3 LIKE ?"
                    " OR noodcontact_1_naam LIKE ? OR noodcontact_2_naam LIKE ?)"
                )
                term = f"%{search}%"
                params.extend([term] * 11)

            query += " ORDER BY CAST(index_nummer AS INTEGER) ASC, index_nummer ASC"
            cursor.execute(query, params)
            return [self._row_to_contact(row) for row in cursor.fetchall()]

    def get_by_id(self, contact_id: str) -> Optional[Contact]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contacten WHERE id = ?", (contact_id,))
            row = cursor.fetchone()
            return self._row_to_contact(row) if row else None

    def find_existing(self, index_nummer: str, adres: str) -> Optional[Contact]:
        """Zoekt of een contact al bestaat op basis van index_nummer of adres."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            clean_index = index_nummer.strip()
            clean_adres = adres.strip().lower()

            cursor.execute("""
                SELECT * FROM contacten
                WHERE (index_nummer != '' AND index_nummer = ?)
                   OR (adres_appartementsrecht != '' AND LOWER(adres_appartementsrecht) = ?)
                LIMIT 1
            """, (clean_index, clean_adres))
            row = cursor.fetchone()
            return self._row_to_contact(row) if row else None

    def create(self, contact_in: ContactCreate) -> Contact:
        contact_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO contacten (
                    id, index_nummer, bestemming, adres_appartementsrecht, naam, postadres,
                    telefoonnummer, telefoonnummer_2, telefoonnummer_3,
                    email, email_2, email_3,
                    noodcontact_1_naam, noodcontact_1_telefoon, noodcontact_1_email,
                    noodcontact_2_naam, noodcontact_2_telefoon, noodcontact_2_email,
                    etage, minder_mobiel, huisdieren, intercom_naam, notities,
                    aangemaakt_op, bijgewerkt_op
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                contact_id,
                contact_in.index_nummer.strip(),
                contact_in.bestemming or "",
                contact_in.adres_appartementsrecht.strip(),
                contact_in.naam.strip(),
                contact_in.postadres or "",
                contact_in.telefoonnummer or "",
                contact_in.telefoonnummer_2 or "",
                contact_in.telefoonnummer_3 or "",
                contact_in.email or "",
                contact_in.email_2 or "",
                contact_in.email_3 or "",
                contact_in.noodcontact_1_naam or "",
                contact_in.noodcontact_1_telefoon or "",
                contact_in.noodcontact_1_email or "",
                contact_in.noodcontact_2_naam or "",
                contact_in.noodcontact_2_telefoon or "",
                contact_in.noodcontact_2_email or "",
                contact_in.etage or "",
                1 if contact_in.minder_mobiel else 0,
                contact_in.huisdieren or "",
                contact_in.intercom_naam or "",
                contact_in.notities or "",
                now,
                now
            ))
            conn.commit()
        return self.get_by_id(contact_id)

    def update(self, contact_id: str, update_in: ContactUpdate) -> Optional[Contact]:
        existing = self.get_by_id(contact_id)
        if not existing:
            return None

        update_dict = update_in.model_dump(exclude_unset=True)
        if not update_dict:
            return existing

        update_dict["bijgewerkt_op"] = datetime.now(timezone.utc).isoformat()
        if "minder_mobiel" in update_dict and update_dict["minder_mobiel"] is not None:
            update_dict["minder_mobiel"] = 1 if update_dict["minder_mobiel"] else 0

        fields = [f"{k} = ?" for k in update_dict.keys()]
        values = list(update_dict.values()) + [contact_id]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE contacten SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()

        return self.get_by_id(contact_id)

    def delete(self, contact_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM contacten WHERE id = ?", (contact_id,))
            conn.commit()
            return cursor.rowcount > 0

    def reset_all(self) -> int:
        """Wist alle contacten zodat de gebruiker vanaf nul kan beginnen."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM contacten")
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM contacten")
            conn.commit()
            return count

    # --- Mailinglijsten beheer ---
    def _row_to_mailinglijst(self, row: sqlite3.Row) -> Mailinglijst:
        data = dict(row)
        leden_raw = data.get("leden")
        if leden_raw:
            try:
                data["leden"] = json.loads(leden_raw)
            except Exception:
                data["leden"] = []
        else:
            data["leden"] = []
        return Mailinglijst(**data)

    def list_mailinglijsten(self) -> List[Mailinglijst]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cooperatie_mailinglijsten ORDER BY naam ASC")
            return [self._row_to_mailinglijst(r) for r in cursor.fetchall()]

    def get_mailinglijst(self, ml_id: str) -> Optional[Mailinglijst]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cooperatie_mailinglijsten WHERE id = ?", (ml_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_mailinglijst(row)

    def create_mailinglijst(self, data: MailinglijstCreate) -> Mailinglijst:
        ml_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cooperatie_mailinglijsten (
                    id, naam, email_groep, omschrijving, leden, google_group_id,
                    aangemaakt_op, bijgewerkt_op, laatst_gesynchroniseerd, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ml_id, data.naam, data.email_groep, data.omschrijving or "",
                json.dumps([]), "", now, now, "", "Niet gesynchroniseerd"
            ))
            conn.commit()
        return self.get_mailinglijst(ml_id)

    def update_mailinglijst(self, ml_id: str, data: MailinglijstUpdate) -> Optional[Mailinglijst]:
        ml = self.get_mailinglijst(ml_id)
        if not ml:
            return None
        now = datetime.now(timezone.utc).isoformat()
        fields = []
        values = []
        if data.naam is not None:
            fields.append("naam = ?")
            values.append(data.naam)
        if data.email_groep is not None:
            fields.append("email_groep = ?")
            values.append(data.email_groep)
        if data.omschrijving is not None:
            fields.append("omschrijving = ?")
            values.append(data.omschrijving)

        if not fields:
            return ml

        fields.append("bijgewerkt_op = ?")
        values.append(now)
        values.append(ml_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE cooperatie_mailinglijsten SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()
        return self.get_mailinglijst(ml_id)

    def delete_mailinglijst(self, ml_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cooperatie_mailinglijsten WHERE id = ?", (ml_id,))
            conn.commit()
            return cursor.rowcount > 0

    def add_members_to_mailinglijst(self, ml_id: str, contact_ids: List[str]) -> Optional[Mailinglijst]:
        ml = self.get_mailinglijst(ml_id)
        if not ml:
            return None
        current_members = set(ml.leden)
        for cid in contact_ids:
            if cid:
                current_members.add(cid)
        new_list = sorted(list(current_members))
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE cooperatie_mailinglijsten SET leden = ?, bijgewerkt_op = ? WHERE id = ?",
                (json.dumps(new_list), now, ml_id)
            )
            conn.commit()
        return self.get_mailinglijst(ml_id)

    def remove_member_from_mailinglijst(self, ml_id: str, contact_id: str) -> Optional[Mailinglijst]:
        ml = self.get_mailinglijst(ml_id)
        if not ml:
            return None
        new_list = [c for c in ml.leden if c != contact_id]
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE cooperatie_mailinglijsten SET leden = ?, bijgewerkt_op = ? WHERE id = ?",
                (json.dumps(new_list), now, ml_id)
            )
            conn.commit()
        return self.get_mailinglijst(ml_id)

    def update_sync_status(self, ml_id: str, status: str, sync_time: str, google_group_id: Optional[str] = None) -> Optional[Mailinglijst]:
        ml = self.get_mailinglijst(ml_id)
        if not ml:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if google_group_id:
                cursor.execute(
                    "UPDATE cooperatie_mailinglijsten SET sync_status = ?, laatst_gesynchroniseerd = ?, google_group_id = ? WHERE id = ?",
                    (status, sync_time, google_group_id, ml_id)
                )
            else:
                cursor.execute(
                    "UPDATE cooperatie_mailinglijsten SET sync_status = ?, laatst_gesynchroniseerd = ? WHERE id = ?",
                    (status, sync_time, ml_id)
                )
            conn.commit()
        return self.get_mailinglijst(ml_id)



class FirestoreStore:
    def __init__(self, client, collection_name: str):
        self.client = client
        self.col = self.client.collection(collection_name)

    def list_all(self, search: Optional[str] = None, minder_mobiel_only: bool = False) -> List[Contact]:
        query = self.col
        if minder_mobiel_only:
            query = query.where("minder_mobiel", "==", True)

        docs = query.stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(Contact(**data))

        if search:
            s = search.lower()
            results = [
                c for c in results
                if s in c.index_nummer.lower()
                or s in c.naam.lower()
                or s in c.adres_appartementsrecht.lower()
                or s in (c.telefoonnummer or "").lower()
                or s in (c.telefoonnummer_2 or "").lower()
                or s in (c.telefoonnummer_3 or "").lower()
                or s in (c.email or "").lower()
                or s in (c.email_2 or "").lower()
                or s in (c.email_3 or "").lower()
                or s in (c.noodcontact_1_naam or "").lower()
                or s in (c.noodcontact_2_naam or "").lower()
            ]

        results.sort(key=lambda x: (int(x.index_nummer) if x.index_nummer.isdigit() else 999999, x.index_nummer))
        return results

    def get_by_id(self, contact_id: str) -> Optional[Contact]:
        doc = self.col.document(contact_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        return Contact(**data)

    def find_existing(self, index_nummer: str, adres: str) -> Optional[Contact]:
        clean_index = index_nummer.strip()
        clean_adres = adres.strip().lower()

        if clean_index:
            query_index = self.col.where("index_nummer", "==", clean_index).limit(1).stream()
            for doc in query_index:
                data = doc.to_dict()
                data["id"] = doc.id
                return Contact(**data)

        if clean_adres:
            docs = self.col.stream()
            for doc in docs:
                data = doc.to_dict()
                if data.get("adres_appartementsrecht", "").strip().lower() == clean_adres:
                    data["id"] = doc.id
                    return Contact(**data)

        return None

    def create(self, contact_in: ContactCreate) -> Contact:
        doc_ref = self.col.document()
        now = datetime.now(timezone.utc).isoformat()
        data = contact_in.model_dump()
        data["id"] = doc_ref.id
        data["aangemaakt_op"] = now
        data["bijgewerkt_op"] = now
        doc_ref.set(data)
        return Contact(**data)

    def update(self, contact_id: str, update_in: ContactUpdate) -> Optional[Contact]:
        doc_ref = self.col.document(contact_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None

        update_dict = update_in.model_dump(exclude_unset=True)
        if not update_dict:
            data = doc.to_dict()
            data["id"] = doc.id
            return Contact(**data)

        update_dict["bijgewerkt_op"] = datetime.now(timezone.utc).isoformat()
        doc_ref.update(update_dict)
        updated_doc = doc_ref.get()
        data = updated_doc.to_dict()
        data["id"] = updated_doc.id
        return Contact(**data)

    def delete(self, contact_id: str) -> bool:
        doc_ref = self.col.document(contact_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False
        doc_ref.delete()
        return True

    def reset_all(self) -> int:
        """Wist alle documenten in de Firestore collectie."""
        docs = list(self.col.stream())
        count = len(docs)
        for doc in docs:
            doc.reference.delete()
        return count

    # --- Mailinglijsten beheer in Firestore ---
    @property
    def ml_col(self):
        return self.client.collection("cooperatie_mailinglijsten")

    def list_mailinglijsten(self) -> List[Mailinglijst]:
        docs = self.ml_col.stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            if "leden" not in data or not isinstance(data["leden"], list):
                data["leden"] = []
            results.append(Mailinglijst(**data))
        results.sort(key=lambda x: x.naam.lower())
        return results

    def get_mailinglijst(self, ml_id: str) -> Optional[Mailinglijst]:
        doc = self.ml_col.document(ml_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        if "leden" not in data or not isinstance(data["leden"], list):
            data["leden"] = []
        return Mailinglijst(**data)

    def create_mailinglijst(self, data: MailinglijstCreate) -> Mailinglijst:
        doc_ref = self.ml_col.document()
        now = datetime.now(timezone.utc).isoformat()
        payload = data.model_dump()
        payload["id"] = doc_ref.id
        payload["leden"] = []
        payload["google_group_id"] = ""
        payload["aangemaakt_op"] = now
        payload["bijgewerkt_op"] = now
        payload["laatst_gesynchroniseerd"] = ""
        payload["sync_status"] = "Niet gesynchroniseerd"
        doc_ref.set(payload)
        return Mailinglijst(**payload)

    def update_mailinglijst(self, ml_id: str, data: MailinglijstUpdate) -> Optional[Mailinglijst]:
        doc_ref = self.ml_col.document(ml_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None
        update_dict = data.model_dump(exclude_unset=True)
        if not update_dict:
            return self.get_mailinglijst(ml_id)
        update_dict["bijgewerkt_op"] = datetime.now(timezone.utc).isoformat()
        doc_ref.update(update_dict)
        return self.get_mailinglijst(ml_id)

    def delete_mailinglijst(self, ml_id: str) -> bool:
        doc_ref = self.ml_col.document(ml_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True

    def add_members_to_mailinglijst(self, ml_id: str, contact_ids: List[str]) -> Optional[Mailinglijst]:
        ml = self.get_mailinglijst(ml_id)
        if not ml:
            return None
        current_members = set(ml.leden)
        for cid in contact_ids:
            if cid:
                current_members.add(cid)
        new_list = sorted(list(current_members))
        now = datetime.now(timezone.utc).isoformat()
        self.ml_col.document(ml_id).update({
            "leden": new_list,
            "bijgewerkt_op": now
        })
        return self.get_mailinglijst(ml_id)

    def remove_member_from_mailinglijst(self, ml_id: str, contact_id: str) -> Optional[Mailinglijst]:
        ml = self.get_mailinglijst(ml_id)
        if not ml:
            return None
        new_list = [c for c in ml.leden if c != contact_id]
        now = datetime.now(timezone.utc).isoformat()
        self.ml_col.document(ml_id).update({
            "leden": new_list,
            "bijgewerkt_op": now
        })
        return self.get_mailinglijst(ml_id)

    def update_sync_status(self, ml_id: str, status: str, sync_time: str, google_group_id: Optional[str] = None) -> Optional[Mailinglijst]:
        doc_ref = self.ml_col.document(ml_id)
        if not doc_ref.get().exists:
            return None
        payload = {
            "sync_status": status,
            "laatst_gesynchroniseerd": sync_time
        }
        if google_group_id:
            payload["google_group_id"] = google_group_id
        doc_ref.update(payload)
        return self.get_mailinglijst(ml_id)



# Actieve repository selector
def get_db():
    if firestore_client:
        return FirestoreStore(firestore_client, settings.firestore_collection)
    return SQLiteStore(settings.sqlite_db_path)
