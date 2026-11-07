"""Validate the real demo recording without making CI network requests."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('recorded_demo', ROOT / 'examples/demo.py')
assert SPEC is not None and SPEC.loader is not None
DEMO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEMO)


def recording():
    return json.loads((ROOT / 'docs/assets/demo-session.json').read_text())


def test_recorded_session_contains_all_three_successful_tools():
    data = recording()
    DEMO.validate(data['responses'])
    assert data['source'] == 'live network execution; not mocked'
    assert data['transport'] == 'stdio'
    assert len(data['requests']) == 6
    for response in data['responses'][2:]:
        content = json.loads(response['result']['content'][0]['text'])
        assert not content.get('error')
        assert content.get('results') or content.get('content') or content.get('markdown')


def test_failed_tool_cannot_be_recorded_as_success():
    data = recording()
    data['responses'][4]['result']['isError'] = True
    with pytest.raises(ValueError, match='Live tool failed'):
        DEMO.validate(data['responses'])


def test_recording_isolates_state_and_does_not_forward_explicit_env_file(monkeypatch):
    monkeypatch.setenv('API_KEY', 'synthetic-secret')
    monkeypatch.setenv('MCP_WEB_ENGINE_ENV_FILE', '/untrusted/dotenv')
    def run(command, **options):
        env = options['env']
        assert 'API_KEY' not in env and 'MCP_WEB_ENGINE_ENV_FILE' not in env
        assert env['ALLOW_DDG_FALLBACK'] == 'false'
        assert Path(env['MCP_WEB_ENGINE_STATE_DB']).parent == Path(options['cwd'])
        assert Path(env['MCP_WEB_ENGINE_BETA_KEYS_FILE']).parent == Path(options['cwd'])
        return SimpleNamespace(returncode=0, stdout=''.join(json.dumps(r) + '\n' for r in recording()['responses']))
    monkeypatch.setattr(DEMO.subprocess, 'run', run)
    assert len(DEMO.record()['responses']) == 5


def test_demo_animation_exists_and_has_gif_header():
    # Duration/frame geometry are additionally checked with ffprobe during creation.
    assert (ROOT / 'docs/assets/demo.gif').read_bytes()[:6] in (b'GIF89a', b'GIF87a')


def test_readme_tools_have_valid_copyable_argument_examples():
    from mcp_web_engine.mcp_tools import ExtractMarkdownInput, FetchUrlInput, WebSearchInput
    text = (ROOT / 'README.md').read_text()
    for tool, schema in [('web_search', WebSearchInput), ('fetch_url', FetchUrlInput), ('extract_markdown', ExtractMarkdownInput)]:
        row = next(line for line in text.splitlines() if line.startswith('| `' + tool + '` |'))
        arguments = json.loads(row.split('|')[-2].strip().strip('`'))
        schema.model_validate(arguments)
    assert '## Use cases' in text
    assert '## License' in text
