import os
import sys
import core.prelaunch
import hashlib
from decimal import Decimal, getcontext, ROUND_DOWN
from core.serialization import serialize_block, serialize_balances
from core.transactions import hash_transaction
from core.mempool import mine_transaction_pow

getcontext().prec = 18
getcontext().rounding = ROUND_DOWN

CREATOR_ADDRESS = "588d4bd806abbf999ea84020ed4396ed00183daa21a033bca5ca8d9d9d4b04c2"
TALENTS_FUND_ADDRESS = "2e0562d004cd5af7b82a5c2190dc419ac8f0994aa0772bd086bd72bf820fcce9"

CHAIN_PATH = "storage/chain.bin"
BALANCES_PATH = "storage/balances.bin"

if os.path.exists(CHAIN_PATH):
    print("🚫 Chain already exists. Genesis block generation is locked.")
    sys.exit(1)

for lf in [CHAIN_PATH, BALANCES_PATH, "storage/node.lock", "storage/verifier.lock"]:
    try:
        if os.path.exists(lf):
            os.remove(lf)
    except Exception as e:
        print(f"[!] Error removing {lf}: {e}")

def mine_block(block, prefix="000"):
    nonce = 0
    while True:
        block["nonce"] = nonce
        block_copy = {
            "index": block["index"],
            "timestamp": block["timestamp"],
            "previous_hash": block["previous_hash"],
            "transactions": block["transactions"],
            "miner": block.get("miner", ""),
            "nonce": nonce
        }
        serialized = serialize_block(block_copy)
        block_hash = hashlib.sha256(serialized).hexdigest()
        if block_hash.startswith(prefix):
            block["hash"] = block_hash
            return block
        nonce += 1

def create_genesis_block():
    tx1 = {
        "from": "SYSTEM",
        "to": CREATOR_ADDRESS,
        "amount": Decimal("50000000"),
        "timestamp": 0,
        "nonce": "GEN-0",
        "signature": "",
        "public_key": "",
        "fee": Decimal("0"),
        "hash": ""
    }
    tx1 = mine_transaction_pow(tx1)
    tx1["hash"] = hash_transaction(tx1)

    tx2 = {
        "from": "SYSTEM",
        "to": TALENTS_FUND_ADDRESS,
        "amount": Decimal("5000000"),
        "timestamp": 0,
        "nonce": "GEN-1",
        "signature": "",
        "public_key": "",
        "fee": Decimal("0"),
        "hash": ""
    }
    tx2 = mine_transaction_pow(tx2)
    tx2["hash"] = hash_transaction(tx2)

    block = {
        "index": 0,
        "timestamp": 0,
        "previous_hash": "0" * 64,
        "transactions": [tx1, tx2],
        "miner": "",
        "nonce": 0
    }
    return mine_block(block)

def save_chain(chain):
    os.makedirs("storage", exist_ok=True)
    with open(CHAIN_PATH, "wb") as f:
        for block in chain:
            f.write(serialize_block(block))

def save_balances(balances):
    with open(BALANCES_PATH, "wb") as f:
        f.write(serialize_balances(balances))

def main():
    genesis_block = create_genesis_block()
    save_chain([genesis_block])

    balances = {
        CREATOR_ADDRESS: {"balance": Decimal("50000000")},
        TALENTS_FUND_ADDRESS: {"balance": Decimal("5000000")}
    }
    save_balances(balances)

    print(f"✅ Genesis block mined with nonce {genesis_block['nonce']} and hash {genesis_block['hash']}")
    print(f"📦 Saved: {CHAIN_PATH}")
    print(f"💰 Saved: {BALANCES_PATH}")

if __name__ == "__main__":
    main()

