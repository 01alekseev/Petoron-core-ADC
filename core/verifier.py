import os
import time
import socket
import pickle
from datetime import datetime
from decimal import Decimal

from core.serialization import (
    load_chain, save_chain, calculate_block_hash, save_daily_rewards_bin
)
from core.transactions import hash_transaction, verify_transaction
from core.limits import calculate_max_txs_per_block, calculate_reward_per_second
from core.mempool import MICRO_POW_PREFIX
from core.da_vinci import verify_davinci
from core.security import verify_block_signature
from network.obfuscator import start_obfuscator

LOCK_PATH = "network/verifier.lock"
LOG_PATH = "logs/verifier.log"
BAD_BLOCKS_PATH = "logs/bad_blocks.txt"
PEERS_FILE = "storage/peers.bin"

os.makedirs("logs", exist_ok=True)

GENESIS_HASH = "0005f280fa112983bc5d0e042ed31ea278bf3248c28afd61d2991d762837e994"

def log(message, level="🔵"):
    ts = datetime.utcnow().isoformat()
    line = f"[{ts}] {level} {message}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def check_lock():
    if os.path.exists(LOCK_PATH):
        log("Verifier already running (lock file exists).", "🟡")
        exit(0)
    with open(LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))

def cleanup():
    if os.path.exists(LOCK_PATH):
        os.remove(LOCK_PATH)

def verify_genesis_block(block):
    if block.get("index") != 0:
        return False, "Invalid index for Genesis block"
    if block.get("previous_hash") != "0" * 64:
        return False, "Invalid previous_hash for Genesis block"
    if block.get("hash") != GENESIS_HASH:
        return False, f"Genesis hash mismatch. Expected: {GENESIS_HASH}, Got: {block.get('hash')}"
    return True, ""

def load_peers_bin():
    if not os.path.exists(PEERS_FILE):
        return []
    with open(PEERS_FILE, "rb") as f:
        try:
            return pickle.load(f)
        except:
            return []

def request_block(index):
    peers = load_peers_bin()
    for peer in peers:
        try:
            ip, port = peer.split(":")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(4)
                s.connect((ip, int(port)))
                req = {"type": "block_request", "indexes": [index]}
                s.sendall(pickle.dumps(req))
                data = bytearray()
                while True:
                    chunk = s.recv(8192)
                    if not chunk:
                        break
                    data.extend(chunk)
                msg = pickle.loads(data)
                if isinstance(msg, dict) and msg.get("type") == "block_response":
                    blocks = msg.get("blocks", [])
                    if blocks:
                        return blocks[0]
        except:
            continue
    return None

def verify_chain(chain):
    seen_tx_hashes: set = set()
    bad_block_indexes: list = []
    recovered = 0

    if not isinstance(chain, list) or len(chain) == 0:
        return False, "❌ Blockchain data is empty or invalid."

    is_valid_genesis, reason = verify_genesis_block(chain[0])
    if not is_valid_genesis:
        return False, f"❌ Invalid Genesis block: {reason}"

    for i, block in enumerate(chain):
        if i == 0:
            continue
        try:
            if not isinstance(block, dict):
                bad_block_indexes.append(i)
                continue

            if "hash" not in block or "transactions" not in block:
                bad_block_indexes.append(i)
                continue

            expected_hash = calculate_block_hash(block)
            if block["hash"] != expected_hash:
                bad_block_indexes.append(i)
                continue

            if not block["hash"].startswith(MICRO_POW_PREFIX):
                bad_block_indexes.append(i)
                continue

            if block["previous_hash"] != chain[i - 1]["hash"]:
                bad_block_indexes.append(i)
                continue

            if len(block["transactions"]) > calculate_max_txs_per_block(1):
                bad_block_indexes.append(i)
                continue

            if not verify_block_signature(block):
                log(f"❌ Invalid block signature at #{i}", "🔴")
                bad_block_indexes.append(i)
                continue

            reward_total = Decimal("0")
            for tx in block["transactions"]:
                tx_hash = tx.get("hash")
                if not tx_hash or tx_hash in seen_tx_hashes:
                    bad_block_indexes.append(i)
                    break
                if hash_transaction(tx) != tx_hash:
                    bad_block_indexes.append(i)
                    break
                seen_tx_hashes.add(tx_hash)
                if tx.get("from") == "SYSTEM":
                    try:
                        amount = Decimal(str(tx.get("amount", "0")))
                        reward_total += amount
                    except:
                        bad_block_indexes.append(i)
                        break
                else:
                    if not verify_transaction(tx):
                        bad_block_indexes.append(i)
                        break

            allowed = calculate_reward_per_second(total_minted=Decimal("0"), active_miners=1) * Decimal("3")
            if reward_total > allowed:
                log(f"❌ Block #{i} exceeds mining reward limit: {reward_total} > {allowed}", "🔴")
                bad_block_indexes.append(i)

        except Exception:
            bad_block_indexes.append(i)
            continue

    for idx in bad_block_indexes:
        replacement = request_block(idx)
        if replacement:
            new_hash = calculate_block_hash(replacement)
            if new_hash != replacement.get("hash"):
                log(f"⚠️ Rejected replacement block #{idx}: invalid hash", "🔴")
                continue
            if replacement["index"] != idx:
                log(f"⚠️ Replacement block #{idx} has mismatched index", "🔴")
                continue
            if not verify_block_signature(replacement):
                log(f"⚠️ Replacement block #{idx} has invalid signature", "🔴")
                continue
            chain[idx] = replacement
            recovered += 1
            log(f"♻️ Recovered corrupted block #{idx} from network", "🟢")

    if recovered > 0:
        save_chain(chain)
        save_daily_rewards_bin({})
        log(f"✅ Chain updated with {recovered} recovered block(s)", "🟢")

    if bad_block_indexes and recovered < len(bad_block_indexes):
        with open(BAD_BLOCKS_PATH, "w") as f:
            for idx in bad_block_indexes:
                f.write(f"{idx}\n")
        return False, f"❌ Chain has {len(bad_block_indexes)} corrupted block(s), {recovered} recovered"

    return True, "✅ Chain is valid and globally synchronized."

def verify_chain_integrity() -> bool:
    try:
        chain = load_chain()
        ok, _ = verify_chain(chain)
        return ok
    except:
        return False

def verify_last_block() -> bool:
    try:
        chain = load_chain()
        if len(chain) < 2:
            return True
        last = chain[-1]
        prev = chain[-2]

        if last["previous_hash"] != prev["hash"]:
            log("❌ Last block previous_hash mismatch", "🔴")
            return False

        if calculate_block_hash(last) != last["hash"]:
            log("❌ Last block hash invalid", "🔴")
            return False

        if not last["hash"].startswith(MICRO_POW_PREFIX):
            log("❌ Last block PoW prefix invalid", "🔴")
            return False

        if not verify_block_signature(last):
            log("❌ Last block signature invalid", "🔴")
            return False

        seen = set()
        for tx in last["transactions"]:
            h = tx.get("hash")
            if not h or hash_transaction(tx) != h or h in seen:
                log("❌ Invalid transaction in last block", "🔴")
                return False
            seen.add(h)

        log("✅ Last block passed verification", "🟢")
        return True
    except Exception as e:
        log(f"❗ Exception in verify_last_block: {e}", "🔴")
        return False

def verifier_loop(interval=10):
    if os.path.exists(LOCK_PATH):
        log("Verifier already running in background (lock file exists).", "🟡")
        return
    with open(LOCK_PATH, "w") as f:
        f.write(str(os.getpid()))
    log("🔵 Background verifier_loop started.")
    threading.Thread(target=start_obfuscator, daemon=True).start()
    try:
        while True:
            try:
                chain = load_chain()
                ok, msg = verify_chain(chain)
                log(msg, "🟢" if ok else "🔴")
            except Exception as e:
                log(f"❗ Verifier loop exception: {e}", "🔴")
            time.sleep(interval)
    finally:
        cleanup()

if __name__ == "__main__":
    if not verify_davinci():
        log("Da Vinci Code: Unauthorized fork detected.", "🔴")
        exit(1)
    check_lock()
    verifier_loop()
