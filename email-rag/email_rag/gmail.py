"""Explicit, read-only Gmail synchronization; inference remains entirely local."""
import base64
import json
import os
from pathlib import Path
from urllib.parse import quote

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def connect(credentials_path, token_path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    path = Path(token_path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    creds = Credentials.from_authorized_user_file(str(path), SCOPES) if path.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as out:
            out.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds, cache_discovery=False)


def messages(service, expected_account, query='in:anywhere -in:spam -in:trash', limit=100):
    actual = service.users().getProfile(userId='me').execute(num_retries=3)['emailAddress']
    if actual.casefold() != expected_account.casefold():
        raise ValueError('Authenticated Gmail account does not match --account; choose the correct OAuth account')
    token = None
    count = 0
    while count < limit:
        page = service.users().messages().list(userId='me', q=query, maxResults=min(100, limit-count),
                                                pageToken=token).execute(num_retries=3)
        for item in page.get('messages', []):
            data = service.users().messages().get(userId='me', id=item['id'], format='raw').execute(num_retries=3)
            encoded = data['raw']
            raw = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))
            link = 'https://mail.google.com/mail/u/?authuser=' + quote(actual, safe='') + '#all/' + data['threadId']
            yield raw, 'gmail:' + actual.casefold() + ':' + item['id'], link
            count += 1
        token = page.get('nextPageToken')
        if not token:
            break
