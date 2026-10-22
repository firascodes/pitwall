"""Who is asking: a Supabase user (verified access token) or a guest (hashed IP)."""

import hashlib
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import HTTPException, Request

from pitwall.api.limits import client_ip
from pitwall.config import get_settings


@dataclass(frozen=True)
class Asker:
    key: str  # quota and thread namespace: "user:<id>" or "ip:<hash>"
    signed_in: bool
    email: str | None = None


@lru_cache
def _jwks(url: str) -> jwt.PyJWKClient:
    # Keys are cached for 10 minutes, like Supabase's own edge cache, so rotation still works
    return jwt.PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json", lifespan=600)


def verify(token: str, supabase_url: str) -> dict:
    """Check an asymmetric (ES256/RS256) Supabase access token against the project's JWKS."""
    key = _jwks(supabase_url).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        key,
        algorithms=["ES256", "RS256"],
        audience="authenticated",
        issuer=f"{supabase_url}/auth/v1",
    )


def asker(request: Request) -> Asker:
    s = get_settings()
    header = request.headers.get("authorization", "")
    if s.supabase_url and header.startswith("Bearer "):
        try:
            claims = verify(header.removeprefix("Bearer "), s.supabase_url.rstrip("/"))
        except jwt.PyJWTError as e:
            raise HTTPException(401, "Your session expired. Sign in again.") from e
        return Asker(f"user:{claims['sub']}", True, claims.get("email"))
    salted = f"{s.ip_salt.get_secret_value()}:{client_ip(request)}".encode()
    return Asker(f"ip:{hashlib.sha256(salted).hexdigest()[:24]}", False)
