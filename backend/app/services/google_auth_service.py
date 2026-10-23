"""
Google OAuth token verification service.
Verifies ID tokens issued by Google Sign-In using google-auth library.
"""
import os
from typing import Optional, Dict, Any
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")


def verify_google_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Google ID token and return user info if valid.

    Returns:
        dict with keys: sub (google_id), email, name, picture
        None if token is invalid
    """
    if not GOOGLE_CLIENT_ID:
        raise ValueError("GOOGLE_CLIENT_ID environment variable is not configured.")

    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=10
        )

        if idinfo.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
            return None

        return {
            "google_id": idinfo.get("sub"),
            "email": idinfo.get("email"),
            "name": idinfo.get("name", ""),
            "picture": idinfo.get("picture", ""),
            "email_verified": idinfo.get("email_verified", False),
        }
    except ValueError:
        return None
    except Exception:
        return None
