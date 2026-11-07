"""Offline packaging contracts; never launch network tools on import."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_npm_ships_canonical_python_package():
    package = json.loads((ROOT / "package.json").read_text())
    assert package["version"] == "1.2.1"
    assert {"src/mcp_web_engine/*.py", "pyproject.toml"} <= set(package["files"])
    assert "*.py" not in package["files"]


def test_dependencies_have_one_source():
    assert (ROOT / "requirements.txt").read_text().strip() == "-e ."


def test_docker_installs_package_and_serves_nonroot():
    docker = (ROOT / "Dockerfile").read_text()
    assert 'CMD ["mcp-web-engine", "--serve"]' in docker
    assert "USER appuser" in docker
    assert "EXPOSE 5050" in docker
    assert "pip install --no-cache-dir ." in docker
    assert "COPY . ." not in docker


def test_compose_has_no_embedded_secret_or_public_binding():
    compose = (ROOT / "docker-compose.yml").read_text()
    assert '127.0.0.1:5050:5050' in compose
    assert '${API_KEY:?' in compose
    assert 'sk_mcp' not in compose
    assert 'container_name:' not in compose


def test_build_context_excludes_secrets_and_caches():
    ignore = (ROOT / ".dockerignore").read_text().splitlines()
    assert {".env", ".env.*", "**/__pycache__", ".git", ".venv", "beta_keys.json", "*.pem", "*.key"} <= set(ignore)


def test_compose_preserves_quota_state_across_container_replacement():
    compose = (ROOT / "docker-compose.yml").read_text()
    assert 'usage-state:/home/appuser/.local/state/mcp-web-engine' in compose
    assert 'usage-state:' in compose
    assert 'mkdir -p /home/appuser/.local/state/mcp-web-engine' in (ROOT / "Dockerfile").read_text()


def test_docs_do_not_claim_official_future_spec_or_absolute_privacy():
    readme = (ROOT / "README.md").read_text()
    for claim in ["MCP Specification 2026-07-28", "Zero Third-Party Tracking", "No query leaves the host", "0% system contamination"]:
        assert claim not in readme
    assert "MCP_WEB_ENGINE_ENV_FILE" in readme
    assert "SearXNG" in readme
    assert "limitations" in readme.lower()


def test_npm_actual_manifest_excludes_caches_and_root_shims():
    import shutil
    import subprocess

    import pytest
    if not shutil.which("npm"):
        pytest.skip("npm is needed to inspect the actual npm artifact manifest")
    result = subprocess.run(["npm", "pack", "--dry-run", "--json", "--ignore-scripts"], cwd=ROOT, text=True, capture_output=True, check=True)
    paths = {entry["path"] for entry in json.loads(result.stdout)[0]["files"]}
    assert {"src/mcp_web_engine/main.py", "src/mcp_web_engine/security.py", "pyproject.toml", "bin/cli.js"} <= paths
    assert "main.py" not in paths
    assert not any("__pycache__" in p or p.endswith((".pyc", ".key", ".pem")) or ".env" in p or p.endswith("beta_keys.json") for p in paths)
