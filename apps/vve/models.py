from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class VveContactBase(BaseModel):
    # Exacte kolommen aangeleverd door Rebo voor de VvE
    index_nummer: str = Field(..., description="Index nummer uit Rebo export, bijv. 101, B-01, G-05")
    bestemming: Optional[str] = Field(default="Woning", description="Woning, Bedrijf, Commercieel, Garage")
    adres_appartementsrecht: str = Field(..., description="Adres van het appartementsrecht / unit")
    naam: str = Field(..., description="Naam van de eigenaar of onderneming")
    postadres: Optional[str] = Field(default="", description="Postadres van de eenheid")

    # Reguliere contactgegevens van de eigenaar zelf
    telefoonnummer: Optional[str] = Field(default="", description="Primair telefoonnummer eigenaar")
    telefoonnummer_2: Optional[str] = Field(default="", description="Tweede telefoonnummer")
    telefoonnummer_3: Optional[str] = Field(default="", description="Derde telefoonnummer")

    email: Optional[str] = Field(default="", description="Primair e-mailadres eigenaar")
    email_2: Optional[str] = Field(default="", description="Tweede e-mailadres")
    email_3: Optional[str] = Field(default="", description="Derde e-mailadres")

    # VvE-specifieke velden
    correspondentieadres_extern: Optional[str] = Field(
        default="",
        description="Correspondentieadres wanneer eigenaar elders woont (belegger/verhuurder)"
    )
    is_externe_eigenaar: bool = Field(default=False, description="Eigenaar woont niet in het complex")
    garageboxnummers: Optional[str] = Field(default="", description="Garagebox- of parkeerplaatsnummers (bijv. G-12)")
    breukdeel: Optional[str] = Field(default="", description="Breukdeel / stemverhouding (bijv. 15/1000)")
    type_lid: Optional[str] = Field(
        default="Woningeigenaar",
        description="Type lid: Woningeigenaar, Bedrijf / Commercieel, of Garageboxhouder"
    )
    bedrijfsnaam: Optional[str] = Field(default="", description="Indien bedrijf / commerciële ruimte")
    contactpersoon_zakelijk: Optional[str] = Field(default="", description="Vaste contactpersoon bij bedrijf of beheerder")

    # Noodcontactpersonen / Sleutelhouders (voor calamiteiten/lekkages)
    noodcontact_1_naam: Optional[str] = Field(default="", description="Naam 1e noodcontact / sleutelhouder")
    noodcontact_1_telefoon: Optional[str] = Field(default="", description="Telefoon 1e noodcontact")
    noodcontact_1_email: Optional[str] = Field(default="", description="E-mail 1e noodcontact")

    noodcontact_2_naam: Optional[str] = Field(default="", description="Naam 2e noodcontact / sleutelhouder")
    noodcontact_2_telefoon: Optional[str] = Field(default="", description="Telefoon 2e noodcontact")
    noodcontact_2_email: Optional[str] = Field(default="", description="E-mail 2e noodcontact")

    notities: Optional[str] = Field(default="", description="Interne VvE-notities")


class VveContactCreate(VveContactBase):
    pass


class VveContactUpdate(BaseModel):
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
    correspondentieadres_extern: Optional[str] = None
    is_externe_eigenaar: Optional[bool] = None
    garageboxnummers: Optional[str] = None
    breukdeel: Optional[str] = None
    type_lid: Optional[str] = None
    bedrijfsnaam: Optional[str] = None
    contactpersoon_zakelijk: Optional[str] = None
    noodcontact_1_naam: Optional[str] = None
    noodcontact_1_telefoon: Optional[str] = None
    noodcontact_1_email: Optional[str] = None
    noodcontact_2_naam: Optional[str] = None
    noodcontact_2_telefoon: Optional[str] = None
    noodcontact_2_email: Optional[str] = None
    notities: Optional[str] = None


class VveContact(VveContactBase):
    id: str
    aangemaakt_op: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    bijgewerkt_op: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    model_config = {"from_attributes": True}

