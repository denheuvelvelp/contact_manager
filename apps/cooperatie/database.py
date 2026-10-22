import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Any
from .config import settings
from .models import Contact, ContactCreate, ContactUpdate

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
                    noodcontactpersoon_1 TEXT,
                    noodcontactpersoon_2 TEXT,
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
                    " OR telefoonnummer LIKE ? OR email LIKE ?)"
                )
                term = f"%{search}%"
                params.extend([term, term, term, term, term])

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
                    noodcontactpersoon_1, noodcontactpersoon_2, etage,
                    minder_mobiel, huisdieren, intercom_naam, notities,
                    aangemaakt_op, bijgewerkt_op
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                contact_in.noodcontactpersoon_1 or "",
                contact_in.noodcontactpersoon_2 or "",
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
                or s in (c.email or "").lower()
            ]

        # Sorteer op index_nummer
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


# Actieve repository selector
def get_db():
    if firestore_client:
        return FirestoreStore(firestore_client, settings.firestore_collection)
    return SQLiteStore(settings.sqlite_db_path)
