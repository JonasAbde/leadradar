#!/usr/bin/env python3
"""LeadRadar state checker — run on every session start."""

import subprocess, json, os, sys

def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return "", str(e), 1

def check():
    print("=" * 60)
    print("LEADRADER STATE CHECK")
    print("=" * 60)

    # Git status
    out, _, code = run("cd ~/leadradar && git status --short")
    print(f"\n[Git Status] {'CLEAN' if not out else f'DIRTY: {out[:200]}'}")

    out, _, _ = run("cd ~/leadradar && git log --oneline -3")
    print(f"[Last commits]\n{out}")

    # App health
    out, _, code = run("curl -s http://localhost:8000/health 2>/dev/null || echo 'DOWN'")
    print(f"\n[App Health] {out}")

    # Processes
    out, _, _ = run("pgrep -f 'python.*run.py' | wc -l")
    print(f"[Running instances] {out.strip()} process(es)")

    # DB
    for db in ["data/leadradar.db", "leadradar.db"]:
        exists = os.path.exists(os.path.expanduser(f"~/leadradar/{db}"))
        size = os.path.getsize(os.path.expanduser(f"~/leadradar/{db}")) if exists else 0
        print(f"[DB {db}] {'EXISTS' if exists else 'MISSING'} ({size} bytes)")

    # Files
    for f in ["STATE.md", "BUILD_PROTOCOL.md"]:
        exists = os.path.exists(os.path.expanduser(f"~/leadradar/{f}"))
        print(f"[{f}] {'EXISTS' if exists else 'MISSING'}")

    # Systemd
    out, _, code = run("systemctl is-active leadradar 2>/dev/null || echo 'unknown'")
    print(f"\n[Systemd] {out}")

    print("\n" + "=" * 60)
    print("Read STATE.md for next steps.")
    print("=" * 60)

if __name__ == "__main__":
    check()
