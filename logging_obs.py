"""
Structured JSON Logging & Observability Metrics Module
"""
import logging
import json
import time
from datetime import datetime
from config import settings

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

    def record(self, tool_name: str, latency_ms: float, success: bool, units: int = 1):
        self.total_requests += 1
        if tool_name in self.tool_calls:
            self.tool_calls[tool_name] += 1
        if not success:
            self.total_errors += 1
        self.total_units_consumed += units
        self.latencies_ms.append(latency_ms)
        if len(self.latencies_ms) > 1000:
            self.latencies_ms = self.latencies_ms[-1000:]

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
