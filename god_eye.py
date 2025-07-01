"""
🔐 GOD EYE — INDEPENDENT INTEGRITY GUARD FOR PETORON

Runs before network launch.
- Verifies protected files are intact (via SHA-256).
- If valid, creates `god_eye.locked` to permit launch.
"""

import os
import sys
import hashlib
from pathlib import Path
import logging

logging.basicConfig(filename="logs/god_eye.log", level=logging.INFO, format="%(message)s")

LOCK_FILE = "god_eye.locked"
HASHES_FILE = "god_eye.hashes"

PROTECTED_FILES = [
    "network/p2p_node.py", "network/miner.py",
    "network/autopeer.py", "network/obfuscator.py",
    
    "core/serialization.py", "core/verifier.py",
    "core/firewall.py", "core/blockchain.py", "core/transactions.py",
    "core/chain_guard.py", "core/backup.py",
    "core/locks.py",

    "wallet.py",
    "cli/interface.py"
]


def hash_file(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except:
        return None

def build_hashes():
    hashes = {}
    for path in PROTECTED_FILES:
        if os.path.exists(path):
            hashes[path] = hash_file(path)
    with open(HASHES_FILE, "w") as f:
        for k, v in hashes.items():
            f.write(f"{k}:{v}\n")
    logging.info("Reference hashes created")
    return hashes

def load_hashes():
    hashes = {}
    if not os.path.exists(HASHES_FILE):
        return {}
    with open(HASHES_FILE) as f:
        for line in f:
            if ":" in line:
                k, v = line.strip().split(":", 1)
                hashes[k] = v
    return hashes

def check_file_integrity():
    saved = load_hashes()
    for path in PROTECTED_FILES:
        current = hash_file(path)
        if not current:
            print(f"❌ Missing or unreadable: {path}")
            return False
        if path not in saved:
            print(f"❌ No reference hash for {path}")
            return False
        if saved[path] != current:
            print(f"🚨 Modified: {path}")
            return False
    return True

def main():
    print("🔐 Launching God Eye (preflight security check)...")
    Path(LOCK_FILE).unlink(missing_ok=True)

    if not os.path.exists(HASHES_FILE):
        print("📁 No hash reference file found. Building fresh hashes...")
        build_hashes()
        print("✅ Reference hashes created. Rerun god_eye.py to validate.")
        return

    if not check_file_integrity():
        print("❌ Integrity check failed. Aborting launch.")
        sys.exit(1)

    Path(LOCK_FILE).write_text("locked")
    logging.info("God Eye validation passed")
    print("✅ God Eye lock engaged. Proceed to launch Petoron.")

if __name__ == "__main__":
    main()
