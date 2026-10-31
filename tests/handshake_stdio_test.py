#!/usr/bin/env python3
"""
Handshake re-test: reproduces the exact StdioMcpClient sequence used by TurboLLM
(initialize -> notifications/initialized -> tools/list -> tools/call) against the
stdio transport, line by line, and shows whether every message is answered correctly.

Checks:
  1. `initialize` (protocolVersion 2024-11-05) must NOT return -32601
  2. `notifications/initialized` (no id) must produce NO output at all
  3. `tools/list` must return tool definitions
  4. `tools/call` must execute
"""
import json
import subprocess
import sys
import threading
import queue
import time

import os
# run the installed console script (same entry point uvx resolves)
CMD = [os.path.join(os.path.dirname(sys.executable), "mcp-web-engine")]

MESSAGES = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2024-11-05",
                "capabilities": {"roots": {"listChanged": False}},
                "clientInfo": {"name": "TurboLLM", "version": "handshake-test"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "web_search", "arguments": {"query": "MCP protocol 2026", "limit": 2}}},
]

proc = subprocess.Popen(CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, bufsize=1)
q = queue.Queue()
threading.Thread(target=lambda: [q.put(l) for l in proc.stdout], daemon=True).start()

print("$ uvx mcp-web-engine   (stdio)")
transcript = []
for msg in MESSAGES:
    raw = json.dumps(msg, ensure_ascii=False)
    label = msg.get("method")
    no_id = "id" not in msg
    print(f"\n--> {label}{'   [notification: no id]' if no_id else ''}")
    print(f"    {raw[:150]}")
    proc.stdin.write(raw + "\n")
    proc.stdin.flush()

    if no_id:
        try:
            out = q.get(timeout=2.0)
            print(f"<-- UNEXPECTED REPLY: {out.strip()[:200]}")
            transcript.append((label, "unexpected_reply", out.strip()))
        except queue.Empty:
            print("<-- (no output — correct: notifications must not be answered)")
            transcript.append((label, "no_output", None))
        continue

    try:
        out = q.get(timeout=25.0).strip()
        print(f"<-- {out[:400]}")
        try:
            parsed = json.loads(out)
            err = parsed.get("error")
            if err:
                print(f"    !! error {err.get('code')}: {err.get('message')}")
                transcript.append((label, "error", err))
            else:
                transcript.append((label, "ok", parsed.get("result")))
        except json.JSONDecodeError:
            transcript.append((label, "unparseable", out[:200]))
    except queue.Empty:
        print("<-- TIMEOUT: no reply within 25s")
        transcript.append((label, "timeout", None))

proc.stdin.close()
try:
    proc.wait(timeout=10)
except subprocess.TimeoutExpired:
    proc.kill()
err = proc.stderr.read()
if err.strip():
    print("\n--- stderr ---")
    print(err.strip()[:800])

print("\n=== VEREDICTO ===")
ok = True
for label, status, _ in transcript:
    mark = "PASS" if status in ("ok", "no_output") else "FAIL"
    if mark == "FAIL":
        ok = False
    print(f"  [{mark}] {label:<28} {status}")
print("\nEN TOTAL:", "TODOS LOS PASOS CORRECTOS" if ok else "HAY FALLOS")
sys.exit(0 if ok else 1)
