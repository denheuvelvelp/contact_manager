import os
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("google_workspace")

# Google Workspace Directory API scopes
SCOPES = [
    "https://www.googleapis.com/auth/admin.directory.group",
    "https://www.googleapis.com/auth/admin.directory.group.member"
]


class GoogleWorkspaceManager:
    """
    Manager voor synchronisatie van handmatig samengestelde mailinglijsten
    naar Google Workspace Groepen (@denheuvelvelp.nl).
    """

    def __init__(self):
        self.credentials_path = os.getenv("GOOGLE_WORKSPACE_CREDENTIALS_PATH")
        self.credentials_json = os.getenv("GOOGLE_WORKSPACE_CREDENTIALS_JSON")
        self.admin_email = os.getenv("GOOGLE_WORKSPACE_ADMIN_EMAIL")
        self.domain = os.getenv("GOOGLE_WORKSPACE_DOMAIN", "denheuvelvelp.nl")

    def is_configured(self) -> bool:
        """Controleert of de Google Workspace Service Account en Admin e-mail zijn ingesteld."""
        has_creds = bool(
            (self.credentials_path and os.path.exists(self.credentials_path))
            or self.credentials_json
        )
        return bool(has_creds and self.admin_email)

    def _get_access_token(self) -> Optional[str]:
        """Haalt een OAuth2 Bearer token op via Service Account impersonation."""
        try:
            from google.oauth2 import service_account
            import google.auth.transport.requests

            if self.credentials_path and os.path.exists(self.credentials_path):
                creds = service_account.Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=SCOPES,
                    subject=self.admin_email
                )
            elif self.credentials_json:
                info = json.loads(self.credentials_json)
                creds = service_account.Credentials.from_service_account_info(
                    info,
                    scopes=SCOPES,
                    subject=self.admin_email
                )
            else:
                return None

            request = google.auth.transport.requests.Request()
            creds.refresh(request)
            return creds.token
        except Exception as e:
            logger.error(f"Fout bij ophalen Google Workspace access token: {e}")
            return None

    def sync_mailinglijst(
        self,
        group_email: str,
        group_name: str,
        description: str,
        member_emails: List[str]
    ) -> Dict[str, Any]:
        """
        Synchroniseert een mailinglijst met een Google Workspace Groep.
        Als credentials ontbreken, wordt een veilige simulatiestatus teruggegeven.
        """
        # Valideer en normaliseer e-mailadres van de groep
        group_email = group_email.strip().lower()
        if not group_email.endswith(f"@{self.domain}"):
            if "@" in group_email:
                prefix = group_email.split("@")[0]
            else:
                prefix = group_email
            group_email = f"{prefix}@{self.domain}"

        # Filter en ontdubbel geldige leden-emails
        valid_members = sorted(list({
            email.strip().lower()
            for email in member_emails
            if email and "@" in email.strip()
        }))

        if not self.is_configured():
            return {
                "success": True,
                "mode": "simulatie",
                "group_email": group_email,
                "group_name": group_name,
                "member_count": len(valid_members),
                "members": valid_members,
                "message": (
                    f"Groep '{group_email}' gesimuleerd gesynchroniseerd ({len(valid_members)} leden). "
                    "Google Workspace Service Account credentials zijn nog niet geconfigureerd in de omgeving."
                )
            }

        # Uitvoering met actieve Google Workspace Directory API
        try:
            import httpx

            token = self._get_access_token()
            if not token:
                return {
                    "success": False,
                    "mode": "live",
                    "group_email": group_email,
                    "member_count": len(valid_members),
                    "error": "Kon geen geldig autorisatietoken verkrijgen bij Google Workspace."
                }

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # 1. Haal de groep op of maak hem aan
            check_url = f"https://admin.googleapis.com/admin/directory/v1/groups/{group_email}"
            resp = httpx.get(check_url, headers=headers, timeout=10.0)

            if resp.status_code == 404:
                # Groep bestaat nog niet, aanmaken
                create_url = "https://admin.googleapis.com/admin/directory/v1/groups"
                create_payload = {
                    "email": group_email,
                    "name": group_name,
                    "description": description or f"Mailinglijst {group_name}"
                }
                create_resp = httpx.post(create_url, headers=headers, json=create_payload, timeout=10.0)
                if create_resp.status_code not in (200, 201):
                    return {
                        "success": False,
                        "mode": "live",
                        "error": f"Fout bij aanmaken groep: {create_resp.text}"
                    }
            elif resp.status_code != 200:
                return {
                    "success": False,
                    "mode": "live",
                    "error": f"Fout bij ophalen groep info: {resp.text}"
                }

            # 2. Haal bestaande groepsleden op
            members_url = f"https://admin.googleapis.com/admin/directory/v1/groups/{group_email}/members"
            existing_members_resp = httpx.get(members_url, headers=headers, timeout=10.0)
            existing_emails = set()
            if existing_members_resp.status_code == 200:
                data = existing_members_resp.json()
                for m in data.get("members", []):
                    if "email" in m:
                        existing_emails.add(m["email"].lower())

            # 3. Voeg ontbrekende leden toe
            added_count = 0
            target_set = set(valid_members)
            for email in target_set:
                if email not in existing_emails:
                    add_payload = {"email": email, "role": "MEMBER"}
                    add_resp = httpx.post(members_url, headers=headers, json=add_payload, timeout=10.0)
                    if add_resp.status_code in (200, 201):
                        added_count += 1

            # 4. Verwijder leden die niet meer geselecteerd zijn
            removed_count = 0
            for email in existing_emails:
                if email not in target_set:
                    del_url = f"https://admin.googleapis.com/admin/directory/v1/groups/{group_email}/members/{email}"
                    del_resp = httpx.delete(del_url, headers=headers, timeout=10.0)
                    if del_resp.status_code in (200, 204):
                        removed_count += 1

            return {
                "success": True,
                "mode": "live",
                "group_email": group_email,
                "member_count": len(valid_members),
                "added": added_count,
                "removed": removed_count,
                "message": f"Succesvol gesynchroniseerd met Google Workspace: {added_count} toegevoegd, {removed_count} verwijderd."
            }

        except Exception as e:
            logger.exception("Fout bij synchronisatie naar Google Workspace")
            return {
                "success": False,
                "mode": "live",
                "error": f"Uitzondering tijdens synchronisatie: {str(e)}"
            }


workspace_manager = GoogleWorkspaceManager()
