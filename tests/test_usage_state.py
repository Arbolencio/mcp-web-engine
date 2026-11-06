"""Synthetic, isolated persistence and logging regressions; no live credentials."""
import hashlib
import json
import logging
from concurrent.futures import ProcessPoolExecutor

import pytest
from fastapi import HTTPException

from mcp_web_engine import security, state_store
from mcp_web_engine.logging_obs import JSONFormatter, MetricsTracker


def _admit_in_worker(args):
    path, key, rate, quota = args
    try:
        state_store.admit(key, rate, quota=quota, path=path)
        return 1
    except state_store.AdmissionDenied:
        return 0


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_WEB_ENGINE_STATE_DB", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setattr(security, "BETA_KEYS_FILE", str(tmp_path / "keys.json"))
    monkeypatch.setattr(security.settings, "API_KEY", "synthetic-master")
    security.rate_limit_records.clear()


def _write_beta(**changes):
    record = {"status": "active", "limit": 1, "rate_limit": 100,
              "telemetry": {"requests": 0}, **changes}
    with open(security.BETA_KEYS_FILE, "w") as stream:
        json.dump({"synthetic-beta": record}, stream)


def test_processes_cannot_overrun_last_unit(tmp_path):
    path = str(tmp_path / "shared.sqlite3")
    with ProcessPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(_admit_in_worker, [(path, "hashed-id", 1000, 1)] * 12)) == 1
    assert state_store.read_usage("hashed-id", path=path)["admissions"] == 1
    # New worker processes still see the exhausted ledger.
    with ProcessPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(_admit_in_worker, [(path, "hashed-id", 1000, 1)] * 4)) == 0


def test_master_rate_shared_across_processes(tmp_path):
    path = str(tmp_path / "master.sqlite3")
    with ProcessPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(_admit_in_worker, [(path, "master-id", 3, None)] * 12)) == 3
    assert state_store.read_usage("master-id", path=path)["admissions"] == 3


def test_clock_rollback_does_not_reset_rate_window():
    state_store.admit("clock-id", 1, now=100)
    with pytest.raises(state_store.AdmissionDenied):
        state_store.admit("clock-id", 1, now=50)
    state_store.admit("clock-id", 1, now=161)
    assert state_store.read_usage("clock-id")["admissions"] == 2


def test_quota_survives_new_connection_and_memory_reset():
    _write_beta()
    security.check_rate_limit("synthetic-beta")
    security.rate_limit_records.clear()
    assert not security.is_beta_key_valid("synthetic-beta")
    with pytest.raises(HTTPException) as exc:
        security.check_rate_limit("synthetic-beta")
    assert exc.value.detail["error"] == "BETA_QUOTA_EXCEEDED"


def test_telemetry_never_rewrites_revocation_or_double_counts_admission():
    _write_beta(limit=2)
    security.check_rate_limit("synthetic-beta")
    _write_beta(status="revoked", limit=2)
    before = open(security.BETA_KEYS_FILE, "rb").read()
    tracker = MetricsTracker()
    tracker.record("fetch_url", 10, False, api_key="synthetic-beta")
    assert open(security.BETA_KEYS_FILE, "rb").read() == before
    assert not security.is_beta_key_valid("synthetic-beta")
    usage = state_store.read_usage(hashlib.sha256(b"synthetic-beta").hexdigest())
    assert usage["admissions"] == 1
    assert usage["requests"] == usage["errors"] == usage["fetch_url"] == 1
    telemetry = tracker.get_beta_telemetry("synthetic-beta")
    assert telemetry["admissions"] == telemetry["requests"] == 1
    assert telemetry["tool_requests"] == telemetry["fetch_url"] == 1
    assert telemetry["avg_latency_ms"] == 10


@pytest.mark.parametrize("telemetry", [None, [], "bad", {"requests": "0"}, {"requests": True}, {"requests": -1}])
def test_malformed_legacy_telemetry_fails_closed(telemetry):
    _write_beta(telemetry=telemetry)
    assert not security.is_beta_key_valid("synthetic-beta")
    with pytest.raises(HTTPException):
        security.check_rate_limit("synthetic-beta")


def test_corrupt_state_fails_closed(monkeypatch, tmp_path):
    path = tmp_path / "broken.sqlite3"
    path.write_text("not a database")
    monkeypatch.setenv("MCP_WEB_ENGINE_STATE_DB", str(path))
    with pytest.raises(HTTPException) as exc:
        security.check_rate_limit("synthetic-master")
    assert exc.value.status_code == 503


def test_log_message_and_nested_fields_do_not_leak_secrets():
    secret_url = "https://alice:private-password@example.test/a?token=private-query"
    record = logging.LogRecord("test", logging.ERROR, __file__, 1,
        "failed %s synthetic-master Bearer unknown-token sk_mcp_beta_abcdef", (secret_url,), None)
    record.extra_data = {"outer": [{"url": secret_url, "note": "synthetic-master",
                                   "authorization": "unknown-token"}],
                         "password": "hidden", "safe": "completed"}
    output = JSONFormatter().format(record)
    for secret in (secret_url, "private-password", "private-query", "synthetic-master",
                   "unknown-token", "sk_mcp_beta_abcdef", "hidden"):
        assert secret not in output
    assert json.loads(output)["extra"]["safe"] == "completed"


def test_manage_cli_uses_explicit_state_path(monkeypatch, tmp_path):
    from pathlib import Path
    path = tmp_path / "operator" / "keys.json"
    monkeypatch.setenv("MCP_WEB_ENGINE_BETA_KEYS_FILE", str(path))
    import importlib

    import mcp_web_engine.manage_beta_keys as manager
    importlib.reload(manager)
    assert str(manager.KEYS_FILE) == str(path)
    manager.save_keys({"synthetic-beta": {"id": "Beta_001", "status": "active"}})
    assert path.stat().st_mode & 0o777 == 0o600
    manager.revoke_key_by_id("Beta_001")
    assert json.loads(path.read_text())["synthetic-beta"]["status"] == "revoked"
    root_path = Path(__file__).parents[1] / "manage_beta_keys.py"
    spec = importlib.util.spec_from_file_location("synthetic_root_manager", root_path)
    root_manager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(root_manager)
    assert str(root_manager.KEYS_FILE) == str(path)


def test_default_paths_are_outside_source(monkeypatch, tmp_path):
    monkeypatch.delenv("MCP_WEB_ENGINE_STATE_DB", raising=False)
    monkeypatch.delenv("MCP_WEB_ENGINE_BETA_KEYS_FILE", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert state_store.state_db_path() == tmp_path / "mcp-web-engine" / "usage.sqlite3"
    assert state_store.beta_keys_path() == tmp_path / "mcp-web-engine" / "beta_keys.json"
