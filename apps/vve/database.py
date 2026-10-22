import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Any
from .config import settings
from .models import VveContact, VveContactCreate, VveContactUpdate

# Initialiseer Firestore indien geconfigureerd
firestore_client = None
if settings.use_firestore or settings.firestore_project_id:
    try:
        from google.cloud import firestore
        if settings.firestore_project_id:
            firestore_client = firestore.Client(project=settings.firestore_project_id)
        else:
            firestore_client = firestore.Client()
        print(f"[Database VvE] Verbonden met Firestore (Collectie: {settings.firestore_collection})")
    except Exception as e:
        print(f"[Database VvE] Waarschuwing: Kon Firestore niet laden ({e}). Terugval naar SQLite.")
        firestore_client = None


class VveSQLiteStore:
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
                CREATE TABLE IF NOT EXISTS vve_contacten (
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
                    correspondentieadres_extern TEXT,
                    is_externe_eigenaar INTEGER DEFAULT 0,
                    garageboxnummers TEXT,
                    breukdeel TEXT,
                    type_lid TEXT DEFAULT 'Woningeigenaar',
                    bedrijfsnaam TEXT,
                    contactpersoon_zakelijk TEXT,
                    noodcontact_1_naam TEXT,
                    noodcontact_1_telefoon TEXT,
                    noodcontact_1_email TEXT,
                    noodcontact_2_naam TEXT,
                    noodcontact_2_telefoon TEXT,
                    noodcontact_2_email TEXT,
                    notities TEXT,
                    aangemaakt_op TEXT NOT NULL,
                    bijgewerkt_op TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vve_index ON vve_contacten (index_nummer)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vve_adres ON vve_contacten (adres_appartementsrecht)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vve_type ON vve_contacten (type_lid)")
            conn.commit()

    def _row_to_contact(self, row: sqlite3.Row) -> VveContact:
        data = dict(row)
        data["is_externe_eigenaar"] = bool(data.get("is_externe_eigenaar", 0))
        return VveContact(**data)

    def list_all(
        self,
        search: Optional[str] = None,
        type_lid: Optional[str] = None,
        externe_only: bool = False
    ) -> List[VveContact]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM vve_contacten WHERE 1=1"
            params: List[Any] = []

            if externe_only:
                query += " AND is_externe_eigenaar = 1"

            if type_lid:
                query += " AND type_lid = ?"
                params.append(type_lid)

            if search:
                query += (
                    " AND (index_nummer LIKE ? OR naam LIKE ? OR adres_appartementsrecht LIKE ?"
                    " OR bedrijfsnaam LIKE ? OR garageboxnummers LIKE ? OR breukdeel LIKE ?"
                    " OR telefoonnummer LIKE ? OR email LIKE ? OR correspondentieadres_extern LIKE ?)"
                )
                term = f"%{search}%"
                params.extend([term] * 9)

            query += " ORDER BY CAST(index_nummer AS INTEGER) ASC, index_nummer ASC"
            cursor.execute(query, params)
            return [self._row_to_contact(row) for row in cursor.fetchall()]

    def get_by_id(self, contact_id: str) -> Optional[VveContact]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vve_contacten WHERE id = ?", (contact_id,))
            row = cursor.fetchone()
            return self._row_to_contact(row) if row else None

    def find_existing(self, index_nummer: str, adres: str) -> Optional[VveContact]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            clean_index = index_nummer.strip()
            clean_adres = adres.strip().lower()

            cursor.execute("""
                SELECT * FROM vve_contacten
                WHERE (index_nummer != '' AND index_nummer = ?)
                   OR (adres_appartementsrecht != '' AND LOWER(adres_appartementsrecht) = ?)
                LIMIT 1
            """, (clean_index, clean_adres))
            row = cursor.fetchone()
            return self._row_to_contact(row) if row else None

    def create(self, contact_in: VveContactCreate) -> VveContact:
        contact_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vve_contacten (
                    id, index_nummer, bestemming, adres_appartementsrecht, naam, postadres,
                    telefoonnummer, telefoonnummer_2, telefoonnummer_3,
                    email, email_2, email_3,
                    correspondentieadres_extern, is_externe_eigenaar, garageboxnummers, breukdeel,
                    type_lid, bedrijfsnaam, contactpersoon_zakelijk,
                    noodcontact_1_naam, noodcontact_1_telefoon, noodcontact_1_email,
                    noodcontact_2_naam, noodcontact_2_telefoon, noodcontact_2_email,
                    notities, aangemaakt_op, bijgewerkt_op
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                contact_in.correspondentieadres_extern or "",
                1 if contact_in.is_externe_eigenaar else 0,
                contact_in.garageboxnummers or "",
                contact_in.breukdeel or "",
                contact_in.type_lid or "Woningeigenaar",
                contact_in.bedrijfsnaam or "",
                contact_in.contactpersoon_zakelijk or "",
                contact_in.noodcontact_1_naam or "",
                contact_in.noodcontact_1_telefoon or "",
                contact_in.noodcontact_1_email or "",
                contact_in.noodcontact_2_naam or "",
                contact_in.noodcontact_2_telefoon or "",
                contact_in.noodcontact_2_email or "",
                contact_in.notities or "",
                now,
                now
            ))
            conn.commit()
        return self.get_by_id(contact_id)

    def update(self, contact_id: str, update_in: VveContactUpdate) -> Optional[VveContact]:
        existing = self.get_by_id(contact_id)
        if not existing:
            return None

        update_dict = update_in.model_dump(exclude_unset=True)
        if not update_dict:
            return existing

        update_dict["bijgewerkt_op"] = datetime.now(timezone.utc).isoformat()
        if "is_externe_eigenaar" in update_dict and update_dict["is_externe_eigenaar"] is not None:
            update_dict["is_externe_eigenaar"] = 1 if update_dict["is_externe_eigenaar"] else 0

        fields = [f"{k} = ?" for k in update_dict.keys()]
        values = list(update_dict.values()) + [contact_id]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE vve_contacten SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()

        return self.get_by_id(contact_id)

    def delete(self, contact_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM vve_contacten WHERE id = ?", (contact_id,))
            conn.commit()
            return cursor.rowcount > 0

    def reset_all(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM vve_contacten")
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM vve_contacten")
            conn.commit()
            return count


class VveFirestoreStore:
    def __init__(self, client, collection_name: str):
        self.client = client
        self.col = self.client.collection(collection_name)

    def list_all(
        self,
        search: Optional[str] = None,
        type_lid: Optional[str] = None,
        externe_only: bool = False
    ) -> List[VveContact]:
        query = self.col
        if externe_only:
            query = query.where("is_externe_eigenaar", "==", True)
        if type_lid:
            query = query.where("type_lid", "==", type_lid)

        docs = query.stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(VveContact(**data))

        if search:
            s = search.lower()
            results = [
                c for c in results
                if s in c.index_nummer.lower()
                or s in c.naam.lower()
                or s in c.adres_appartementsrecht.lower()
                or s in (c.bedrijfsnaam or "").lower()
                or s in (c.garageboxnummers or "").lower()
                or s in (c.breukdeel or "").lower()
                or s in (c.telefoonnummer or "").lower()
                or s in (c.email or "").lower()
                or s in (c.correspondentieadres_extern or "").lower()
            ]

        results.sort(key=lambda x: (int(x.index_nummer) if x.index_nummer.isdigit() else 999999, x.index_nummer))
        return results

    def get_by_id(self, contact_id: str) -> Optional[VveContact]:
        doc = self.col.document(contact_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        return VveContact(**data)

    def find_existing(self, index_nummer: str, adres: str) -> Optional[VveContact]:
        clean_index = index_nummer.strip()
        clean_adres = adres.strip().lower()

        if clean_index:
            query_index = self.col.where("index_nummer", "==", clean_index).limit(1).stream()
            for doc in query_index:
                data = doc.to_dict()
                data["id"] = doc.id
                return VveContact(**data)

        if clean_adres:
            docs = self.col.stream()
            for doc in docs:
                data = doc.to_dict()
                if data.get("adres_appartementsrecht", "").strip().lower() == clean_adres:
                    data["id"] = doc.id
                    return VveContact(**data)

        return None

    def create(self, contact_in: VveContactCreate) -> VveContact:
        doc_ref = self.col.document()
        now = datetime.now(timezone.utc).isoformat()
        data = contact_in.model_dump()
        data["id"] = doc_ref.id
        data["aangemaakt_op"] = now
        data["bijgewerkt_op"] = now
        doc_ref.set(data)
        return VveContact(**data)

    def update(self, contact_id: str, update_in: VveContactUpdate) -> Optional[VveContact]:
        doc_ref = self.col.document(contact_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None

        update_dict = update_in.model_dump(exclude_unset=True)
        if not update_dict:
            data = doc.to_dict()
            data["id"] = doc.id
            return VveContact(**data)

        update_dict["bijgewerkt_op"] = datetime.now(timezone.utc).isoformat()
        doc_ref.update(update_dict)
        updated_doc = doc_ref.get()
        data = updated_doc.to_dict()
        data["id"] = updated_doc.id
        return VveContact(**data)

    def delete(self, contact_id: str) -> bool:
        doc_ref = self.col.document(contact_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False
        doc_ref.delete()
        return True

    def reset_all(self) -> int:
        docs = list(self.col.stream())
        count = len(docs)
        for doc in docs:
            doc.reference.delete()
        return count


def get_vve_db():
    if firestore_client:
        return VveFirestoreStore(firestore_client, settings.firestore_collection)
    return VveSQLiteStore(settings.sqlite_db_path)

