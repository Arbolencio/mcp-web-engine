"""Exercise an installed entry point without searching or fetching public data."""
import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def smoke(command, timeout=240):
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "artifact-smoke", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "ping"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "fetch_url", "arguments": {"url": "http://127.0.0.1:1/"}}},
    ]
    env = os.environ.copy()
    for key in ("PYTHONPATH", "MCP_WEB_ENGINE_ENV_FILE", "API_KEY"):
        env.pop(key, None)
    env["ALLOW_DDG_FALLBACK"] = "false"
    with tempfile.TemporaryDirectory(prefix="mcp-artifact-", dir=os.environ.get("TMPDIR")) as cwd:
        env["MCP_WEB_ENGINE_STATE_DB"] = str(Path(cwd, "usage.sqlite3"))
        env["MCP_WEB_ENGINE_BETA_KEYS_FILE"] = str(Path(cwd, "beta_keys.json"))
        # A hostile CWD env file must not be implicitly loaded.
        Path(cwd, ".env").write_text("PORT=not-a-number\n")
        result = subprocess.run(command, input="".join(json.dumps(m) + "\n" for m in messages), text=True, capture_output=True, timeout=timeout, cwd=cwd, env=env)
    if result.stderr:
        print(result.stderr, end="", file=__import__("sys").stderr)
    assert result.returncode == 0, (result.returncode, result.stderr)
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert [r["id"] for r in responses] == [1, 2, 3, 4], responses
    assert responses[0]["result"]["protocolVersion"] == "2025-11-25"
    assert responses[1]["result"] == {}
    assert {t["name"] for t in responses[2]["result"]["tools"]} == {"web_search", "fetch_url", "extract_markdown"}
    blocked = responses[3]["result"]
    assert blocked["isError"] is True, blocked
    text = json.dumps(blocked).lower()
    assert any(term in text for term in ("blocked", "not allowed", "forbidden", "ssrf", "public")), blocked
    print(json.dumps({"status": "ok", "responses": len(responses), "checks": ["initialize", "silent notification", "ping", "tools/list", "blocked loopback", "untrusted cwd env ignored", "stdout JSON only"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("provide an installed entrypoint after --")
    smoke(command)


if __name__ == "__main__":
    main()
