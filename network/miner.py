import os
import sys
import time
import argparse
import traceback
from decimal import Decimal, getcontext, ROUND_DOWN
from datetime import datetime, date
import socket
import pickle
import hashlib

from core.mempool import global_mempool
from core.serialization import (
    load_chain, save_chain,
    load_balances, save_balances,
    load_daily_rewards_bin, save_daily_rewards_bin,
    DailyReward
)
from core.blockchain import apply_transaction, calculate_block_hash, verify_transaction_with_balance
from core.limits import calculate_reward_per_second, calculate_max_txs_per_block
from network.p2p_node import broadcast_block
from core.da_vinci import verify_davinci

LOCK_FILE = "network/miner.lock"
MICRO_POW_PREFIX = "000"
BLOCK_INTERVAL = 120
DAILY_LIMIT_PER_MINER = Decimal("24.0")
REQUIRED_FILES = [
    "storage/chain.bin",
    "storage/balances.bin",
    "storage/daily_rewards.bin"
]

getcontext().prec = 18
getcontext().rounding = ROUND_DOWN
ROLE = os.getenv("PETH_ROLE", "user")
P2P_PORT = 5007

def log(msg, level="🔵"):
    print(f"{level} {msg}")

def is_valid_petoron_address(address: str) -> bool:
    return len(address) == 64 and all(c in "0123456789abcdef" for c in address.lower())

def get_total_minted(balances: dict) -> Decimal:
    return sum(Decimal(user.get("balance", 0)) for user in balances.values())

def sign_block(block: dict, miner_address: str) -> str:
    base = block["hash"] + miner_address
    return hashlib.sha256(base.encode()).hexdigest()

def create_valid_block(transactions: list, miner_address: str, previous_block: dict) -> dict:
    index = previous_block["index"] + 1
    previous_hash = previous_block["hash"]
    timestamp = int(time.time())
    nonce = 0
    for tx in transactions:
        if "hash" not in tx or not tx["hash"]:
            tx["hash"] = f"SYSTEM-{miner_address[:8]}-{timestamp}" if tx["from"] == "SYSTEM" else ""
    while True:
        block = {
            "index": index,
            "timestamp": timestamp,
            "transactions": transactions,
            "previous_hash": previous_hash,
            "miner": miner_address,
            "nonce": nonce
        }
        block["hash"] = calculate_block_hash(block)
        if block["hash"].startswith(MICRO_POW_PREFIX):
            block["signature"] = sign_block(block, miner_address)
            return block
        nonce += 1

def update_daily_rewards_incremental(daily_rewards: dict, new_block: dict):
    for tx in new_block.get("transactions", []):
        if tx.get("from") == "SYSTEM":
            dt = datetime.fromtimestamp(new_block["timestamp"]).date()
            key = f"{tx['to'][:12]}-{dt}"
            if key not in daily_rewards:
                daily_rewards[key] = DailyReward(date=dt, miner=tx["to"], amount=0.0)
            daily_rewards[key].amount += float(tx["amount"])

def sync_chain_from_network():
    try:
        with open("storage/peers.bin", "rb") as f:
            peers = pickle.load(f)
    except:
        return

    for peer in peers:
        try:
            s = socket.socket()
            s.settimeout(2)
            s.connect((peer, P2P_PORT))
            s.sendall(b"file_request:chain.bin")
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            s.close()
            if data and len(data) > 100:
                with open("storage/chain.tmp", "wb") as f:
                    f.write(data)
                new_chain = pickle.loads(data)
                local_chain = load_chain()
                if len(new_chain) > len(local_chain):
                    os.replace("storage/chain.tmp", "storage/chain.bin")
                    log("✅ Chain updated from network", "🔁")
                    return
        except:
            continue

def miner_loop(miner_address: str):
    if not miner_address or not is_valid_petoron_address(miner_address):
        log("Invalid miner address.", "🔴")
        sys.exit(1)

    if ROLE != "server":
        log("This device is not authorized to mine (role=user).", "🔴")
        log("Set env var: export PETH_ROLE=server", "🔧")
        sys.exit(1)

    missing = [f for f in REQUIRED_FILES if not os.path.exists(f)]
    if missing:
        for f in missing:
            log(f"❌ Missing: {f}", "🔴")
        log("Please sync full blockchain before mining.", "🔴")
        sys.exit(1)

    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
            log("Previous miner.lock removed", "🔷")
        except Exception as e:
            log(f"Couldn't remove miner.lock: {e}", "🔴")

    log(f"Miner started for {miner_address} | Block every {BLOCK_INTERVAL}s", "🔷")
    log("Peer check skipped — solo mining enabled", "🔷")
    log("Connected to Petoron network", "🔷")
    log("Mining loop started", "🔷")

    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(time.time()))
    except Exception as e:
        log(f"Failed to create miner.lock: {e}", "🔴")
        sys.exit(1)

    daily_rewards = load_daily_rewards_bin()

    try:
        next_mine = time.time()
        while True:
            now = time.time()
            if now < next_mine:
                time.sleep(min(0.5, round(next_mine - now, 2)))
                continue

            current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log(f"[{current_time_str}] ⛏️ Starting new mining cycle", "🔷")

            try:
                sync_chain_from_network()
                global_mempool.clear_expired_transactions()
                mempool_tx = global_mempool.get_pending_transactions()
                chain = load_chain()
                balances = load_balances()
                today = date.today()

                last_block = chain[-1] if chain else {"index": 0, "hash": "0" * 64}
                total_minted = get_total_minted(balances)
                reward_per_second = calculate_reward_per_second(total_minted, 1)
                reward_amount = reward_per_second * Decimal(BLOCK_INTERVAL)

                miner_total_today = sum(
                    Decimal(str(r.amount))
                    for r in daily_rewards.values()
                    if isinstance(r, DailyReward) and r.date == today and r.miner == miner_address
                )
                total_today = sum(
                    Decimal(str(r.amount))
                    for r in daily_rewards.values()
                    if isinstance(r, DailyReward) and r.date == today
                )
                log(f"🪙 TOTAL MINTED TODAY: {total_today:.8f} ADC", "🔷")

                if reward_amount <= 0 or miner_total_today + reward_amount > DAILY_LIMIT_PER_MINER:
                    log(f"‼️ Debug: reward_amount={reward_amount}, mined_today={miner_total_today}", "🧩")
                    log(f"Daily limit reached ({miner_total_today}/{DAILY_LIMIT_PER_MINER}) — skipping mining", "🟡")
                    next_mine = time.time() + BLOCK_INTERVAL
                    continue

                max_txs = calculate_max_txs_per_block(1)
                all_tx = []
                accepted_hashes = set()
                fee_total = Decimal("0")

                for tx in mempool_tx:
                    if len(all_tx) >= max_txs:
                        break
                    try:
                        if tx["from"] == tx["to"] or tx["hash"] in accepted_hashes:
                            continue
                        if tx["from"] != "SYSTEM" and tx["hash"].startswith(MICRO_POW_PREFIX):
                            if verify_transaction_with_balance(tx, balances):
                                apply_transaction(tx, balances)
                                fee_total += Decimal(tx.get("fee", "0"))
                                all_tx.append(tx)
                                accepted_hashes.add(tx["hash"])
                    except Exception as e:
                        log(f"Skipping invalid tx: {e}", "🔴")

                full_reward = reward_amount + fee_total
                reward_tx = {
                    "from": "SYSTEM",
                    "to": miner_address,
                    "amount": str(full_reward),
                    "hash": f"SYSTEM-{miner_address[:8]}-{int(time.time())}",
                    "fee": "0"
                }
                apply_transaction(reward_tx, balances)
                all_tx.insert(0, reward_tx)

                for b in reversed(chain[-10:]):
                    if b["index"] == last_block["index"] + 1:
                        log("❌ Duplicate block index detected — skipping block", "🔴")
                        next_mine = time.time() + BLOCK_INTERVAL
                        break
                else:
                    new_block = create_valid_block(all_tx, miner_address, last_block)
                    if new_block["previous_hash"] != last_block["hash"]:
                        log("❌ Conflict: New block does not match last known hash — skipping", "🔴")
                        next_mine = time.time() + BLOCK_INTERVAL
                        continue

                    chain.append(new_block)
                    save_chain(chain)
                    save_balances(balances)
                    update_daily_rewards_incremental(daily_rewards, new_block)
                    save_daily_rewards_bin(daily_rewards)
                    global_mempool.remove_transactions(accepted_hashes)
                    broadcast_block(new_block)

                    log(f"[{current_time_str}] 🪙 Reward awarded: {full_reward:.8f} ADC", "🟢")
                    log(f"[{current_time_str}] ✅ Block {new_block['index']} created | TXs: {len(all_tx)-1}", "🔷")
                    log(f"[{current_time_str}] ⏳ Waiting {BLOCK_INTERVAL} seconds until next mining cycle...\n", "🔷")

                    next_mine = time.time() + BLOCK_INTERVAL

            except Exception as e:
                log(f"‼️ Exception in mining cycle: {e}", "🔴")
                traceback.print_exc()
                next_mine = time.time() + BLOCK_INTERVAL

    except KeyboardInterrupt:
        log("Miner stopped by user", "🔴")
    finally:
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
                log("miner.lock removed", "🔷")
            except Exception as e:
                log(f"Failed to remove miner.lock: {e}", "🔴")
        sys.exit(0)

if __name__ == "__main__":
    if not verify_davinci():
        log("Da Vinci Code: Unauthorized fork detected.", "🔴")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--address", required=True, help="Miner address for reward")
    args = parser.parse_args()
    miner_loop(args.address)
