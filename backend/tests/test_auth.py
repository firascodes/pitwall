import time
import uuid

import jwt
import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from pitwall.api import auth
from pitwall.api.limits import DailyQuota, RateLimiter
from pitwall.api.main import app
from pitwall.config import get_settings

SUPABASE = "https://pitwall-test.supabase.co"


class FakeAgent:
    async def astream(self, state, config, stream_mode):
        yield "updates", {"composer": {"blocks": [{"type": "text", "text": "Antonelli leads."}]}}


KEY = ec.generate_private_key(ec.SECP256R1())


class FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        return KEY.public_key()


def token(**claims) -> str:
    base = {
        "sub": "user-1",
        "email": "fan@example.com",
        "aud": "authenticated",
        "iss": f"{SUPABASE}/auth/v1",
        "exp": int(time.time()) + 600,
    }
    return jwt.encode(base | claims, KEY, algorithm="ES256")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(get_settings(), "supabase_url", SUPABASE)
    monkeypatch.setattr(auth, "_jwks", lambda url: FakeJWKS())
    app.state.agent = FakeAgent()
    app.state.quota = DailyQuota()
    app.state.limiter = RateLimiter(100)
    return TestClient(app)


def ask(client, headers=None):
    return client.post("/ask", json={"question": "Who leads?"}, headers=headers or {})


def test_a_guest_gets_one_question(client) -> None:
    assert ask(client).status_code == 200
    second = ask(client)
    assert second.status_code == 429
    assert second.json()["detail"]["code"] == "guest_limit"
    assert client.get("/quota").json() == {"auth": True, "signed_in": False, "used": 1, "limit": 1}


def test_a_signed_in_user_has_their_own_quota(client) -> None:
    ask(client)  # the guest question from this IP does not count against the user
    headers = {"authorization": f"Bearer {token()}"}
    assert ask(client, headers).status_code == 200
    got = client.get("/quota", headers=headers).json()
    assert got == {"auth": True, "signed_in": True, "used": 1, "limit": 30}


def test_a_bad_or_expired_token_is_rejected(client) -> None:
    for bad in (
        token(exp=int(time.time()) - 10),
        token(aud="anon"),
        token(iss="https://evil/auth/v1"),
    ):
        assert ask(client, {"authorization": f"Bearer {bad}"}).status_code == 401


async def test_the_quota_upsert_never_goes_over_the_limit() -> None:
    dsn = get_settings().database_url
    try:
        await (await psycopg.AsyncConnection.connect(dsn, connect_timeout=2)).close()
    except psycopg.OperationalError:
        pytest.skip("Postgres is not running (docker compose up -d)")
    quota = DailyQuota(dsn)
    await quota.setup()
    who = f"test:{uuid.uuid4().hex}"
    assert [await quota.take(who, 2) for _ in range(3)] == [True, True, False]
    assert await quota.used(who) == 2
