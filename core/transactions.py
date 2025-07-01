import os
import time
import logging
import binascii
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
import pickle

from core.limits import TOTAL_SUPPLY, calculate_fee
from core.pow import hash_transaction, mine_transaction_pow
from core.nonce_guard import check_nonce, update_nonce

TOTAL_SUPPLY_LIMIT = TOTAL_SUPPLY
MICRO_POW_PREFIX = "000"
PENDING_TXS_FILE = "storage/pending_txs.bin"
TX_EXPIRATION_SECONDS = 300
TX_RETRY_INTERVAL = 60

logging.basicConfig(filename='logs/transactions.log', level=logging.WARNING)

pending_tx_pool = []

def format_decimal(value):
    try:
        return Decimal(value).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
    except (InvalidOperation, TypeError):
        return Decimal("0.0")

def generate_nonce(length=8) -> str:
    return binascii.hexlify(os.urandom(length)).decode()

def create_transaction(sender: str, receiver: str, amount: Decimal, miner: str = None, total_supply: Decimal = Decimal("0")) -> list:
    if sender == receiver:
        logging.warning(f"[TX BLOCKED] Self-transfer from {sender}")
        return []

    base_tx = {
        "from": sender,
        "to": receiver,
        "amount": format_decimal(amount),
        "timestamp": int(time.time()),
        "nonce": "",
        "signature": "",
        "public_key": "",
        "hash": "",
        "status": "pending"
    }
    base_tx = mine_transaction_pow(base_tx)
    transactions = [base_tx]
    pending_tx_pool.append(base_tx)
    save_pending_transactions()

    if total_supply >= TOTAL_SUPPLY_LIMIT and sender != "SYSTEM" and miner and receiver != miner:
        fee = calculate_fee(amount, total_supply)
        if fee > 0:
            fee_tx = {
                "from": sender,
                "to": miner,
                "amount": format_decimal(fee),
                "timestamp": int(time.time()),
                "nonce": "",
                "signature": "",
                "public_key": "",
                "hash": "",
                "status": "pending"
            }
            fee_tx = mine_transaction_pow(fee_tx)
            transactions.append(fee_tx)
            pending_tx_pool.append(fee_tx)
            save_pending_transactions()

    return transactions

def save_pending_transactions():
    try:
        with open(PENDING_TXS_FILE, "wb") as f:
            pickle.dump(pending_tx_pool, f)
    except Exception as e:
        logging.warning(f"[SAVE FAIL] {e}")

def load_pending_transactions():
    global pending_tx_pool
    try:
        with open(PENDING_TXS_FILE, "rb") as f:
            pending_tx_pool = pickle.load(f)
    except:
        pending_tx_pool = []

def retry_pending_transactions(mempool):
    now = int(time.time())
    for tx in list(pending_tx_pool):
        if now - tx.get("timestamp", 0) > TX_EXPIRATION_SECONDS:
            tx["status"] = "expired"
            pending_tx_pool.remove(tx)
        elif tx["status"] == "pending":
            mempool.add_transaction(tx)
    save_pending_transactions()

def sign_transaction(wallet, tx: dict) -> str:
    amt_str = str(format_decimal(tx["amount"]))
    data = f"{tx['from']}|{tx['to']}|{amt_str}|{tx['timestamp']}|{tx['nonce']}".encode()
    signature = wallet.sign(data)
    return signature.hex()

def verify_signature(tx: dict) -> bool:
    try:
        public_key_pem = tx["public_key"]
        if isinstance(public_key_pem, bytes):
            public_key_pem = public_key_pem.decode("utf-8")
        public_key = serialization.load_pem_public_key(public_key_pem.encode())

        amt_str = str(format_decimal(tx["amount"]))
        data = f"{tx['from']}|{tx['to']}|{amt_str}|{tx['timestamp']}|{tx['nonce']}".encode()

        public_key.verify(
            bytes.fromhex(tx["signature"]),
            data,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except (InvalidSignature, Exception):
        return False

def verify_transaction(tx: dict) -> bool:
    try:
        if tx.get("from") == "SYSTEM":
            required = ["from", "to", "amount", "timestamp", "nonce", "hash"]
            for k in required:
                if k not in tx or not tx[k]:
                    return False
            if tx.get("signature") or tx.get("public_key"):
                return False
            if tx["hash"] != hash_transaction(tx):
                return False
            if not tx["hash"].startswith(MICRO_POW_PREFIX):
                return False
            return True

        required_fields = ["from", "to", "amount", "timestamp", "nonce", "hash", "signature", "public_key"]
        if not all(k in tx and tx[k] for k in required_fields):
            logging.warning(f"[TX MISSING FIELD] {tx}")
            return False
        if tx["from"] == tx["to"]:
            return False
        if tx["from"].startswith("SYSTEM") and tx["from"] != "SYSTEM":
            return False
        if abs(int(time.time()) - int(tx["timestamp"])) > 600:
            return False
        if Decimal(tx["amount"]) <= Decimal("0"):
            return False
        if tx["hash"] != hash_transaction(tx):
            return False
        if not tx["hash"].startswith(MICRO_POW_PREFIX):
            return False
        if not verify_signature(tx):
            return False

        return True
    except Exception as e:
        logging.warning(f"[TX VERIFY ERROR] {e} — {tx}")
        return False

def verify_transaction_with_balance(tx: dict, balances: dict) -> bool:
    if tx.get("from") == "SYSTEM":
        if tx.get("signature") or tx.get("public_key"):
            print(f"[SYSTEM TX BLOCKED] Signed SYSTEM transaction")
            return False
        return verify_transaction(tx)

    if not verify_transaction(tx):
        print(f"[SIGNATURE FAIL] {tx.get('from')} → {tx.get('to')} | hash={tx.get('hash')}")
        return False

    if not check_nonce(tx.get("from"), int(tx.get("nonce", 0)), balances):
        print(f"[NONCE FAIL] {tx.get('from')}")
        return False

    sender = tx.get("from")
    amount = format_decimal(tx.get("amount", 0))
    sender_balance = format_decimal(balances.get(sender, {}).get("balance", 0))

    if sender_balance < amount:
        print(f"[BALANCE FAIL] {sender}: need {amount}, has {sender_balance}")
        return False

    return True

def apply_transaction(tx: dict, balances: dict):
    sender = tx.get("from")
    receiver = tx.get("to")
    amount = format_decimal(tx.get("amount", 0))

    if sender != "SYSTEM":
        prev_balance = format_decimal(balances.get(sender, {}).get("balance", 0))
        balances[sender] = {"balance": prev_balance - amount}
        update_nonce(sender, balances)

    prev_balance_recv = format_decimal(balances.get(receiver, {}).get("balance", 0))
    balances[receiver] = {"balance": prev_balance_recv + amount}

def validate_transaction_sequence(txs: list) -> (bool, str):
    seen_hashes = set()
    signatures = set()
    for i, tx in enumerate(txs):
        tx_hash = tx.get("hash")
        sig = tx.get("signature")

        if not tx_hash:
            return False, f"Missing hash at tx {i}"
        if tx_hash in seen_hashes:
            return False, f"Duplicate tx hash: {tx_hash}"
        if hash_transaction(tx) != tx_hash:
            return False, f"Hash mismatch in tx {i}"
        if not tx_hash.startswith(MICRO_POW_PREFIX):
            return False, f"Micro-PoW failed at tx {i}"
        if sig in signatures and tx.get("from") != "SYSTEM":
            return False, f"Duplicate signature at tx {i}"
        if tx.get("from") != "SYSTEM" and not verify_transaction(tx):
            return False, f"Invalid signature in tx {i}"

        seen_hashes.add(tx_hash)
        signatures.add(sig)

    return True, "OK"

load_pending_transactions()
