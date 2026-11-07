"""Regression tests for explicit configuration and fail-closed HTTP mode."""
import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from mcp_web_engine.config import Settings


def test_cwd_dotenv_does_not_enable_fallback(tmp_path, monkeypatch):
    (tmp_path / '.env').write_text('ALLOW_DDG_FALLBACK=true\nAPI_KEY=unexpected-key\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('ALLOW_DDG_FALLBACK', raising=False)
    monkeypatch.delenv('API_KEY', raising=False)
    settings = Settings()
    assert settings.ALLOW_DDG_FALLBACK is False
    assert settings.API_KEY == ''


def test_no_builtin_http_secret():
    settings = Settings(_env_file=None, API_KEY='')
    assert settings.API_KEY == ''


def test_http_defaults_to_loopback(monkeypatch):
    monkeypatch.delenv('HOST', raising=False)
    assert Settings(_env_file=None).HOST == '127.0.0.1'


@pytest.mark.parametrize('field,value', [('RATE_LIMIT_PER_MINUTE', 0), ('MAX_PAYLOAD_BYTES', -1), ('DEFAULT_TIMEOUT_SEC', 0), ('PORT', 70000)])
def test_invalid_resource_limits_rejected(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_cli_serve_refuses_missing_api_key(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in ('API_KEY', 'MCP_WEB_ENGINE_ENV_FILE')}
    env['PORT'] = '5050'
    result = subprocess.run([sys.executable, '-m', 'mcp_web_engine.main', '--serve'], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'API_KEY' in result.stderr


def test_explicit_env_file_loaded_only_when_selected(tmp_path):
    env_file = tmp_path / 'chosen.env'
    env_file.write_text('ALLOW_DDG_FALLBACK=true\nUNRELATED_VAR=ignored\n')
    env = {**os.environ, 'MCP_WEB_ENGINE_ENV_FILE': str(env_file)}
    env.pop('ALLOW_DDG_FALLBACK', None)
    result = subprocess.run([sys.executable, '-c', 'from mcp_web_engine.config import settings; print(settings.ALLOW_DDG_FALLBACK)'], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'True'
