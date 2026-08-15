# Contributing to MCP Web Engine

Thank you for helping improve MCP Web Engine!

## Development Guidelines

1. **Fork & Clone:** Clone your fork locally.
2. **Virtual Environment:** Set up Python 3.11+ virtual environment (`python -m venv .venv && source .venv/bin/activate`).
3. **Dependencies:** Install dependencies with `pip install -r requirements.txt`.
4. **Security Rule:** Always ensure all SSRF validations pass (`validate_ssrf_url`).
5. **Run Tests:** Ensure 100% of tests pass before submitting a PR (`pytest tests/test_suite.py`).
