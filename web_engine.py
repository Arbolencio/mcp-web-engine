"""Compatibility alias; implementation lives in src/mcp_web_engine/web_engine.py."""
import importlib
import sys

_impl = importlib.import_module("mcp_web_engine.web_engine")
sys.modules[__name__] = _impl
