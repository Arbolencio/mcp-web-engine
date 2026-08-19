"""
Structured JSON Logging & Observability Metrics Module with Per-Beta-Key Telemetry Tracking
"""
import logging
import json
import time
import os
from typing import Optional
from datetime import datetime
from .config import settings

BETA_KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "beta_keys.json")

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage()
        }
        if hasattr(record, "extra_data"):
            log_obj["extra"] = self.sanitize_data(record.extra_data)
        return json.dumps(log_obj)

    def sanitize_data(self, data):
        if isinstance(data, dict):
            clean = {}
            for k, v in data.items():
                if "key" in k.lower() or "token" in k.lower() or "secret" in k.lower() or "auth" in k.lower():
                    clean[k] = "REDACTED"
                else:
                    clean[k] = self.sanitize_data(v)
            return clean
        elif isinstance(data, list):
            return [self.sanitize_data(i) for i in data]
        return data

logger = logging.getLogger("mcp_web_engine")
logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

# In-memory Metrics Store
class MetricsTracker:
    def __init__(self):
        self.total_requests = 0
        self.total_errors = 0
        self.tool_calls = {"web_search": 0, "fetch_url": 0, "extract_markdown": 0}
        self.total_units_consumed = 0
        self.latencies_ms = []

    def record(self, tool_name: str, latency_ms: float, success: bool, units: int = 1, api_key: Optional[str] = None):
        self.total_requests += 1
        if tool_name in self.tool_calls:
            self.tool_calls[tool_name] += 1
        if not success:
            self.total_errors += 1
        self.total_units_consumed += units
        self.latencies_ms.append(latency_ms)
        if len(self.latencies_ms) > 1000:
            self.latencies_ms = self.latencies_ms[-1000:]

        if api_key and api_key.startswith("sk_mcp_beta_"):
            self.update_beta_telemetry(api_key, tool_name, latency_ms, success)

    def update_beta_telemetry(self, api_key: str, tool_name: str, latency_ms: float, success: bool):
        if not os.path.exists(BETA_KEYS_FILE):
            return
        try:
            with open(BETA_KEYS_FILE, "r", encoding="utf-8") as f:
                keys = json.load(f)

            if api_key in keys:
                t = keys[api_key].setdefault("telemetry", {
                    "requests": 0,
                    "web_search": 0,
                    "fetch_url": 0,
                    "extract_markdown": 0,
                    "errors": 0,
                    "avg_latency_ms": 0.0,
                    "last_seen": None
                })
                t["requests"] += 1
                if tool_name in t:
                    t[tool_name] += 1
                if not success:
                    t["errors"] += 1

                old_avg = t.get("avg_latency_ms", 0.0)
                n = t["requests"]
                t["avg_latency_ms"] = round(((old_avg * (n - 1)) + latency_ms) / n, 2)
                t["last_seen"] = datetime.utcnow().isoformat() + "Z"

                with open(BETA_KEYS_FILE, "w", encoding="utf-8") as f:
                    json.dump(keys, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to update beta telemetry: {str(e)}")

    def get_summary(self):
        avg_lat = round(sum(self.latencies_ms) / len(self.latencies_ms), 2) if self.latencies_ms else 0.0
        return {
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "tool_calls": self.tool_calls,
            "total_units_consumed": self.total_units_consumed,
            "avg_latency_ms": avg_lat
        }

metrics = MetricsTracker()
