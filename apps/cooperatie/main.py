from pathlib import Path
from typing import Optional, List
import urllib.parse
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import get_db
from .models import ContactCreate, ContactUpdate, MailinglijstCreate
from .importer import import_cooperatie_csv
from . import auth
from shared.google_workspace import workspace_manager

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Contactmanager voor Huismeester - Coöperatieve Vereniging"
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.middleware("http")
async def auth_guard_middleware(request: Request, call_next):
    """Beveiligt alle beheerpagina's zodat alleen ingelogde gebruikers erbij kunnen."""
    path = request.url.path

    # Openbare paden
    public_paths = ("/health", "/login", "/auth/", "/static/")
    if path == "/" or any(path.startswith(p) for p in public_paths):
        return await call_next(request)

    # Controleer of gebruiker is ingelogd
    user = auth.get_current_user(request)
    if not user:
        return RedirectResponse(url=f"/login?next={path}", status_code=303)

    return await call_next(request)


# Sessie-middleware wordt als laatste toegevoegd zodat request.session beschikbaar is in auth_guard_middleware
app.add_middleware(SessionMiddleware, secret_key=auth.SESSION_SECRET_KEY)
app.include_router(auth.auth_router)


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
    minder_mobiel: Optional[int] = None,
    reset: Optional[int] = None
):
    db = get_db()
    minder_mobiel_bool = bool(minder_mobiel == 1)
    contacts = db.list_all(search=q, minder_mobiel_only=minder_mobiel_bool)

    # Bereken statistieken voor het KPI banner
    all_contacts = db.list_all()
    total_count = len(all_contacts)
    with_emergency_count = sum(
        1 for c in all_contacts
        if c.noodcontact_1_naam or c.noodcontact_1_telefoon or c.noodcontact_1_email
        or c.noodcontact_2_naam or c.noodcontact_2_telefoon or c.noodcontact_2_email
    )
    minder_mobiel_count = sum(1 for c in all_contacts if c.minder_mobiel)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "user": auth.get_current_user(request),
            "contacts": contacts,
            "search_query": q,
            "minder_mobiel_only": minder_mobiel_bool,
            "total_count": total_count,
            "with_emergency_count": with_emergency_count,
            "minder_mobiel_count": minder_mobiel_count,
            "was_reset": bool(reset == 1)
        }
    )


@app.post("/contacten/reset")
def reset_database_action():
    """Wist alle contacten in de database zodat de gebruiker vanaf nul kan beginnen."""
    db = get_db()
    db.reset_all()
    return RedirectResponse(url="/contacten?reset=1", status_code=303)


@app.get("/contacten/nieuw", response_class=HTMLResponse)
def new_contact_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="contact_form.html",
        context={"request": request, "user": auth.get_current_user(request), "contact": None}
    )


@app.post("/contacten/nieuw")
def create_contact_action(
    index_nummer: str = Form(...),
    bestemming: str = Form("Woning"),
    adres_appartementsrecht: str = Form(...),
    naam: str = Form(...),
    postadres: str = Form(""),
    # Contacten van de eigenaar
    telefoonnummer: str = Form(""),
    telefoonnummer_2: str = Form(""),
    telefoonnummer_3: str = Form(""),
    email: str = Form(""),
    email_2: str = Form(""),
    email_3: str = Form(""),
    # Aparte noodcontacten
    noodcontact_1_naam: str = Form(""),
    noodcontact_1_telefoon: str = Form(""),
    noodcontact_1_email: str = Form(""),
    noodcontact_2_naam: str = Form(""),
    noodcontact_2_telefoon: str = Form(""),
    noodcontact_2_email: str = Form(""),
    # Huismeester velden
    etage: str = Form(""),
    minder_mobiel: Optional[int] = Form(None),
    huisdieren: str = Form(""),
    intercom_naam: str = Form(""),
    notities: str = Form("")
):
    db = get_db()

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
        noodcontact_1_naam=noodcontact_1_naam,
        noodcontact_1_telefoon=noodcontact_1_telefoon,
        noodcontact_1_email=noodcontact_1_email,
        noodcontact_2_naam=noodcontact_2_naam,
        noodcontact_2_telefoon=noodcontact_2_telefoon,
        noodcontact_2_email=noodcontact_2_email,
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
        context={"user": auth.get_current_user(request), "contact": contact}
    )


@app.post("/contacten/{contact_id}")
def update_contact_action(
    contact_id: str,
    index_nummer: str = Form(...),
    bestemming: str = Form("Woning"),
    adres_appartementsrecht: str = Form(...),
    naam: str = Form(...),
    postadres: str = Form(""),
    # Contacten van de eigenaar
    telefoonnummer: str = Form(""),
    telefoonnummer_2: str = Form(""),
    telefoonnummer_3: str = Form(""),
    email: str = Form(""),
    email_2: str = Form(""),
    email_3: str = Form(""),
    # Aparte noodcontacten
    noodcontact_1_naam: str = Form(""),
    noodcontact_1_telefoon: str = Form(""),
    noodcontact_1_email: str = Form(""),
    noodcontact_2_naam: str = Form(""),
    noodcontact_2_telefoon: str = Form(""),
    noodcontact_2_email: str = Form(""),
    # Huismeester velden
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
        noodcontact_1_naam=noodcontact_1_naam,
        noodcontact_1_telefoon=noodcontact_1_telefoon,
        noodcontact_1_email=noodcontact_1_email,
        noodcontact_2_naam=noodcontact_2_naam,
        noodcontact_2_telefoon=noodcontact_2_telefoon,
        noodcontact_2_email=noodcontact_2_email,
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
        context={"user": auth.get_current_user(request), "results": None}
    )


@app.post("/importeren", response_class=HTMLResponse)
async def handle_csv_upload(request: Request, file: UploadFile = File(...)):
    db = get_db()
    content = await file.read()
    results = import_cooperatie_csv(content, db)
    return templates.TemplateResponse(
        request=request,
        name="import.html",
        context={"user": auth.get_current_user(request), "results": results}
    )


@app.get("/sample-csv")
def download_sample_csv():
    sample_path = BASE_DIR / "sample_rebo_cooperatie.csv"
    return FileResponse(
        path=str(sample_path),
        filename="rebo_cooperatie_voorbeeld.csv",
        media_type="text/csv"
    )


# --- Mailinglijsten Beheer (Handmatig & Google Workspace) ---
@app.get("/mailinglijsten", response_class=HTMLResponse)
def page_mailinglijsten(request: Request, msg: Optional[str] = None, error: Optional[str] = None):
    db = get_db()
    lijsten = db.list_mailinglijsten()
    return templates.TemplateResponse(
        request=request,
        name="mailinglijsten.html",
        context={
            "user": auth.get_current_user(request),
            "mailinglijsten": lijsten,
            "msg": msg,
            "error": error
        }
    )


@app.post("/mailinglijsten/nieuw")
def action_create_mailinglijst(
    naam: str = Form(...),
    email_prefix: str = Form(...),
    omschrijving: Optional[str] = Form(default="")
):
    clean_prefix = email_prefix.strip().lower().replace("@denheuvelvelp.nl", "")
    full_email = f"{clean_prefix}@denheuvelvelp.nl"
    db = get_db()
    ml = db.create_mailinglijst(MailinglijstCreate(
        naam=naam.strip(),
        email_groep=full_email,
        omschrijving=omschrijving.strip() if omschrijving else ""
    ))
    return RedirectResponse(
        url=f"/mailinglijsten/{ml.id}/leden?msg=Mailinglijst+'{urllib.parse.quote(ml.naam)}'+aangemaakt.",
        status_code=303
    )


@app.get("/mailinglijsten/{ml_id}/leden", response_class=HTMLResponse)
def page_mailinglijst_leden(
    request: Request,
    ml_id: str,
    msg: Optional[str] = None,
    error: Optional[str] = None
):
    db = get_db()
    ml = db.get_mailinglijst(ml_id)
    if not ml:
        raise HTTPException(status_code=404, detail="Mailinglijst niet gevonden")

    alle_contacten = db.list_all()
    leden_set = set(ml.leden)
    huidige_leden = [c for c in alle_contacten if c.id in leden_set]

    return templates.TemplateResponse(
        request=request,
        name="mailinglijst_leden.html",
        context={
            "user": auth.get_current_user(request),
            "mailinglijst": ml,
            "huidige_leden": huidige_leden,
            "alle_contacten": alle_contacten,
            "msg": msg,
            "error": error
        }
    )


@app.post("/mailinglijsten/{ml_id}/leden/toevoegen")
def action_add_members_to_mailinglijst(
    ml_id: str,
    contact_ids: List[str] = Form(default=[])
):
    db = get_db()
    ml = db.get_mailinglijst(ml_id)
    if not ml:
        raise HTTPException(status_code=404, detail="Mailinglijst niet gevonden")

    if not contact_ids:
        return RedirectResponse(
            url=f"/mailinglijsten/{ml_id}/leden?error=Geen+bewoners+geselecteerd",
            status_code=303
        )

    db.add_members_to_mailinglijst(ml_id, contact_ids)
    return RedirectResponse(
        url=f"/mailinglijsten/{ml_id}/leden?msg={len(contact_ids)}+bewoner(s)+toegevoegd+aan+lijst",
        status_code=303
    )


@app.post("/mailinglijsten/{ml_id}/leden/verwijderen")
def action_remove_member_from_mailinglijst(
    ml_id: str,
    contact_id: str = Form(...)
):
    db = get_db()
    ml = db.get_mailinglijst(ml_id)
    if not ml:
        raise HTTPException(status_code=404, detail="Mailinglijst niet gevonden")

    db.remove_member_from_mailinglijst(ml_id, contact_id)
    return RedirectResponse(
        url=f"/mailinglijsten/{ml_id}/leden?msg=Bewoner+verwijderd+uit+lijst",
        status_code=303
    )


@app.post("/mailinglijsten/{ml_id}/sync-google")
def action_sync_mailinglijst_to_google(ml_id: str):
    db = get_db()
    ml = db.get_mailinglijst(ml_id)
    if not ml:
        raise HTTPException(status_code=404, detail="Mailinglijst niet gevonden")

    # Verzamel alle e-mailadressen van de leden
    alle_contacten = db.list_all()
    leden_set = set(ml.leden)
    emails = []
    for c in alle_contacten:
        if c.id in leden_set:
            if c.email:
                emails.append(c.email)
            if c.email_2:
                emails.append(c.email_2)
            if c.email_3:
                emails.append(c.email_3)

    result = workspace_manager.sync_mailinglijst(
        group_email=ml.email_groep,
        group_name=ml.naam,
        description=ml.omschrijving,
        member_emails=emails
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    if result.get("success"):
        status_str = "Gesynchroniseerd" if result.get("mode") == "live" else "Simulatiemodus (Google Workspace)"
        db.update_sync_status(ml_id, status_str, now_iso, ml.email_groep)
        msg_text = urllib.parse.quote(result.get("message", "Synchronisatie geslaagd."))
        return RedirectResponse(url=f"/mailinglijsten/{ml_id}/leden?msg={msg_text}", status_code=303)
    else:
        err_text = urllib.parse.quote(result.get("error", "Fout bij Google synchronisatie."))
        return RedirectResponse(url=f"/mailinglijsten/{ml_id}/leden?error={err_text}", status_code=303)


@app.post("/mailinglijsten/{ml_id}/verwijderen")
def action_delete_mailinglijst(ml_id: str):
    db = get_db()
    db.delete_mailinglijst(ml_id)
    return RedirectResponse(
        url="/mailinglijsten?msg=Mailinglijst+verwijderd",
        status_code=303
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

