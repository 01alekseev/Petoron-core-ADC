import os
import time
from datetime import datetime
from core.blockchain import load_chain

FIREWALL_LOG = "logs/firewall_rejections.log"
os.makedirs("logs", exist_ok=True)

def block_origin_check(new_block: dict) -> tuple[bool, str]:
    chain = load_chain()

    if len(chain) == 0:
        if new_block.get("index") != 0:
            return False, "Genesis block index must be 0"
        if new_block.get("previous_hash") != "0" * 64:
            return False, "Invalid genesis previous hash"
        return True, "Genesis block accepted"

    if new_block.get("index") != len(chain):
        return False, "Invalid block index"

    expected_prev_hash = chain[-1].get("hash")
    if new_block.get("previous_hash") != expected_prev_hash:
        log_firewall_event(new_block["index"], "Previous hash mismatch")
        return False, "Mismatch with previous block"

    now = time.time()
    if abs(new_block.get("timestamp", now) - now) > 300:
        log_firewall_event(new_block["index"], "Timestamp anomaly")
        return False, "Timestamp too far from now"

    if "hash" in new_block:
        import hashlib
        import json
        block_copy = dict(new_block)
        block_copy.pop("hash", None)
        calculated = hashlib.sha256(json.dumps(block_copy, sort_keys=True).encode()).hexdigest()
        if calculated != new_block["hash"]:
            log_firewall_event(new_block["index"], "Invalid block hash")
            return False, "Block hash mismatch"

    return True, "Block passed firewall"

def log_firewall_event(block_index: int, reason: str):
    ts = datetime.utcnow().isoformat()
    log_line = f"[{ts}] Block {block_index} rejected: {reason}\n"
    try:
        with open(FIREWALL_LOG, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception:
        pass
