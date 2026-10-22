from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class ContactBase(BaseModel):
    # Exacte kolommen aangeleverd door Rebo voor de Coöperatieve Vereniging
    index_nummer: str = Field(..., description="Index nummer uit Rebo export, bijv. 101 of A-01")
    bestemming: Optional[str] = Field(default="Woning", description="Bijv. Woning of Appartement")
    adres_appartementsrecht: str = Field(..., description="Bijv. Dorpsstraat 10 A")
    naam: str = Field(..., description="Volledige naam van de bewoner")
    postadres: Optional[str] = Field(default="", description="Postadres")

    # Primair telefoon en noodtelefoons
    telefoonnummer: Optional[str] = Field(default="", description="Primair telefoonnummer bewoner")
    telefoonnummer_2: Optional[str] = Field(default="", description="Noodtelefoonnummer 1")
    telefoonnummer_3: Optional[str] = Field(default="", description="Noodtelefoonnummer 2")

    # Primair email en nood-emails
    email: Optional[str] = Field(default="", description="Primair e-mailadres bewoner")
    email_2: Optional[str] = Field(default="", description="Nood-e-mailadres 1")
    email_3: Optional[str] = Field(default="", description="Nood-e-mailadres 2")

    # Extra velden voor de huismeester (noodcontactpersonen en veiligheid)
    noodcontactpersoon_1: Optional[str] = Field(default="", description="Naam van eerste noodcontactpersoon")
    noodcontactpersoon_2: Optional[str] = Field(default="", description="Naam van tweede noodcontactpersoon")
    etage: Optional[str] = Field(default="", description="Verdieping/etage")
    minder_mobiel: bool = Field(default=False, description="Hulpbehoevend/minder mobiel bij calamiteiten/ontruiming")
    huisdieren: Optional[str] = Field(default="", description="Aanwezigheid van huisdieren (bijv. 1 hond, 2 katten)")
    intercom_naam: Optional[str] = Field(default="", description="Naam op het bellenbord/intercom")
    notities: Optional[str] = Field(default="", description="Interne huismeesternotities")


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    bestemming: Optional[str] = None
    adres_appartementsrecht: Optional[str] = None
    naam: Optional[str] = None
    postadres: Optional[str] = None
    telefoonnummer: Optional[str] = None
    telefoonnummer_2: Optional[str] = None
    telefoonnummer_3: Optional[str] = None
    email: Optional[str] = None
    email_2: Optional[str] = None
    email_3: Optional[str] = None
    noodcontactpersoon_1: Optional[str] = None
    noodcontactpersoon_2: Optional[str] = None
    etage: Optional[str] = None
    minder_mobiel: Optional[bool] = None
    huisdieren: Optional[str] = None
    intercom_naam: Optional[str] = None
    notities: Optional[str] = None


class Contact(ContactBase):
    id: str
    aangemaakt_op: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    bijgewerkt_op: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = {"from_attributes": True}
