from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from . import config


def get_credentials() -> Credentials:
    """Load cached YouTube OAuth credentials, refreshing or running the
    one-time browser login flow as needed."""
    creds = None
    token_path = Path(config.YT_TOKEN_FILE)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), config.YT_SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            config.YT_CLIENT_SECRETS_FILE, config.YT_SCOPES
        )
        creds = flow.run_local_server(port=0)

    token_path.write_text(creds.to_json())
    return creds
