import hashlib
from decimal import Decimal, ROUND_DOWN, InvalidOperation

MICRO_POW_PREFIX = "000"

def format_decimal(value):
    try:
        return Decimal(value).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
    except (InvalidOperation, TypeError):
        return Decimal("0.0")

def hash_transaction(tx: dict) -> str:
    try:
        amt_str = str(format_decimal(tx["amount"]))
        base = f"{tx['from']}|{tx['to']}|{amt_str}|{tx['timestamp']}|{tx['nonce']}"
        return hashlib.sha256(base.encode()).hexdigest()
    except Exception:
        return ""

def mine_transaction_pow(tx: dict, prefix: str = MICRO_POW_PREFIX) -> dict:
    nonce_counter = 0
    while True:
        tx["nonce"] = str(nonce_counter).zfill(16)
        tx_hash = hash_transaction(tx)
        if tx_hash.startswith(prefix):
            tx["hash"] = tx_hash
            return tx
        nonce_counter += 1
