"""Compatibility alias; configuration lives in src/mcp_web_engine/config.py."""
import importlib
import sys

sys.modules[__name__] = importlib.import_module("mcp_web_engine.config")