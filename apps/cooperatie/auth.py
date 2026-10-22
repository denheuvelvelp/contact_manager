import os
from typing import Optional
from urllib.parse import urlencode
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse

auth_router = APIRouter()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
ALLOWED_DOMAIN = os.getenv("ALLOWED_DOMAIN", "denheuvelvelp.nl").lower().strip()
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "den-heuvel-secret-key-vve-coop-2026")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def get_current_user(request: Request) -> Optional[dict]:
    """Haalt de ingelogde gebruiker op uit de beveiligde sessie."""
    return request.session.get("user")


def require_auth(request: Request):
    """Controleert of de gebruiker is ingelogd; indien niet, stuurt door naar login."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url=f"/login?next={request.url.path}", status_code=303)
    return None


@auth_router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: Optional[str] = "/contacten"):
    # Als de gebruiker al is ingelogd, ga direct door
    if get_current_user(request):
        return RedirectResponse(url=next or "/contacten", status_code=303)

    is_configured = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="nl" class="h-full bg-slate-100">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Inloggen - Coöperatieve Vereniging Portaal</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    </head>
    <body class="h-full flex items-center justify-center p-4 antialiased">
        <div class="max-w-md w-full bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
            <!-- Header Banner -->
            <div class="bg-emerald-800 p-8 text-center text-white">
                <div class="w-16 h-16 bg-emerald-700 rounded-2xl flex items-center justify-center mx-auto mb-3 shadow-inner">
                    <i class="fa-solid fa-building-user text-3xl text-emerald-200"></i>
                </div>
                <h1 class="text-xl font-bold tracking-tight">Huismeester Portaal</h1>
                <p class="text-xs text-emerald-200 mt-1 uppercase font-semibold tracking-wider">
                    Coöperatieve Vereniging
                </p>
            </div>

            <!-- Inhoud -->
            <div class="p-8 space-y-6">
                <div class="text-center space-y-2">
                    <h2 class="text-lg font-bold text-slate-800">Inloggen met Google</h2>
                    <p class="text-xs text-slate-500 leading-relaxed">
                        Toegang tot deze contactmanager is uitsluitend voorbehouden aan geautoriseerde gebruikers met een 
                        <strong class="text-emerald-800 font-bold">@{ALLOWED_DOMAIN}</strong> account.
                    </p>
                </div>

                <div class="space-y-3">
                    <!-- Google Login Knop -->
                    <a href="/auth/google" class="w-full py-3 px-4 bg-white hover:bg-slate-50 text-slate-700 font-semibold text-sm rounded-xl border border-slate-300 shadow-sm flex items-center justify-center space-x-3 transition hover:border-slate-400">
                        <svg class="w-5 h-5" viewBox="0 0 24 24">
                            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
                        </svg>
                        <span>Inloggen met @{ALLOWED_DOMAIN}</span>
                    </a>

                    <!-- Lokale ontwikkel / bypass knop als OAuth client nog niet is ingevoerd -->
                    {f'''
                    <div class="pt-4 border-t border-slate-100 text-center">
                        <span class="inline-block px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 uppercase mb-2">Lokale Ontwikkelmodus</span>
                        <form method="POST" action="/auth/dev-login">
                            <button type="submit" class="w-full py-2 px-3 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition">
                                <i class="fa-solid fa-laptop-code mr-1"></i> Direct inloggen als beheerder (Lokaal)
                            </button>
                        </form>
                    </div>
                    ''' if not is_configured else ''}
                </div>

                <div class="text-center pt-2">
                    <p class="text-[11px] text-slate-400">
                        <i class="fa-solid fa-lock mr-1"></i> Beveiligde Google Workspace koppeling
                    </p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@auth_router.get("/auth/google")
def redirect_to_google(request: Request):
    """Start de Google OAuth login flow."""
    if not GOOGLE_CLIENT_ID:
        # Als er nog geen Google Client ID is ingesteld, geef instructie
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLIENT_ID is nog niet ingesteld in de omgevingsvariabelen."
        )

    # Bepaal redirect URI (werkt op zowel https in Cloud Run als http lokaal)
    redirect_uri = str(request.url_for("google_callback"))
    if "http://" in redirect_uri and "run.app" in redirect_uri:
        redirect_uri = redirect_uri.replace("http://", "https://")

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "hd": ALLOWED_DOMAIN,  # Verplicht Google login tot het denheuvelvelp.nl domein!
        "prompt": "select_account"
    }
    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=url, status_code=303)


@auth_router.get("/auth/callback")
async def google_callback(request: Request, code: Optional[str] = None, error: Optional[str] = None):
    """Verwerkt het antwoord van Google OAuth."""
    if error:
        raise HTTPException(status_code=400, detail=f"Google inlogfout: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Geen autorisatiecode ontvangen van Google.")

    redirect_uri = str(request.url_for("google_callback"))
    if "http://" in redirect_uri and "run.app" in redirect_uri:
        redirect_uri = redirect_uri.replace("http://", "https://")

    # Wissel authorization code in voor tokens
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }

    async with httpx.AsyncClient() as client:
        token_res = await client.post(GOOGLE_TOKEN_URL, data=token_data)
        if token_res.status_code != 200:
            raise HTTPException(status_code=400, detail="Kon Google inlogtokens niet verifiëren.")

        tokens = token_res.json()
        access_token = tokens.get("access_token")

        # Haal profielinformatie op
        headers = {"Authorization": f"Bearer {access_token}"}
        userinfo_res = await client.get(GOOGLE_USERINFO_URL, headers=headers)
        if userinfo_res.status_code != 200:
            raise HTTPException(status_code=400, detail="Kon gebruikersprofiel niet ophalen bij Google.")

        userinfo = userinfo_res.json()

    email = userinfo.get("email", "").lower().strip()
    name = userinfo.get("name", email)
    picture = userinfo.get("picture", "")

    # STRIKTE CONTROLE OP DOMEIN: alleen @denheuvelvelp.nl
    if not email.endswith(f"@{ALLOWED_DOMAIN}"):
        html_denied = f"""
        <!DOCTYPE html>
        <html lang="nl" class="h-full bg-slate-100">
        <head>
            <meta charset="UTF-8"><title>Toegang Geweigerd</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
        </head>
        <body class="h-full flex items-center justify-center p-4">
            <div class="max-w-md w-full bg-white p-8 rounded-2xl shadow-xl border border-red-200 text-center space-y-4">
                <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto text-red-600 text-2xl">
                    <i class="fa-solid fa-user-xmark"></i>
                </div>
                <h1 class="text-xl font-bold text-slate-800">Toegang Geweigerd</h1>
                <p class="text-sm text-slate-600">
                    Je bent ingelogd met het account <strong>{email}</strong>.
                </p>
                <div class="p-3 bg-red-50 text-red-800 text-xs rounded-lg border border-red-200">
                    Alleen accounts die eindigen op <strong>@{ALLOWED_DOMAIN}</strong> hebben toegang tot deze VvE/Coöperatie gegevens.
                </div>
                <div class="pt-4">
                    <a href="/login" class="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-semibold transition">
                        Opnieuw proberen met ander account
                    </a>
                </div>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_denied, status_code=403)

    # Toegang goedgekeurd: sla sessie op
    request.session["user"] = {
        "email": email,
        "name": name,
        "picture": picture
    }

    return RedirectResponse(url="/contacten", status_code=303)


@auth_router.post("/auth/dev-login")
def dev_login_action(request: Request):
    """Ontwikkel-inlog voor lokaal testen zolang Google Client ID nog niet is geconfigureerd."""
    request.session["user"] = {
        "email": f"huismeester@{ALLOWED_DOMAIN}",
        "name": "Huismeester (Lokaal Beheerder)",
        "picture": ""
    }
    return RedirectResponse(url="/contacten", status_code=303)


@auth_router.get("/logout")
def logout_action(request: Request):
    """Logt de gebruiker uit en wist de sessie."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
