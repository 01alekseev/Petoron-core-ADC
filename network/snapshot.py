import os
import shutil
from datetime import datetime

SNAPSHOT_DIR = "storage/snapshots"
FILES_TO_BACKUP = [
    "storage/chain.bin",
    "storage/balances.bin",
    "storage/daily_rewards.bin",
    "storage/peers.bin"
]

def create_snapshot() -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    target_dir = os.path.join(SNAPSHOT_DIR, timestamp)
    os.makedirs(target_dir, exist_ok=True)

    for file in FILES_TO_BACKUP:
        if os.path.exists(file):
            shutil.copy2(file, os.path.join(target_dir, os.path.basename(file)))

    print(f"[📦] Snapshot saved: {target_dir}")
    return target_dir

def list_snapshots() -> list:
    if not os.path.isdir(SNAPSHOT_DIR):
        return []
    return sorted(os.listdir(SNAPSHOT_DIR))

def restore_snapshot(snapshot_name: str) -> bool:
    snapshot_path = os.path.join(SNAPSHOT_DIR, snapshot_name)
    if not os.path.isdir(snapshot_path):
        print(f"[⚠️] Snapshot not found: {snapshot_path}")
        return False

    for filename in os.listdir(snapshot_path):
        src = os.path.join(snapshot_path, filename)
        dst = os.path.join("storage", filename)
        if os.path.isfile(src):
            shutil.copy2(src, dst)

    print(f"[✅] Restored snapshot: {snapshot_name}")
    return True

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Petoron Snapshot Manager")
    parser.add_argument("--create", action="store_true", help="Create a new snapshot")
    parser.add_argument("--list", action="store_true", help="List available snapshots")
    parser.add_argument("--restore", metavar="SNAPSHOT", help="Restore from given snapshot name")

    args = parser.parse_args()

    if args.create:
        create_snapshot()
    elif args.list:
        snaps = list_snapshots()
        if snaps:
            print("Available snapshots:")
            for s in snaps:
                print(" -", s)
        else:
            print("No snapshots found.")
    elif args.restore:
        restore_snapshot(args.restore)
    else:
        parser.print_help()
