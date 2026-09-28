"""One-time local helper to authorize the YouTube channel.

Usage:
    python scripts/get_youtube_refresh_token.py client_secret.json

The printed refresh token should be stored as the GitHub Actions secret
YOUTUBE_REFRESH_TOKEN. Never commit client_secret.json or the refresh token.
"""

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python scripts/get_youtube_refresh_token.py client_secret.json"
        )

    client_secrets = Path(sys.argv[1]).expanduser().resolve()
    if not client_secrets.is_file():
        raise SystemExit(f"Client secrets file not found: {client_secrets}")

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets),
        SCOPES,
    )
    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=8086,
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    print("\nAuthorization completed.")
    print("YOUTUBE_CLIENT_ID=" + credentials.client_id)
    print("YOUTUBE_CLIENT_SECRET=" + credentials.client_secret)
    print("YOUTUBE_REFRESH_TOKEN=" + credentials.refresh_token)
    print("\nStore these as GitHub Actions secrets. Do not commit them.")


if __name__ == "__main__":
    main()
