# Contributing to MCP Web Engine

Thank you for helping improve MCP Web Engine!

## Development

Use Python 3.11+ and [uv](https://docs.astral.sh/uv/). From your fork's checkout:

```bash
uv sync --locked --extra test
uv run --locked pytest -q
uv run --with build python -m build
npm pack --dry-run --json --ignore-scripts
```

The pip alternative is `python -m pip install -e '.[test]'` in an activated virtual environment; it resolves version ranges rather than the uv lock. `requirements.txt` installs the editable runtime package only, not the test extra.

Tests are offline by default; do not require a live search backend. Keep test credentials and SQLite databases in disposable directories, never operator stores. Add regressions before fixes and run the full suite, not only `tests/test_suite.py`. Preserve SSRF, redirect, authentication and protocol boundary tests. Node >=18 is needed for npm launcher tests.

Dependency changes belong in `pyproject.toml`; regenerate and review `uv.lock` together. Docker validates that lock and installs its hashed runtime dependency set. Do not commit secrets, local `.env` files, caches or generated distributions.

CI builds wheel, sdist and npm archives, installs wheel/npm artifacts outside the checkout and checks stdio with `tests/artifact_smoke.py`. Include test evidence with your PR; do not publish or bump versions as part of an unrelated fix.
