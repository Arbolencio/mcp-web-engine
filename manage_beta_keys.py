#!/usr/bin/env python3
"""
Beta Keys Management CLI for MCP Web Engine
Genera, lista y revoca claves Beta de acceso (sk_mcp_beta_...) almacenadas en beta_keys.json.
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

def generate_keys(count=15, name_prefix="beta_user"):
    keys = load_keys()
    generated = []

    for i in range(count):
        raw = secrets.token_hex(16)
        key_str = f"sk_mcp_beta_{raw}"
        keys[key_str] = {
            "name": f"{name_prefix}_{i+1:02d}",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "active",
            "usage_count": 0
        }
        generated.append(key_str)

    save_keys(keys)
    print(f"✅ Generadas {len(generated)} Beta Keys activas en: {KEYS_FILE}")
    for k in generated:
        print(f"  - {k} ({keys[k]['name']})")
    return generated

def list_keys():
    keys = load_keys()
    if not keys:
        print("ℹ️ No hay Beta Keys registradas aún.")
        return

    print(f"📋 LISTA DE BETA KEYS ({len(keys)} Total):")
    print("-" * 65)
    print(f"{'Clave API':35s} | {'Nombre':15s} | {'Estado':8s}")
    print("-" * 65)
    for k, info in keys.items():
        print(f"{k:35s} | {info['name']:15s} | {info['status']:8s}")
    print("-" * 65)

def revoke_key(key_str):
    keys = load_keys()
    if key_str in keys:
        keys[key_str]["status"] = "revoked"
        save_keys(keys)
        print(f"🔴 Clave '{key_str}' revocada con éxito.")
    else:
        print(f"❌ Clave '{key_str}' no encontrada.")

def main():
    parser = argparse.ArgumentParser(description="Beta Keys Manager CLI")
    subparsers = parser.add_subparsers(dest="command")

    gen_parser = subparsers.add_parser("generate", help="Genera nuevas Beta Keys")
    gen_parser.add_argument("--count", type=int, default=15, help="Número de claves a generar")
    gen_parser.add_argument("--prefix", type=str, default="beta_user", help="Prefijo para los nombres de usuario")

    list_parser = subparsers.add_parser("list", help="Lista todas las Beta Keys")

    rev_parser = subparsers.add_parser("revoke", help="Revoca una Beta Key")
    rev_parser.add_argument("--key", type=str, required=True, help="Clave a revocar")

    args = parser.parse_args()

    if args.command == "generate":
        generate_keys(args.count, args.prefix)
    elif args.command == "list":
        list_keys()
    elif args.command == "revoke":
        revoke_key(args.key)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
