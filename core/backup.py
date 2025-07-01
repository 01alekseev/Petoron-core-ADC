import os
import shutil
from datetime import datetime

SNAPSHOT_DIR = "storage/snapshots"
FILES = [
    "chain.bin",
    "balances.bin",
    "daily_rewards.bin",
    "peers.bin"
]
STORAGE_DIR = "storage"

def log(msg):
    print(f"[🛡️] {msg}")

def get_latest_snapshot_path():
    if not os.path.exists(SNAPSHOT_DIR):
        return None
    snapshots = sorted(os.listdir(SNAPSHOT_DIR), reverse=True)
    for snap in snapshots:
        path = os.path.join(SNAPSHOT_DIR, snap)
        if os.path.isdir(path):
            return path
    return None

def is_file_missing_or_empty(filename):
    path = os.path.join(STORAGE_DIR, filename)
    return not os.path.exists(path) or os.path.getsize(path) == 0

def restore_from_snapshot():
    snapshot_path = get_latest_snapshot_path()
    if not snapshot_path:
        log("❌ No snapshot found.")
        return False

    restored = 0
    for name in FILES:
        target_path = os.path.join(STORAGE_DIR, name)
        source_path = os.path.join(snapshot_path, name)

        if is_file_missing_or_empty(name) and os.path.exists(source_path):
            shutil.copy2(source_path, target_path)
            log(f"♻️ Restored {name} from snapshot.")
            restored += 1

    if restored > 0:
        log(f"✅ Restored {restored} file(s) from: {snapshot_path}")
        return True
    else:
        log("ℹ️ All files present. No restore needed.")
        return False

if __name__ == "__main__":
    restore_from_snapshot()
