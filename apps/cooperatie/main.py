from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates

from .config import settings
from .database import get_db
from .models import ContactCreate, ContactUpdate
from .importer import import_cooperatie_csv

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Contactmanager voor Huismeester - Coöperatieve Vereniging"
)

# Template configuratie
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/health")
def healthcheck():
    """Cloud Run healthcheck endpoint."""
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.get("/", response_class=RedirectResponse)
def index_redirect():
    return RedirectResponse(url="/contacten", status_code=302)


@app.get("/contacten", response_class=HTMLResponse)
def list_contacts(
    request: Request,
    q: Optional[str] = None,
    minder_mobiel: Optional[int] = None
):
    db = get_db()
    minder_mobiel_bool = bool(minder_mobiel == 1)
    contacts = db.list_all(search=q, minder_mobiel_only=minder_mobiel_bool)

    # Bereken statistieken voor het KPI banner
    all_contacts = db.list_all()
    total_count = len(all_contacts)
    with_emergency_count = sum(
        1 for c in all_contacts
        if c.telefoonnummer_2 or c.telefoonnummer_3 or c.email_2 or c.email_3 or c.noodcontactpersoon_1 or c.noodcontactpersoon_2
    )
    minder_mobiel_count = sum(1 for c in all_contacts if c.minder_mobiel)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "contacts": contacts,
            "search_query": q,
            "minder_mobiel_only": minder_mobiel_bool,
            "total_count": total_count,
            "with_emergency_count": with_emergency_count,
            "minder_mobiel_count": minder_mobiel_count,
        }
    )


@app.get("/contacten/nieuw", response_class=HTMLResponse)
def new_contact_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="contact_form.html",
        context={"contact": None}
    )


@app.post("/contacten/nieuw")
def create_contact_action(
    index_nummer: str = Form(...),
    bestemming: str = Form("Woning"),
    adres_appartementsrecht: str = Form(...),
    naam: str = Form(...),
    postadres: str = Form(""),
    telefoonnummer: str = Form(""),
    telefoonnummer_2: str = Form(""),
    telefoonnummer_3: str = Form(""),
    email: str = Form(""),
    email_2: str = Form(""),
    email_3: str = Form(""),
    noodcontactpersoon_1: str = Form(""),
    noodcontactpersoon_2: str = Form(""),
    etage: str = Form(""),
    minder_mobiel: Optional[int] = Form(None),
    huisdieren: str = Form(""),
    intercom_naam: str = Form(""),
    notities: str = Form("")
):
    db = get_db()
    
    # Controleer of index al bestaat
    existing = db.find_existing(index_nummer, adres_appartementsrecht)
    if existing:
        msg = f"Contact met index '{index_nummer}' of adres '{adres_appartementsrecht}' bestaat al."
        raise HTTPException(status_code=400, detail=msg)

    contact_in = ContactCreate(
        index_nummer=index_nummer,
        bestemming=bestemming,
        adres_appartementsrecht=adres_appartementsrecht,
        naam=naam,
        postadres=postadres,
        telefoonnummer=telefoonnummer,
        telefoonnummer_2=telefoonnummer_2,
        telefoonnummer_3=telefoonnummer_3,
        email=email,
        email_2=email_2,
        email_3=email_3,
        noodcontactpersoon_1=noodcontactpersoon_1,
        noodcontactpersoon_2=noodcontactpersoon_2,
        etage=etage,
        minder_mobiel=bool(minder_mobiel == 1),
        huisdieren=huisdieren,
        intercom_naam=intercom_naam,
        notities=notities
    )
    created = db.create(contact_in)
    return RedirectResponse(url=f"/contacten/{created.id}", status_code=303)


@app.get("/contacten/{contact_id}", response_class=HTMLResponse)
def get_contact_detail(request: Request, contact_id: str):
    db = get_db()
    contact = db.get_by_id(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Bewoner niet gevonden")

    return templates.TemplateResponse(
        request=request,
        name="contact_form.html",
        context={"contact": contact}
    )


@app.post("/contacten/{contact_id}")
def update_contact_action(
    contact_id: str,
    index_nummer: str = Form(...),
    bestemming: str = Form("Woning"),
    adres_appartementsrecht: str = Form(...),
    naam: str = Form(...),
    postadres: str = Form(""),
    telefoonnummer: str = Form(""),
    telefoonnummer_2: str = Form(""),
    telefoonnummer_3: str = Form(""),
    email: str = Form(""),
    email_2: str = Form(""),
    email_3: str = Form(""),
    noodcontactpersoon_1: str = Form(""),
    noodcontactpersoon_2: str = Form(""),
    etage: str = Form(""),
    minder_mobiel: Optional[int] = Form(None),
    huisdieren: str = Form(""),
    intercom_naam: str = Form(""),
    notities: str = Form("")
):
    db = get_db()
    contact = db.get_by_id(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Bewoner niet gevonden")

    update_in = ContactUpdate(
        bestemming=bestemming,
        adres_appartementsrecht=adres_appartementsrecht,
        naam=naam,
        postadres=postadres,
        telefoonnummer=telefoonnummer,
        telefoonnummer_2=telefoonnummer_2,
        telefoonnummer_3=telefoonnummer_3,
        email=email,
        email_2=email_2,
        email_3=email_3,
        noodcontactpersoon_1=noodcontactpersoon_1,
        noodcontactpersoon_2=noodcontactpersoon_2,
        etage=etage,
        minder_mobiel=bool(minder_mobiel == 1),
        huisdieren=huisdieren,
        intercom_naam=intercom_naam,
        notities=notities
    )
    db.update(contact_id, update_in)
    return RedirectResponse(url=f"/contacten/{contact_id}", status_code=303)


@app.post("/contacten/{contact_id}/verwijderen")
def delete_contact_action(contact_id: str):
    db = get_db()
    db.delete(contact_id)
    return RedirectResponse(url="/contacten", status_code=303)


@app.get("/importeren", response_class=HTMLResponse)
def import_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="import.html",
        context={"results": None}
    )


@app.post("/importeren", response_class=HTMLResponse)
async def handle_csv_upload(request: Request, file: UploadFile = File(...)):
    db = get_db()
    content = await file.read()
    results = import_cooperatie_csv(content, db)
    return templates.TemplateResponse(
        request=request,
        name="import.html",
        context={"results": results}
    )


@app.get("/sample-csv")
def download_sample_csv():
    sample_path = BASE_DIR / "sample_rebo_cooperatie.csv"
    return FileResponse(
        path=str(sample_path),
        filename="rebo_cooperatie_voorbeeld.csv",
        media_type="text/csv"
    )


# --- REST API Endpoints ---
@app.get("/api/v1/contacten")
def api_list_contacts(q: Optional[str] = None):
    db = get_db()
    return db.list_all(search=q)


@app.post("/api/v1/importeren")
async def api_import_csv(file: UploadFile = File(...)):
    db = get_db()
    content = await file.read()
    return import_cooperatie_csv(content, db)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.cooperatie.main:app", host="0.0.0.0", port=settings.port, reload=True)
