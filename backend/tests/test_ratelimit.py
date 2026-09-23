from app.ratelimit import FailureLimiter
from app.routers.auth import email_limiter, ip_limiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_limiter_blocks_after_limit_and_recovers_after_window():
    clock = FakeClock()
    limiter = FailureLimiter(limit=3, window_seconds=60, clock=clock)
    for _ in range(3):
        assert limiter.retry_after("k") == 0
        limiter.record_failure("k")
    assert limiter.retry_after("k") == 60
    clock.now += 45
    assert limiter.retry_after("k") == 15
    clock.now += 15
    assert limiter.retry_after("k") == 0


def test_limiter_window_slides():
    clock = FakeClock()
    limiter = FailureLimiter(limit=2, window_seconds=60, clock=clock)
    limiter.record_failure("k")
    clock.now += 30
    limiter.record_failure("k")
    clock.now += 31  # the first failure has aged out
    assert limiter.retry_after("k") == 0


def test_limiter_reset_and_keys_are_independent():
    limiter = FailureLimiter(limit=1, window_seconds=60, clock=FakeClock())
    limiter.record_failure("a")
    assert limiter.retry_after("a") > 0
    assert limiter.retry_after("b") == 0
    limiter.reset("a")
    assert limiter.retry_after("a") == 0


def _login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_locks_an_account_after_repeated_failures(client, register):
    register()
    for _ in range(email_limiter.limit):
        assert _login(client, "ada@example.com", "wrong-password").status_code == 401
    res = _login(client, "ada@example.com", "correct-horse")
    assert res.status_code == 429
    assert int(res.headers["Retry-After"]) > 0


def test_email_lockout_ignores_case(client, register):
    register()
    for _ in range(email_limiter.limit):
        _login(client, "ADA@example.com", "wrong-password")
    assert _login(client, "ada@example.com", "correct-horse").status_code == 429


def test_successful_login_clears_account_failures(client, register):
    register()
    for _ in range(email_limiter.limit - 1):
        _login(client, "ada@example.com", "wrong-password")
    assert _login(client, "ada@example.com", "correct-horse").status_code == 200
    assert _login(client, "ada@example.com", "wrong-password").status_code == 401


def test_login_limits_one_ip_guessing_many_accounts(client, register):
    register()
    for i in range(ip_limiter.limit):
        _login(client, f"user{i}@example.com", "guess")
    assert _login(client, "ada@example.com", "correct-horse").status_code == 429
