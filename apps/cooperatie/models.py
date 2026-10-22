from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class ContactBase(BaseModel):
    # Exacte kolommen aangeleverd door Rebo voor de Coöperatieve Vereniging
    index_nummer: str = Field(..., description="Index nummer uit Rebo export, bijv. 101 of A-01")
    bestemming: Optional[str] = Field(default="Woning", description="Bijv. Woning of Appartement")
    adres_appartementsrecht: str = Field(..., description="Bijv. Dorpsstraat 10 A")
    naam: str = Field(..., description="Volledige naam van de eigenaar/bewoner")
    postadres: Optional[str] = Field(default="", description="Postadres")

    # Contactgegevens van de eigenaar/bewoner zelf (meerdere nummers en e-mails)
    telefoonnummer: Optional[str] = Field(default="", description="Primair telefoonnummer eigenaar/bewoner")
    telefoonnummer_2: Optional[str] = Field(default="", description="Tweede telefoonnummer eigenaar/bewoner")
    telefoonnummer_3: Optional[str] = Field(default="", description="Derde telefoonnummer eigenaar/bewoner")

    email: Optional[str] = Field(default="", description="Primair e-mailadres eigenaar/bewoner")
    email_2: Optional[str] = Field(default="", description="Tweede e-mailadres eigenaar/bewoner")
    email_3: Optional[str] = Field(default="", description="Derde e-mailadres eigenaar/bewoner")

    # Aparte Noodcontacten (2 stuks, specifiek voor calamiteiten)
    noodcontact_1_naam: Optional[str] = Field(default="", description="Naam van 1e noodcontactpersoon")
    noodcontact_1_telefoon: Optional[str] = Field(default="", description="Telefoonnummer 1e noodcontactpersoon")
    noodcontact_1_email: Optional[str] = Field(default="", description="E-mailadres 1e noodcontactpersoon")

    noodcontact_2_naam: Optional[str] = Field(default="", description="Naam van 2e noodcontactpersoon")
    noodcontact_2_telefoon: Optional[str] = Field(default="", description="Telefoonnummer 2e noodcontactpersoon")
    noodcontact_2_email: Optional[str] = Field(default="", description="E-mailadres 2e noodcontactpersoon")

    # Huismeester- & gebouwgegevens
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
    noodcontact_1_naam: Optional[str] = None
    noodcontact_1_telefoon: Optional[str] = None
    noodcontact_1_email: Optional[str] = None
    noodcontact_2_naam: Optional[str] = None
    noodcontact_2_telefoon: Optional[str] = None
    noodcontact_2_email: Optional[str] = None
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
