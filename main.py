"""Compatibility alias; implementation lives in src/mcp_web_engine/main.py."""
import importlib
import sys

_impl = importlib.import_module("mcp_web_engine.main")
if __name__ == "__main__":
    _impl.cli_entrypoint()
else:
    sys.modules[__name__] = _impl
