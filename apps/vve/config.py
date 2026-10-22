import os
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Huismeester Contactbeheer - Vereniging van Eigenaren (VvE)"
    app_version: str = "1.0.0"
    port: int = int(os.getenv("PORT", "8081"))

    # Database configuratie
    use_firestore: bool = os.getenv("USE_FIRESTORE", "false").lower() in ("true", "1", "yes")
    firestore_project_id: str = os.getenv("FIRESTORE_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    firestore_collection: str = os.getenv("FIRESTORE_COLLECTION", "vve_contacten")

    sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", "vve_contacts.db")


settings = Settings()
