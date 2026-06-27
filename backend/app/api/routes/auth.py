"""
Auth routes.
Authentication itself is handled by Supabase on the frontend (signup/login/OAuth).
These endpoints expose server-side auth utilities: profile info and token validation.
"""

from fastapi import APIRouter, Depends
from app.core.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Return the authenticated user's profile from the JWT payload."""
    return {
        "id": current_user.get("sub"),
        "email": current_user.get("email"),
        "role": current_user.get("role"),
    }
