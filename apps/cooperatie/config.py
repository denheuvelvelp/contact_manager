import os
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    app_name: str = "Huismeester Contactbeheer - Coöperatieve Vereniging"
    app_version: str = "1.0.0"
    port: int = int(os.getenv("PORT", "8080"))

    # Database configuratie
    # Als FIRESTORE_PROJECT_ID is ingesteld of USE_FIRESTORE=true, gebruikt de app Cloud Firestore.
    # Anders valt de app automatisch terug op lokale SQLite opslag voor soepele lokale ontwikkeling.
    use_firestore: bool = os.getenv("USE_FIRESTORE", "false").lower() in ("true", "1", "yes")
    firestore_project_id: str = os.getenv("FIRESTORE_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    firestore_collection: str = os.getenv("FIRESTORE_COLLECTION", "cooperatie_contacten")

    sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", "cooperatie_contacts.db")


settings = Settings()

