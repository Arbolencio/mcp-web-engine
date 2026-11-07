"""Compatibility alias; implementation lives in src/mcp_web_engine/logging_obs.py."""
import importlib
import sys

_impl = importlib.import_module("mcp_web_engine.logging_obs")
sys.modules[__name__] = _impl
