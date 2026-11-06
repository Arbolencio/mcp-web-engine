"""Compatibility alias; implementation lives in src/mcp_web_engine/mcp_tools.py."""
import importlib
import sys

_impl = importlib.import_module("mcp_web_engine.mcp_tools")
sys.modules[__name__] = _impl
