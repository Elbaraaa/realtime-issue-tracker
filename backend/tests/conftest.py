import os

os.environ.setdefault("BCRYPT_ROUNDS", "4")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import Base, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402


def _make_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return create_engine(url)
    return create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )


@pytest.fixture
def client():
    engine = _make_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


class Api:
    """Small helper that remembers a user's token."""

    def __init__(self, client: TestClient, token: str, user: dict):
        self.client, self.token, self.user = client, token, user

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def get(self, path, **kw):
        return self.client.get(f"/api{path}", headers=self.headers, **kw)

    def post(self, path, json=None):
        return self.client.post(f"/api{path}", json=json, headers=self.headers)

    def patch(self, path, json):
        return self.client.patch(f"/api{path}", json=json, headers=self.headers)

    def delete(self, path):
        return self.client.delete(f"/api{path}", headers=self.headers)


@pytest.fixture
def register(client):
    def _register(email="ada@example.com", name="Ada", password="correct-horse") -> Api:
        res = client.post(
            "/api/auth/register", json={"email": email, "name": name, "password": password}
        )
        assert res.status_code == 201, res.text
        body = res.json()
        return Api(client, body["access_token"], body["user"])

    return _register


@pytest.fixture
def project(register):
    """An owner, a member, and a project they share."""
    owner = register("owner@example.com", "Owner")
    member = register("member@example.com", "Member")
    res = owner.post("/projects", {"key": "WEB", "name": "Website"})
    assert res.status_code == 201, res.text
    proj = res.json()
    assert (
        owner.post(f"/projects/{proj['id']}/members", {"email": member.user["email"]}).status_code
        == 201
    )
    return owner, member, proj
