"""Secret-safe JSON logs and separate durable tool telemetry."""
import hashlib
import json
import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from . import state_store
from .config import settings


class JSONFormatter(logging.Formatter):
    _sensitive_key = re.compile(r"key|token|secret|auth|password|cookie|credential", re.I)
    _url = re.compile(r"(?:[a-z][a-z0-9+.-]*://|www\.)[^\s<>\"']+", re.I)
    _credentials = re.compile(
        r"\b(?:Bearer\s+\S+|sk_mcp_beta_[A-Za-z0-9_-]+|"
        r"(?:password|token|secret|api[_-]?key|authorization|cookie)\s*[:=]\s*\S+)", re.I)

    def _text(self, value):
        if not isinstance(value, str):
            return "[REDACTED_OBJECT]"
        if len(value) > 8192:
            return "[TRUNCATED]"
        master = settings.API_KEY
        if isinstance(master, str) and master:
            value = value.replace(master, "[REDACTED]")
        value = self._url.sub("[REDACTED_URL]", value)
        value = self._credentials.sub("[REDACTED]", value)
        # Bound log size and remove terminal/control injection.
        return "".join(c if ord(c) >= 32 and ord(c) != 127 else " " for c in value[:4096])

    def format(self, record):
        try:
            if record.exc_info:
                message = "Operation failed"
            elif not isinstance(record.msg, str):
                message = "[REDACTED_OBJECT]"
            elif len(record.msg) > 8192 or re.search(
                r"%(?:\([^)]*\))?[-+#0 .\d]*(?:\*|\d{5})", record.msg
            ):
                message = "[TRUNCATED]"
            else:
                args = record.args.values() if isinstance(record.args, dict) else (record.args or ())
                if len(args) > 100:
                    message = "[TRUNCATED]"
                elif any(type(v) not in (str, int, float, bool, type(None)) for v in args):
                    message = "[REDACTED_OBJECT]"
                elif any(isinstance(v, str) and len(v) > 8192 for v in args):
                    message = "[TRUNCATED]"
                else:
                    message = self._text(record.getMessage())
        except Exception:
            message = "Unformattable log message"
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": self._text(record.module),
            "message": message,
        }
        if hasattr(record, "extra_data"):
            log_obj["extra"] = self.sanitize_data(record.extra_data)
        return json.dumps(log_obj, allow_nan=False)

    def sanitize_data(self, data, _depth=0, _budget=None):
        if _budget is None:
            _budget = [200]
        _budget[0] -= 1
        if _depth >= 8 or _budget[0] < 0:
            return "[TRUNCATED]"
        if isinstance(data, dict):
            from itertools import islice
            result = {}
            for k, v in islice(data.items(), 100):
                if _budget[0] <= 0:
                    break
                key = self._text(k)
                result[key] = "REDACTED" if self._sensitive_key.search(key) else self.sanitize_data(v, _depth + 1, _budget)
            return result
        if isinstance(data, (list, tuple)):
            result = []
            for v in data[:100]:
                if _budget[0] <= 0:
                    break
                result.append(self.sanitize_data(v, _depth + 1, _budget))
            return result
        if data is None or type(data) in (bool, int):
            return data
        if isinstance(data, str):
            return self._text(data)
        # No repr/str of arbitrary exceptions or objects: may contain credentials.
        if isinstance(data, float):
            import math
            return data if math.isfinite(data) else None
        return "[REDACTED_OBJECT]"


logger = logging.getLogger("mcp_web_engine")
logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
if not any(isinstance(h.formatter, JSONFormatter) for h in logger.handlers):
    logger.addHandler(handler)
logger.propagate = False


class MetricsTracker:
    """Bounded process summary; per-key tool counters persist independently.

    Call record once per tool completion, and check_rate_limit once per HTTP
    admission. Telemetry requests are tool calls, never the admission quota.
    """
    def __init__(self):
        self.total_requests = 0
        self.total_errors = 0
        self.tool_calls = {"web_search": 0, "fetch_url": 0, "extract_markdown": 0}
        self.total_units_consumed = 0
        self.latencies_ms = []
        self._lock = threading.Lock()

    def record(self, tool_name: str, latency_ms: float, success: bool, units: int = 1, api_key: Optional[str] = None):
        with self._lock:
            self.total_requests += 1
            if tool_name in self.tool_calls:
                self.tool_calls[tool_name] += 1
            self.total_errors += int(not success)
            self.total_units_consumed += units
            self.latencies_ms.append(latency_ms)
            if len(self.latencies_ms) > 1000:
                del self.latencies_ms[:-1000]
        if api_key:
            self.update_beta_telemetry(api_key, tool_name, latency_ms, success, units)

    def update_beta_telemetry(self, api_key: str, tool_name: str, latency_ms: float, success: bool, units: int = 1):
        """Compatibility name; now records any authenticated key without JSON IO."""
        try:
            state_store.record_telemetry(hashlib.sha256(api_key.encode("utf-8")).hexdigest(),
                                         tool_name, latency_ms, success, units)
        except (state_store.StateUnavailable, state_store.AdmissionDenied, ValueError):
            logger.error("Telemetry persistence failed")

    def get_beta_telemetry(self, api_key: str):
        """Durable per-key dashboard, no credential IO.

        requests/admissions are HTTP admissions; tool_requests counts completed
        tool calls (possibly several per HTTP batch). Raises StateUnavailable
        rather than falsely returning zero if the state database cannot be read.
        """
        usage = state_store.read_usage(hashlib.sha256(api_key.encode("utf-8")).hexdigest())
        tools = usage.get("requests", 0)
        return {
            "requests": usage.get("admissions", 0),
            "admissions": usage.get("admissions", 0),
            "tool_requests": tools,
            "errors": usage.get("errors", 0),
            "web_search": usage.get("web_search", 0),
            "fetch_url": usage.get("fetch_url", 0),
            "extract_markdown": usage.get("extract_markdown", 0),
            "total_units_consumed": usage.get("units", 0),
            "avg_latency_ms": round(usage.get("latency_total", 0) / tools, 2) if tools else 0.0,
            "last_seen": datetime.fromtimestamp(usage["last_seen"], timezone.utc).isoformat() if usage.get("last_seen") else None,
        }

    def get_summary(self):
        with self._lock:
            return {
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "tool_calls": dict(self.tool_calls),
                "total_units_consumed": self.total_units_consumed,
                "avg_latency_ms": round(sum(self.latencies_ms) / len(self.latencies_ms), 2) if self.latencies_ms else 0.0,
            }


metrics = MetricsTracker()
