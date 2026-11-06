"""Security helper tests using only synthetic credentials and temporary files."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from mcp_web_engine import security


@pytest.fixture(autouse=True)
def synthetic_auth(monkeypatch, tmp_path):
    monkeypatch.setattr(security.settings, "API_KEY", "synthetic-master-key")
    monkeypatch.setattr(security, "BETA_KEYS_FILE", str(tmp_path / "keys.json"))
    monkeypatch.setenv("MCP_WEB_ENGINE_STATE_DB", str(tmp_path / "usage.sqlite3"))
    security.rate_limit_records.clear()
    yield
    security.rate_limit_records.clear()


def auth(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def write_beta(**fields):
    data = {
        "status": "active",
        "limit": 2,
        "rate_limit": 10,
        "telemetry": {"requests": 0},
        **fields,
    }
    with open(security.BETA_KEYS_FILE, "w", encoding="utf-8") as stream:
        json.dump({"synthetic-beta": data}, stream)


def test_master_only_dependency_rejects_beta():
    write_beta()
    assert security.verify_api_key(auth("synthetic-beta")) == "synthetic-beta"
    with pytest.raises(HTTPException) as exc:
        security.verify_master_api_key(auth("synthetic-beta"))
    assert exc.value.status_code == 403
    assert (
        security.verify_master_api_key(auth("synthetic-master-key"))
        == "synthetic-master-key"
    )


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "revoked"},
        {"expires_at": "2000-01-01T00:00:00Z"},
        {"expires_at": "malformed"},
        {"telemetry": {"requests": 2}},
        {"limit": -1},
        {"rate_limit": 0},
    ],
)
def test_beta_invalid_expired_or_exhausted_fails_closed(fields):
    write_beta(**fields)
    assert not security.is_beta_key_valid("synthetic-beta")
    with pytest.raises(HTTPException):
        security.verify_api_key(auth("synthetic-beta"))


def test_empty_master_is_never_valid(monkeypatch):
    monkeypatch.setattr(security.settings, "API_KEY", "")
    for token in ("", "wrong"):
        with pytest.raises(HTTPException):
            security.verify_api_key(auth(token))


def test_beta_quota_consumed_on_admission_without_telemetry_write():
    write_beta()
    security.check_rate_limit("synthetic-beta")
    security.check_rate_limit("synthetic-beta")
    with pytest.raises(HTTPException) as exc:
        security.check_rate_limit("synthetic-beta")
    assert exc.value.status_code == 429


def test_rate_limit_thread_safety(monkeypatch):
    monkeypatch.setattr(security.settings, "RATE_LIMIT_PER_MINUTE", 3)

    def admit(_):
        try:
            security.check_rate_limit("synthetic-master-key")
            return 1
        except HTTPException as exc:
            assert exc.status_code == 429
            return 0

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(admit, range(30))) == 3


def test_unknown_key_does_not_allocate_rate_bucket():
    for index in range(20):
        with pytest.raises(HTTPException):
            security.check_rate_limit(f"invalid-{index}")
    assert not security.rate_limit_records


def test_rate_bucket_capacity_fails_closed(monkeypatch):
    write_beta(limit=100)
    monkeypatch.setattr(security, "MAX_RATE_BUCKETS", 1)
    security.check_rate_limit("synthetic-beta")
    with pytest.raises(HTTPException) as exc:
        security.check_rate_limit("synthetic-master-key")
    assert exc.value.status_code == 429
    assert len(security.rate_limit_records) == 1


def test_durable_wall_clock_windows_and_beta_totals_survive_idle(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(security.time, "time", lambda: clock[0])
    write_beta(limit=2, rate_limit=1)
    security.check_rate_limit("synthetic-beta")
    with pytest.raises(HTTPException):
        security.check_rate_limit("synthetic-beta")
    clock[0] += 61
    security.check_rate_limit("synthetic-beta")
    clock[0] += 61
    with pytest.raises(HTTPException) as exc:
        security.check_rate_limit("synthetic-beta")
    assert exc.value.detail["error"] == "BETA_QUOTA_EXCEEDED"


def test_revocation_is_reread_on_every_admission():
    write_beta(limit=100)
    security.check_rate_limit("synthetic-beta")
    write_beta(status="revoked", limit=100)
    with pytest.raises(HTTPException) as exc:
        security.check_rate_limit("synthetic-beta")
    assert exc.value.status_code == 401
