#!/usr/bin/env python3
"""
Beta Keys & Telemetry Management CLI for MCP Web Engine
Genera 20 keys independientes (Beta_001 .. Beta_020), lista y gestiona telemetría por usuario en beta_keys.json.
"""
import sys
import os
import json
import secrets
import time
import argparse

KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "beta_keys.json")

def load_keys():
    if not os.path.exists(KEYS_FILE):
        return {}
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_keys(keys):
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=2)

def generate_20_beta_keys():
    keys = {}
    generated_summary = []

    for i in range(1, 21):
        beta_id = f"Beta_{i:03d}"
        raw_token = secrets.token_hex(16)
        key_str = f"sk_mcp_beta_{raw_token}"

        keys[key_str] = {
            "id": beta_id,
            "key": key_str,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "limit": 10000,
            "rate_limit": 120,
            "status": "active",
            "telemetry": {
                "requests": 0,
                "web_search": 0,
                "fetch_url": 0,
                "extract_markdown": 0,
                "errors": 0,
                "avg_latency_ms": 0.0,
                "last_seen": None
            }
        }
        generated_summary.append((beta_id, key_str))

    save_keys(keys)
    print(f"✅ Generadas 20 Beta Keys independientes (Beta_001 .. Beta_020) en: {KEYS_FILE}")
    for beta_id, key_str in generated_summary:
        print(f"  - {beta_id:10s}: {key_str}")
    return keys

def list_beta_telemetry():
    keys = load_keys()
    if not keys:
        print("ℹ️ No hay Beta Keys registradas.")
        return

    print("📊 DASHBOARD DE TELEMETRÍA POR USUARIO BETA:")
    print("=" * 85)
    print(f"{'ID Beta':10s} | {'Estado':8s} | {'Reqs':6s} | {'Search':6s} | {'Fetch':6s} | {'Extract':8s} | {'Errors':6s} | {'Last Seen'}")
    print("=" * 85)
    
    total_reqs = 0
    total_errs = 0
    
    for k, info in keys.items():
        t = info.get("telemetry", {})
        reqs = t.get("requests", 0)
        errs = t.get("errors", 0)
        total_reqs += reqs
        total_errs += errs
        
        last_seen = t.get("last_seen") or "Nunca"
        print(f"{info['id']:10s} | {info['status']:8s} | {reqs:6d} | {t.get('web_search', 0):6d} | {t.get('fetch_url', 0):6d} | {t.get('extract_markdown', 0):8d} | {errs:6d} | {last_seen}")

    print("=" * 85)
    print(f"📈 TOTALES: {len(keys)} Usuarios Beta | {total_reqs} Peticiones Totales | {total_errs} Errores Totales")

def revoke_key_by_id(beta_id):
    keys = load_keys()
    found = False
    for k, info in keys.items():
        if info.get("id") == beta_id or k == beta_id:
            info["status"] = "revoked"
            found = True
            print(f"🔴 Beta Key '{beta_id}' revocada con éxito.")
            break
    if found:
        save_keys(keys)
    else:
        print(f"❌ Beta Key '{beta_id}' no encontrada.")

def main():
    parser = argparse.ArgumentParser(description="Beta Keys & Telemetry Manager")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init20", help="Genera las 20 keys de Beta_001 a Beta_020")
    subparsers.add_parser("telemetry", help="Muestra la telemetría por usuario beta")
    
    rev_parser = subparsers.add_parser("revoke", help="Revoca una beta key por ID o token")
    rev_parser.add_argument("--id", type=str, required=True, help="ID Beta (ej: Beta_001)")

    args = parser.parse_args()

    if args.command == "init20":
        generate_20_beta_keys()
    elif args.command == "telemetry":
        list_beta_telemetry()
    elif args.command == "revoke":
        revoke_key_by_id(args.id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
