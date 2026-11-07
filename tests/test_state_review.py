"""Isolated regression coverage for state/auth/operator/logging review."""
import json
import logging
from concurrent.futures import ProcessPoolExecutor

import pytest

from mcp_web_engine import security, state_store
from mcp_web_engine.logging_obs import JSONFormatter


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_WEB_ENGINE_STATE_DB", str(tmp_path / "state.sqlite3"))
    monkeypatch.setenv("MCP_WEB_ENGINE_BETA_KEYS_FILE", str(tmp_path / "keys.json"))
    monkeypatch.setattr(security, "BETA_KEYS_FILE", str(tmp_path / "keys.json"))


def test_capacity_recovers_without_erasing_quota():
    state_store.admit("old", 1, quota=1, capacity=1, now=100)
    state_store.admit("new", 1, capacity=1, now=161)
    assert state_store.read_usage("old")["admissions"] == 1
    with pytest.raises(state_store.AdmissionDenied) as exc:
        state_store.admit("old", 1, quota=1, capacity=1, now=222)
    assert exc.value.code == "BETA_QUOTA_EXCEEDED"


def test_first_window_starts_at_admission_even_near_epoch():
    state_store.admit("early", 1, now=10)
    with pytest.raises(state_store.AdmissionDenied):
        state_store.admit("early", 1, now=61)


def test_logger_rejects_unbounded_format_width():
    record = logging.LogRecord("test", 20, __file__, 1, "%100000s", ("safe",), None)
    def unsafe_format():
        raise AssertionError("Formatting must not allocate attacker-sized width")
    record.getMessage = unsafe_format
    assert json.loads(JSONFormatter().format(record))["message"] == "[TRUNCATED]"


def test_denial_rolls_back_new_row():
    with pytest.raises(state_store.AdmissionDenied):
        state_store.admit("denied", 1, quota=0)
    assert state_store.read_usage("denied") == {}


def test_deep_auth_json_fails_closed():
    with open(security.BETA_KEYS_FILE, "w") as stream:
        stream.write("[" * 2000 + "0" + "]" * 2000)
    assert security._beta_record("synthetic") is None


def test_surrogate_master_comparison_fails_closed():
    assert not security._secret_matches("\ud800", "synthetic")


def test_logger_has_global_node_budget():
    value = "ordinary"
    for _ in range(5):
        value = [value] * 10
    record = logging.LogRecord("test", 20, __file__, 1, "safe", (), None)
    record.extra_data = value
    assert len(JSONFormatter().format(record)) < 30000


def test_logger_rejects_huge_strings_before_processing():
    assert JSONFormatter()._text("a" * 1000000) == "[TRUNCATED]"


def _revoke(args):
    path, key_id = args
    from mcp_web_engine import manage_beta_keys as manager
    manager.KEYS_FILE = path
    manager.revoke_key_by_id(key_id)


def test_concurrent_revocations_are_not_lost(tmp_path):
    path = tmp_path / "keys.json"
    path.write_text(json.dumps({str(i): {"id": str(i), "status": "active"} for i in range(32)}))
    with ProcessPoolExecutor(max_workers=8) as pool:
        list(pool.map(_revoke, [(str(path), str(i)) for i in range(32)]))
    assert all(info["status"] == "revoked" for info in json.loads(path.read_text()).values())


def test_init_refuses_to_replace_existing_keys(monkeypatch, tmp_path):
    from mcp_web_engine import manage_beta_keys as manager
    path = tmp_path / "keys.json"
    path.write_text('{"synthetic": {"status": "revoked"}}')
    monkeypatch.setattr(manager, "KEYS_FILE", str(path))
    before = path.read_bytes()
    with pytest.raises(RuntimeError):
        manager.generate_20_beta_keys()
    assert path.read_bytes() == before


@pytest.mark.parametrize("raw", ['[]', '{"synthetic": null}', '[' * 2000 + '0' + ']' * 2000, ' ' * (1024 * 1024 + 1)])
def test_manager_rejects_bad_store(monkeypatch, tmp_path, raw):
    from mcp_web_engine import manage_beta_keys as manager
    path = tmp_path / "keys.json"
    path.write_text(raw)
    monkeypatch.setattr(manager, "KEYS_FILE", str(path))
    with pytest.raises(RuntimeError):
        manager.load_keys()
