def test_register_returns_token_that_works(register):
    ada = register()
    res = ada.get("/auth/me")
    assert res.status_code == 200
    assert res.json()["email"] == "ada@example.com"


def test_register_normalizes_email_and_rejects_duplicates(client, register):
    register(email="Ada@Example.com")
    res = client.post(
        "/api/auth/register",
        json={"email": "ada@example.com", "name": "Ada 2", "password": "another-pass"},
    )
    assert res.status_code == 409


def test_register_validates_password_length(client):
    res = client.post(
        "/api/auth/register", json={"email": "a@example.com", "name": "A", "password": "short"}
    )
    assert res.status_code == 422


def test_login(client, register):
    register()
    ok = client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": "correct-horse"}
    )
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad = client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": "wrong-horse"}
    )
    assert bad.status_code == 401
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert unknown.status_code == 401


def test_rejects_missing_or_bad_token(client):
    assert client.get("/api/auth/me").status_code == 401
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert res.status_code == 401
