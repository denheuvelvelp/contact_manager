from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import get_vve_db
from .models import VveContactCreate, VveContactUpdate
from .importer import import_vve_csv
from . import auth

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Contactmanager voor Huismeester - Vereniging van Eigenaren (VvE)"
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.middleware("http")
async def auth_guard_middleware(request: Request, call_next):
    """Beveiligt alle VvE beheerpagina's zodat alleen ingelogde @denheuvelvelp.nl gebruikers erbij kunnen."""
    path = request.url.path

    # Openbare paden
    public_paths = ("/health", "/login", "/auth/", "/static/")
    if path == "/" or any(path.startswith(p) for p in public_paths):
        return await call_next(request)

    user = auth.get_current_user(request)
    if not user:
        return RedirectResponse(url=f"/login?next={path}", status_code=303)

    return await call_next(request)


# Sessie-middleware wordt als laatste toegevoegd zodat request.session beschikbaar is in auth_guard_middleware
app.add_middleware(SessionMiddleware, secret_key=auth.SESSION_SECRET_KEY)
app.include_router(auth.auth_router)


@app.get("/health")
def healthcheck():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.get("/", response_class=RedirectResponse)
def index_redirect():
    return RedirectResponse(url="/contacten", status_code=302)


@app.get("/contacten", response_class=HTMLResponse)
def list_vve_contacts(
    request: Request,
    q: Optional[str] = None,
    type: Optional[str] = None,
    extern: Optional[int] = None,
    reset: Optional[int] = None
):
    db = get_vve_db()
    externe_only = bool(extern == 1)
    contacts = db.list_all(search=q, type_lid=type, externe_only=externe_only)

    all_contacts = db.list_all()
    total_count = len(all_contacts)
    woning_count = sum(1 for c in all_contacts if c.type_lid == "Woningeigenaar")
    bedrijf_count = sum(1 for c in all_contacts if c.type_lid == "Bedrijf / Commercieel")
    garage_count = sum(1 for c in all_contacts if c.type_lid == "Garageboxhouder")
    extern_count = sum(1 for c in all_contacts if c.is_externe_eigenaar)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "user": auth.get_current_user(request),
            "contacts": contacts,
            "search_query": q,
            "selected_type": type,
            "externe_only": externe_only,
            "total_count": total_count,
            "woning_count": woning_count,
            "bedrijf_count": bedrijf_count,
            "garage_count": garage_count,
            "extern_count": extern_count,
            "was_reset": bool(reset == 1)
        }
    )


@app.post("/contacten/reset")
def reset_vve_database_action():
    db = get_vve_db()
    db.reset_all()
    return RedirectResponse(url="/contacten?reset=1", status_code=303)


@app.get("/contacten/nieuw", response_class=HTMLResponse)
def new_vve_contact_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="contact_form.html",
        context={"user": auth.get_current_user(request), "contact": None}
    )


@app.post("/contacten/nieuw")
def create_vve_contact_action(
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
    correspondentieadres_extern: str = Form(""),
    is_externe_eigenaar: Optional[int] = Form(None),
    garageboxnummers: str = Form(""),
    breukdeel: str = Form(""),
    type_lid: str = Form("Woningeigenaar"),
    bedrijfsnaam: str = Form(""),
    contactpersoon_zakelijk: str = Form(""),
    noodcontact_1_naam: str = Form(""),
    noodcontact_1_telefoon: str = Form(""),
    noodcontact_1_email: str = Form(""),
    noodcontact_2_naam: str = Form(""),
    noodcontact_2_telefoon: str = Form(""),
    noodcontact_2_email: str = Form(""),
    notities: str = Form("")
):
    db = get_vve_db()
    existing = db.find_existing(index_nummer, adres_appartementsrecht)
    if existing:
        msg = f"VvE-eenheid met index '{index_nummer}' of adres '{adres_appartementsrecht}' bestaat al."
        raise HTTPException(status_code=400, detail=msg)

    contact_in = VveContactCreate(
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
        correspondentieadres_extern=correspondentieadres_extern,
        is_externe_eigenaar=bool(is_externe_eigenaar == 1),
        garageboxnummers=garageboxnummers,
        breukdeel=breukdeel,
        type_lid=type_lid,
        bedrijfsnaam=bedrijfsnaam,
        contactpersoon_zakelijk=contactpersoon_zakelijk,
        noodcontact_1_naam=noodcontact_1_naam,
        noodcontact_1_telefoon=noodcontact_1_telefoon,
        noodcontact_1_email=noodcontact_1_email,
        noodcontact_2_naam=noodcontact_2_naam,
        noodcontact_2_telefoon=noodcontact_2_telefoon,
        noodcontact_2_email=noodcontact_2_email,
        notities=notities
    )
    created = db.create(contact_in)
    return RedirectResponse(url=f"/contacten/{created.id}", status_code=303)


@app.get("/contacten/{contact_id}", response_class=HTMLResponse)
def get_vve_contact_detail(request: Request, contact_id: str):
    db = get_vve_db()
    contact = db.get_by_id(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="VvE-lid niet gevonden")

    return templates.TemplateResponse(
        request=request,
        name="contact_form.html",
        context={"user": auth.get_current_user(request), "contact": contact}
    )


@app.post("/contacten/{contact_id}")
def update_vve_contact_action(
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
    correspondentieadres_extern: str = Form(""),
    is_externe_eigenaar: Optional[int] = Form(None),
    garageboxnummers: str = Form(""),
    breukdeel: str = Form(""),
    type_lid: str = Form("Woningeigenaar"),
    bedrijfsnaam: str = Form(""),
    contactpersoon_zakelijk: str = Form(""),
    noodcontact_1_naam: str = Form(""),
    noodcontact_1_telefoon: str = Form(""),
    noodcontact_1_email: str = Form(""),
    noodcontact_2_naam: str = Form(""),
    noodcontact_2_telefoon: str = Form(""),
    noodcontact_2_email: str = Form(""),
    notities: str = Form("")
):
    db = get_vve_db()
    contact = db.get_by_id(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="VvE-lid niet gevonden")

    update_in = VveContactUpdate(
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
        correspondentieadres_extern=correspondentieadres_extern,
        is_externe_eigenaar=bool(is_externe_eigenaar == 1),
        garageboxnummers=garageboxnummers,
        breukdeel=breukdeel,
        type_lid=type_lid,
        bedrijfsnaam=bedrijfsnaam,
        contactpersoon_zakelijk=contactpersoon_zakelijk,
        noodcontact_1_naam=noodcontact_1_naam,
        noodcontact_1_telefoon=noodcontact_1_telefoon,
        noodcontact_1_email=noodcontact_1_email,
        noodcontact_2_naam=noodcontact_2_naam,
        noodcontact_2_telefoon=noodcontact_2_telefoon,
        noodcontact_2_email=noodcontact_2_email,
        notities=notities
    )
    db.update(contact_id, update_in)
    return RedirectResponse(url=f"/contacten/{contact_id}", status_code=303)


@app.post("/contacten/{contact_id}/verwijderen")
def delete_vve_contact_action(contact_id: str):
    db = get_vve_db()
    db.delete(contact_id)
    return RedirectResponse(url="/contacten", status_code=303)


@app.get("/importeren", response_class=HTMLResponse)
def import_vve_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="import.html",
        context={"user": auth.get_current_user(request), "results": None}
    )


@app.post("/importeren", response_class=HTMLResponse)
async def handle_vve_csv_upload(request: Request, file: UploadFile = File(...)):
    db = get_vve_db()
    content = await file.read()
    results = import_vve_csv(content, db)
    return templates.TemplateResponse(
        request=request,
        name="import.html",
        context={"user": auth.get_current_user(request), "results": results}
    )


@app.get("/sample-csv")
def download_sample_vve_csv():
    sample_path = BASE_DIR / "sample_rebo_vve.csv"
    return FileResponse(
        path=str(sample_path),
        filename="rebo_vve_voorbeeld.csv",
        media_type="text/csv"
    )


# --- REST API Endpoints ---
@app.get("/api/v1/contacten")
def api_list_vve_contacts(q: Optional[str] = None):
    db = get_vve_db()
    return db.list_all(search=q)


@app.post("/api/v1/importeren")
async def api_import_vve_csv(file: UploadFile = File(...)):
    db = get_vve_db()
    content = await file.read()
    return import_vve_csv(content, db)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.vve.main:app", host="0.0.0.0", port=settings.port, reload=True)

