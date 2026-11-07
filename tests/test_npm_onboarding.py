"""Npm discovery and copy/paste onboarding contracts (offline)."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_metadata_describes_protocol_and_real_features():
    package = json.loads((ROOT / 'package.json').read_text())
    assert {'model-context-protocol', 'markdown-extraction', 'self-hosted'} <= set(package['keywords'])
    assert package['homepage'] == 'https://github.com/Arbolencio/mcp-web-engine#readme'
    assert package['bugs']['url'] == 'https://github.com/Arbolencio/mcp-web-engine/issues'


@pytest.mark.parametrize('filename,windows', [('npm-stdio.json', False), ('npm-stdio.windows.json', True)])
def test_shipped_npm_client_configuration(filename, windows):
    package = json.loads((ROOT / 'package.json').read_text())
    config = json.loads((ROOT / 'examples' / filename).read_text())['mcpServers']['mcp-web-engine']
    assert config['command'] == ('cmd' if windows else 'npx')
    assert config['args'] == (['/c', 'npx'] if windows else []) + ['--yes', 'mcp-web-engine@' + package['version']]
    assert config['env'] == {'SEARXNG_URL': 'http://127.0.0.1:8082/search', 'ALLOW_DDG_FALLBACK': 'false'}
    assert 'examples/*.json' in package['files']


def test_readme_npm_example_matches_shipped_configuration():
    readme = (ROOT / 'README.md').read_text()
    examples = [json.loads(block) for block in re.findall(r'```json\n(.*?)\n```', readme, re.S)]
    config = json.loads((ROOT / 'examples/npm-stdio.json').read_text())
    assert config in examples
    assert readme.index('## npm quick start') < readme.index('## Local stdio')
    section = readme.split('## npm quick start', 1)[1].split('## Local stdio', 1)[0]
    assert 'uv' in section and 'Python' in section and 'SearXNG' in section


def test_npm_compatibility_ci_uses_local_artifacts_not_download_loops():
    workflow = (ROOT / '.github/workflows/npm-compatibility.yml').read_text()
    for platform in ('ubuntu-latest', 'windows-latest', 'macos-latest'):
        assert platform in workflow
    assert 'npm pack' in workflow and 'artifact_smoke.py' in workflow
    assert '--ignore-scripts' in workflow
    assert '--prefer-online' not in workflow
