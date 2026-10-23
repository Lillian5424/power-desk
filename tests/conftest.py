"""Shared fixtures for every test layer.

Key idea: the suite can run in two modes.
  * Local / CI (default): start our own app server on a free port with a
    throw-away database. Each pytest-xdist worker gets its own server.
  * Against a deployed environment: `pytest --base-url https://staging.example.com`
    and no server is started.
"""

from __future__ import annotations

import datetime as dt
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEST_BUSINESS_DATE = "2026-11-02"  # pinned so date rules are reproducible

USERS = {
    "trader": ("trader1", "trader1pass"),
    "trader2": ("trader2", "trader2pass"),
    "viewer": ("viewer1", "viewer1pass"),
}


# ------------------------------------------------------------ test layering


def pytest_collection_modifyitems(config, items):
    """Tag tests with their layer from the folder they live in (unit / api / e2e)."""
    for item in items:
        parts = Path(str(item.fspath)).relative_to(ROOT / "tests").parts
        if parts and parts[0] in {"unit", "api", "e2e"}:
            item.add_marker(getattr(pytest.mark, parts[0]))


# ------------------------------------------------------------ app server


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_healthy(url: str, proc: subprocess.Popen, log: Path, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"App server exited early:\n{log.read_text()}")
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1) as resp:
                if resp.status == 200:
                    return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"App server not healthy after {timeout}s:\n{log.read_text()}")


@pytest.fixture(scope="session")
def _verify_url():
    """Override pytest-base-url's autouse check so unit tests never start a server."""


@pytest.fixture(scope="session")
def base_url(pytestconfig, tmp_path_factory):
    external = pytestconfig.getoption("base_url", None) or os.getenv("BASE_URL")
    if external:
        yield external.rstrip("/")
        return

    workdir = tmp_path_factory.mktemp("server")
    log = workdir / "server.log"
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "APP_ENV": "test",
        "APP_TODAY": TEST_BUSINESS_DATE,
        "DB_PATH": str(workdir / "test.db"),
        "SECRET_KEY": "test-secret",
    }
    with log.open("w") as fh:
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
            cwd=ROOT,
            env=env,
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
    try:
        _wait_until_healthy(url, proc, log)
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(scope="session")
def server_info(playwright, base_url) -> dict:
    ctx = playwright.request.new_context(base_url=base_url)
    info = ctx.get("/api/health").json()
    ctx.dispose()
    return info


@pytest.fixture(scope="session")
def business_date(server_info) -> dt.date:
    """The server's business date, so tests also work against a real environment."""
    return dt.date.fromisoformat(server_info["today"])


# ------------------------------------------------------------ API clients


@pytest.fixture
def anon_api(playwright, base_url):
    ctx = playwright.request.new_context(base_url=base_url)
    yield ctx
    ctx.dispose()


@pytest.fixture
def api_as(playwright, base_url):
    """Factory: api_as("trader") -> an APIRequestContext already logged in."""
    contexts = []

    def _login(role: str):
        username, password = USERS[role]
        ctx = playwright.request.new_context(base_url=base_url)
        resp = ctx.post("/api/login", data={"username": username, "password": password})
        assert resp.ok, f"login as {role} failed: {resp.status} {resp.text()}"
        contexts.append(ctx)
        return ctx

    yield _login
    for ctx in contexts:
        ctx.dispose()


@pytest.fixture
def trader_api(api_as):
    return api_as("trader")


@pytest.fixture
def viewer_api(api_as):
    return api_as("viewer")


@pytest.fixture
def reset_data(anon_api, server_info):
    """Start each API/E2E test from an empty trade book."""
    if server_info["env"] != "test":
        pytest.skip("Data reset is only available in the test environment")
    assert anon_api.post("/api/test/reset").ok
