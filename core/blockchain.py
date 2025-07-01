import os
import core.prelaunch
import time
import hashlib
from decimal import Decimal, ROUND_DOWN, getcontext

from core.serialization import (
    serialize_block,
    deserialize_block,
    serialize_balances,
    deserialize_balances
)
from core.transactions import verify_transaction, hash_transaction
from core.antispam import global_antispam

CHAIN_PATH = "storage/chain.bin"
BALANCES_PATH = "storage/balances.bin"
TOTAL_MINED_PATH = "storage/total_mined.txt"
TOTAL_MINED_LOG_PATH = "storage/total_mined_log.txt"

MAX_SUPPLY = Decimal("1000000000")
COMMISSION_PERCENT = Decimal("0.0001")  # 0.01%

getcontext().prec = 18
getcontext().rounding = ROUND_DOWN

def load_chain(path=CHAIN_PATH):
    if not os.path.exists(path):
        return []
    chain = []
    with open(path, "rb") as f:
        while True:
            length_bytes = f.read(4)
            if not length_bytes or len(length_bytes) < 4:
                break
            block_size = int.from_bytes(length_bytes, "big")
            if block_size <= 0:
                break
            block_data = f.read(block_size)
            if len(block_data) != block_size:
                break
            try:
                block, _ = deserialize_block(block_data)
                chain.append(block)
            except Exception as e:
                print(f"[⚠️] Ошибка десериализации блока: {e}")
    return chain

def save_chain(chain, path=CHAIN_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        for block in chain:
            data = serialize_block(block)
            f.write(len(data).to_bytes(4, "big"))
            f.write(data)

def load_balances(path=BALANCES_PATH):
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as f:
        raw = f.read()
        try:
            return deserialize_balances(raw)
        except Exception:
            return {}

def save_balances(balances, path=BALANCES_PATH):
    with open(path, "wb") as f:
        f.write(serialize_balances(balances))

def calculate_block_hash(block):
    block_copy = {
        "index": block["index"],
        "timestamp": block["timestamp"],
        "previous_hash": block["previous_hash"],
        "transactions": block["transactions"],
        "miner": block.get("miner", ""),
        "nonce": block["nonce"]
    }
    data = serialize_block(block_copy)
    return hashlib.sha256(data).hexdigest()

def load_total_mined():
    if not os.path.exists(TOTAL_MINED_PATH):
        return Decimal("0")
    with open(TOTAL_MINED_PATH, "r") as f:
        return Decimal(f.read().strip())

def save_total_mined(value: Decimal):
    os.makedirs(os.path.dirname(TOTAL_MINED_PATH), exist_ok=True)
    with open(TOTAL_MINED_PATH, "w") as f:
        f.write(str(value))

def log_total_mined(timestamp: int, block_index: int, total: Decimal):
    os.makedirs(os.path.dirname(TOTAL_MINED_LOG_PATH), exist_ok=True)
    with open(TOTAL_MINED_LOG_PATH, "a") as f:
        f.write(f"{timestamp} | {block_index} | {total}\n")

def is_commission_enabled():
    return load_total_mined() >= MAX_SUPPLY

def calculate_commission(amount: Decimal) -> Decimal:
    return (amount * COMMISSION_PERCENT).quantize(Decimal("0.00000001"))

def verify_transaction_with_balance(tx, balances):
    sender = tx.get("from")
    amount = Decimal(str(tx.get("amount", "0")))
    fee = Decimal(str(tx.get("fee", "0")))

    if sender != "SYSTEM":
        ts = tx.get("timestamp", int(time.time()))
        if not global_antispam.check_and_register(sender, ts):
            return False

        if sender not in balances:
            return False

        sender_balance = Decimal(str(balances[sender].get("balance", "0")))
        total_required = amount + (fee if is_commission_enabled() else Decimal("0"))
        if sender_balance < total_required:
            return False

    if is_commission_enabled():
        expected_fee = calculate_commission(amount)
        if fee < expected_fee:
            return False
        if fee > 0 and not tx.get("miner"):
            return False

    if "hash" not in tx or tx["hash"] != hash_transaction(tx):
        return False

    if not verify_transaction(tx):
        return False

    return True

def apply_transaction(tx, balances, block_index=0):
    sender = tx.get("from")
    receiver = tx.get("to")
    amount = Decimal(str(tx.get("amount", "0")))
    fee = Decimal(str(tx.get("fee", "0")))
    miner = tx.get("miner")

    if sender != "SYSTEM":
        prev_balance = Decimal(str(balances.get(sender, {}).get("balance", "0")))
        balances[sender] = {"balance": prev_balance - amount - fee}
    else:
        total_mined = load_total_mined()
        total_mined += amount
        save_total_mined(total_mined)
        log_total_mined(tx.get("timestamp", int(time.time())), block_index, total_mined)

    prev_balance_recv = Decimal(str(balances.get(receiver, {}).get("balance", "0")))
    balances[receiver] = {"balance": prev_balance_recv + amount}

    if is_commission_enabled() and miner and fee > 0:
        prev_miner_bal = Decimal(str(balances.get(miner, {}).get("balance", "0")))
        balances[miner] = {"balance": prev_miner_bal + fee}

def sign_block(block):
    import hashlib
    addr = block.get("miner", "")
    raw = f"{block['index']}{block['timestamp']}{block['previous_hash']}{block['nonce']}{addr}".encode()
    return hashlib.sha256(raw).hexdigest()

def verify_block_signature(block):
    expected = sign_block(block)
    return block.get("signature") == expected

def is_peer_allowed(ip: str):
    from core.serialization import load_peers_bin
    peers = load_peers_bin()
    for p in peers:
        if p.startswith(ip + ":"):
            return True
    return False
