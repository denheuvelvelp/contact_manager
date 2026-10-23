from pathlib import Path
from typing import Optional, List
import urllib.parse
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import get_vve_db
from .models import (
    VveContactCreate, VveContactUpdate,
    VveMailinglijstCreate
)
from .importer import import_vve_csv
from . import auth
from shared.google_workspace import workspace_manager

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Contactmanager voor Huismeester - Vereniging van Eigenaren (VvE)"
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Statische bestanden (logo's, afbeeldingen, iconen)
static_dir = BASE_DIR / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


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


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def page_vve_dashboard(request: Request):
    """Portaal Dashboard conform het voorgestelde ontwerp."""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": auth.get_current_user(request), "active_page": "dashboard"}
    )


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


# --- VvE Mailinglijsten Beheer (Handmatig & Google Workspace) ---
ADMIN_MAILINGLIST_EMAIL = "alberdao@denheuvelvelp.nl"


def is_mailinglist_admin(user: Optional[dict]) -> bool:
    """Controleert of de ingelogde gebruiker de exclusieve beheerder is (alberdao@denheuvelvelp.nl)."""
    if not user:
        return False
    return user.get("email", "").strip().lower() == ADMIN_MAILINGLIST_EMAIL.lower()


@app.get("/mailinglijsten", response_class=HTMLResponse)
def page_vve_mailinglijsten(request: Request, msg: Optional[str] = None, error: Optional[str] = None):
    db = get_vve_db()
    lijsten = db.list_mailinglijsten()
    user = auth.get_current_user(request)
    can_manage = is_mailinglist_admin(user)
    return templates.TemplateResponse(
        request=request,
        name="mailinglijsten.html",
        context={
            "user": user,
            "can_manage": can_manage,
            "admin_email": ADMIN_MAILINGLIST_EMAIL,
            "mailinglijsten": lijsten,
            "msg": msg,
            "error": error
        }
    )


@app.post("/mailinglijsten/nieuw")
def action_create_vve_mailinglijst(
    request: Request,
    naam: str = Form(...),
    email_prefix: str = Form(...),
    omschrijving: Optional[str] = Form(default="")
):
    user = auth.get_current_user(request)
    if not is_mailinglist_admin(user):
        return RedirectResponse(
            url="/mailinglijsten?error=Alleen+alberdao@denheuvelvelp.nl+is+geautoriseerd+om+nieuwe+mededelingenlijsten+aan+te+maken.",
            status_code=303
        )

    clean_prefix = email_prefix.strip().lower().replace("@denheuvelvelp.nl", "")
    full_email = f"{clean_prefix}@denheuvelvelp.nl"
    db = get_vve_db()
    ml = db.create_mailinglijst(VveMailinglijstCreate(
        naam=naam.strip(),
        email_groep=full_email,
        omschrijving=omschrijving.strip() if omschrijving else ""
    ))
    return RedirectResponse(
        url=f"/mailinglijsten/{ml.id}/leden?msg=VvE+Mailinglijst+'{urllib.parse.quote(ml.naam)}'+aangemaakt.",
        status_code=303
    )


@app.get("/mailinglijsten/{ml_id}/leden", response_class=HTMLResponse)
def page_vve_mailinglijst_leden(
    request: Request,
    ml_id: str,
    msg: Optional[str] = None,
    error: Optional[str] = None
):
    db = get_vve_db()
    ml = db.get_mailinglijst(ml_id)
    if not ml:
        raise HTTPException(status_code=404, detail="Mailinglijst niet gevonden")

    user = auth.get_current_user(request)
    can_manage = is_mailinglist_admin(user)

    alle_contacten = db.list_all()
    leden_set = set(ml.leden)
    huidige_leden = [c for c in alle_contacten if c.id in leden_set]

    return templates.TemplateResponse(
        request=request,
        name="mailinglijst_leden.html",
        context={
            "user": user,
            "can_manage": can_manage,
            "admin_email": ADMIN_MAILINGLIST_EMAIL,
            "mailinglijst": ml,
            "huidige_leden": huidige_leden,
            "alle_contacten": alle_contacten,
            "msg": msg,
            "error": error
        }
    )


@app.post("/mailinglijsten/{ml_id}/leden/toevoegen")
def action_add_members_to_vve_mailinglijst(
    request: Request,
    ml_id: str,
    contact_ids: List[str] = Form(default=[])
):
    user = auth.get_current_user(request)
    if not is_mailinglist_admin(user):
        return RedirectResponse(
            url=f"/mailinglijsten/{ml_id}/leden?error=Alleen+alberdao@denheuvelvelp.nl+mag+leden+toevoegen.",
            status_code=303
        )

    db = get_vve_db()
    ml = db.get_mailinglijst(ml_id)
    if not ml:
        raise HTTPException(status_code=404, detail="Mailinglijst niet gevonden")

    if not contact_ids:
        return RedirectResponse(
            url=f"/mailinglijsten/{ml_id}/leden?error=Geen+leden+geselecteerd",
            status_code=303
        )

    db.add_members_to_mailinglijst(ml_id, contact_ids)
    return RedirectResponse(
        url=f"/mailinglijsten/{ml_id}/leden?msg={len(contact_ids)}+lid/leden+toegevoegd+aan+lijst",
        status_code=303
    )


@app.post("/mailinglijsten/{ml_id}/leden/verwijderen")
def action_remove_member_from_vve_mailinglijst(
    request: Request,
    ml_id: str,
    contact_id: str = Form(...)
):
    user = auth.get_current_user(request)
    if not is_mailinglist_admin(user):
        return RedirectResponse(
            url=f"/mailinglijsten/{ml_id}/leden?error=Alleen+alberdao@denheuvelvelp.nl+mag+leden+verwijderen.",
            status_code=303
        )

    db = get_vve_db()
    ml = db.get_mailinglijst(ml_id)
    if not ml:
        raise HTTPException(status_code=404, detail="Mailinglijst niet gevonden")

    db.remove_member_from_mailinglijst(ml_id, contact_id)
    return RedirectResponse(
        url=f"/mailinglijsten/{ml_id}/leden?msg=Lid+verwijderd+uit+lijst",
        status_code=303
    )


@app.post("/mailinglijsten/{ml_id}/sync-google")
def action_sync_vve_mailinglijst_to_google(request: Request, ml_id: str):
    user = auth.get_current_user(request)
    if not is_mailinglist_admin(user):
        return RedirectResponse(
            url=f"/mailinglijsten/{ml_id}/leden?error=Alleen+alberdao@denheuvelvelp.nl+mag+synchroniseren+naar+Google+Workspace.",
            status_code=303
        )

    db = get_vve_db()
    ml = db.get_mailinglijst(ml_id)
    if not ml:
        raise HTTPException(status_code=404, detail="Mailinglijst niet gevonden")

    # Verzamel alle unieke e-mailadressen van de gekozen leden
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
def action_delete_vve_mailinglijst(request: Request, ml_id: str):
    user = auth.get_current_user(request)
    if not is_mailinglist_admin(user):
        return RedirectResponse(
            url="/mailinglijsten?error=Alleen+alberdao@denheuvelvelp.nl+kan+lijsten+verwijderen.",
            status_code=303
        )
    db = get_vve_db()
    db.delete_mailinglijst(ml_id)
    return RedirectResponse(
        url="/mailinglijsten?msg=Mailinglijst+verwijderd",
        status_code=303
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

