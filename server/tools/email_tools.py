from __future__ import annotations
import base64
from email.message import EmailMessage
from pathlib import Path
from utils.logger import get_logger

logger = get_logger("email_tools")

_DATA_DIR = Path(__file__).parents[1] / "data"
_CREDS_FILE = _DATA_DIR / "google_credentials.json"
_TOKEN_FILE = _DATA_DIR / "google_token.json"

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

_ERR_NOT_CONFIGURED = (
    "Gmail non configuré, Monsieur. "
    "Allez dans Paramètres → Services → Connecter Gmail, puis suivez les instructions."
)
_ERR_NOT_AUTHED = (
    "Authentification Gmail requise. "
    "Dites 'connecte Gmail' ou allez dans Paramètres → Services → Connecter Gmail."
)


def _is_configured() -> bool:
    return _CREDS_FILE.exists()


def _is_authenticated() -> bool:
    return _TOKEN_FILE.exists()


def _get_service():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError("Dépendances Gmail manquantes — pip install google-auth-oauthlib google-api-python-client")

    if not _CREDS_FILE.exists():
        raise RuntimeError(_ERR_NOT_CONFIGURED)

    creds: Credentials | None = None
    if _TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _TOKEN_FILE.write_text(creds.to_json())
        else:
            raise RuntimeError(_ERR_NOT_AUTHED)

    return build("gmail", "v1", credentials=creds)


def gmail_status() -> str:
    if not _is_configured():
        return "non_configured"
    if not _is_authenticated():
        return "not_authenticated"
    return "connected"


def list_emails(count: int = 5) -> str:
    try:
        service = _get_service()
        result = service.users().messages().list(
            userId="me", labelIds=["INBOX", "UNREAD"], maxResults=min(int(count), 10)
        ).execute()
        messages = result.get("messages", [])
        if not messages:
            return "Aucun email non lu dans la boîte de réception."

        lines = [f"{len(messages)} email(s) non lu(s):"]
        for msg in messages:
            detail = service.users().messages().get(
                userId="me", id=msg["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            lines.append(
                f"• De: {headers.get('From', '?')}\n"
                f"  Sujet: {headers.get('Subject', '?')}\n"
                f"  Date: {headers.get('Date', '?')}"
            )
        return "\n\n".join(lines)
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        logger.error(f"Erreur lecture emails: {e}")
        return f"Erreur Gmail: {e}"


def send_email(to: str, subject: str, body: str) -> str:
    if not to or "@" not in to:
        return "Erreur: adresse email invalide."
    if not subject.strip():
        return "Erreur: sujet manquant."
    if not body.strip():
        return "Erreur: corps du message manquant."
    try:
        service = _get_service()
        msg = EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email envoyé à {to} — Sujet: {subject}"
    except RuntimeError as e:
        return str(e)
    except Exception as e:
        logger.error(f"Erreur envoi email: {e}")
        return f"Erreur envoi Gmail: {e}"
