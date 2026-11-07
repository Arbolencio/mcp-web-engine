"""Offline onboarding documentation contracts; no GUI compatibility claim."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("windows", [False, True])
def test_vscode_configuration_uses_native_schema_and_pinned_launcher(windows):
    filename = "vscode-mcp.windows.json" if windows else "vscode-mcp.json"
    config = json.loads((ROOT / "examples" / filename).read_text())
    assert set(config) == {"servers"}
    server = config["servers"]["mcp-web-engine"]
    assert server["type"] == "stdio"
    assert server["command"] == ("cmd" if windows else "npx")
    assert server["args"] == (["/c", "npx"] if windows else []) + [
        "--yes", "mcp-web-engine@1.2.1"
    ]
    assert server["env"] == {
        "SEARXNG_URL": "http://127.0.0.1:8082/search",
        "ALLOW_DDG_FALLBACK": "false",
    }


def test_readme_adoption_and_demo_scope():
    text = (ROOT / "README.md").read_text()
    for required in (
        "https://www.npmjs.com/package/mcp-web-engine",
        "https://pypi.org/project/mcp-web-engine/",
        "https://opensource.org/license/mit",
        "docs/assets/demo.gif", "examples/demo.py", "30–60",
        "real tool execution", "paced for readability",
        "not a Claude/Cursor UI recording", "not a performance benchmark",
        "Claude Desktop", "Cursor", "VS Code", ".vscode/mcp.json",
        "examples/vscode-mcp.json", "examples/vscode-mcp.windows.json",
        "https://code.visualstudio.com/docs/agent-customization/mcp-servers",
        "https://cursor.com/docs/mcp",
        "https://modelcontextprotocol.io/quickstart/user",
        "python -m venv", "mcp-web-engine==1.2.1",
        "Node 18/22", "no full end-to-end GUI",
        "SQLite", "hashed", "queries", "upstream",
    ):
        assert required in text, required
    assert text.index("## Tools") < text.index("## npm quick start")
    examples = [json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", text, re.S)]
    assert examples[0] == json.loads((ROOT / "examples/npm-stdio.json").read_text())
