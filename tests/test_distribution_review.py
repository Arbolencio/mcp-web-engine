"""Distribution contracts, with no service, credential or network access."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_example_environment_requires_operator_secret_and_loopback():
    content = (ROOT / ".env.example").read_text()
    values = dict(line.split("=", 1) for line in content.splitlines() if line and not line.startswith("#"))
    assert values["API_KEY"] == ""
    assert values["HOST"] == "127.0.0.1"
    assert values["ALLOW_DDG_FALLBACK"] == "false"
    assert "MCP_WEB_ENGINE_ENV_FILE" in content


def test_public_onboarding_has_no_stale_endpoint_or_privacy_guarantee():
    content = (ROOT / "docs/ONBOARDING.md").read_text()
    assert "trycloudflare.com" not in content
    assert "Zero Tracking" not in content
    assert "Endpoint MCP 2026-07-28" not in content
    assert "mcp-web-engine@1.2.1" in content
    assert "SearXNG" in content


def test_contributors_install_test_extra_and_run_full_suite():
    content = (ROOT / "CONTRIBUTING.md").read_text()
    assert "uv sync --locked --extra test" in content
    assert "pytest -q" in content
    assert "pytest tests/test_suite.py" not in content


def test_container_runtime_dependencies_come_from_lock():
    docker = (ROOT / "Dockerfile").read_text()
    assert "uv.lock" in docker
    assert "uv export --locked" in docker
    assert "--no-emit-project" in docker
    assert "--require-hashes" in docker
    assert "pip install --no-cache-dir . --no-deps" in docker
    assert "!uv.lock" in (ROOT / ".dockerignore").read_text().splitlines()


def test_ci_preserves_test_evidence_even_on_failure():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "--junitxml=" in ci
    assert "if: always()" in ci
    assert "test-results-python-${{ matrix.python }}" in ci
    assert "if-no-files-found: error" in ci


@pytest.mark.parametrize("code,signal,error,expected", [
    (7, None, None, 7), (0, None, None, 0),
    (None, "SIGINT", None, 130), (None, "SIGTERM", None, 143),
    (None, "SIGKILL", None, 137), (None, None, "ENOENT", 127),
    (None, None, "EACCES", 1),
])
def test_npm_wrapper_exit_contract(code, signal, error, expected):
    if not shutil.which("node"):
        pytest.skip("Node is required for launcher contract")
    harness = r'''
const fs = require('fs');
const vm = require('vm');
const EventEmitter = require('events');
const child = new EventEmitter();
child.kill = (signal) => { child.forwarded = signal; return true; };
const proc = new EventEmitter();
proc.argv = ['node', 'cli.js', '--serve']; proc.env = {};
const source = fs.readFileSync(process.argv[1], 'utf8');
const scenario = JSON.parse(process.argv[2]);
vm.runInNewContext(source, {
  require: (name) => name === 'node:child_process' ? {spawn: (cmd, args, opts) => {
    if (cmd !== 'uv' || args.at(-1) !== '--serve' || opts.stdio !== 'inherit') throw Error('spawn contract');
    return child;
  }} : require(name),
  __dirname: '/installed/bin', process: proc, console: {error: () => {}}
});
proc.emit('SIGTERM');
if (child.forwarded !== 'SIGTERM') throw Error('signal not forwarded');
if (scenario.error) {
  child.emit('error', Object.assign(new Error('launch failure'), {code: scenario.error}));
} else child.emit('exit', scenario.code, scenario.signal);
console.log(JSON.stringify({exitCode: proc.exitCode}));
'''
    result = subprocess.run(["node", "-e", harness, str(ROOT / "bin/cli.js"), json.dumps({"code": code, "signal": signal, "error": error})], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)["exitCode"] == expected
