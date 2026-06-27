"""
JWT verification via Supabase SDK.
Calls Supabase's auth server to validate the token — no local JWT secret needed,
no algorithm mismatch possible.
"""

from supabase import create_client
from app.core.config import get_settings

settings = get_settings()


def verify_supabase_token(token: str) -> dict:
    """
    Verify a Supabase JWT by calling supabase.auth.get_user().
    Returns a claims-like dict with sub, email, and role on success.
    Raises ValueError on invalid or expired tokens.
    """
    try:
        client = create_client(settings.supabase_url, settings.supabase_anon_key)
        response = client.auth.get_user(token)
    except Exception as exc:
        raise ValueError(f"Token verification failed: {exc}") from exc

    if not response or not response.user:
        raise ValueError("Invalid or expired token.")

    user = response.user
    return {
        "sub": str(user.id),
        "email": user.email,
        "role": "authenticated",
    }
