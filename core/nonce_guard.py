from typing import Dict, Any


def check_nonce(sender: str, tx_nonce: int, balances: Dict[str, Any]) -> bool:
    try:
        current_nonce = balances.get(sender, {}).get("nonce", 0)
        return tx_nonce == current_nonce
    except Exception:
        return False


def update_nonce(sender: str, balances: Dict[str, Any]):
    if sender not in balances:
        balances[sender] = {"balance": 0, "nonce": 0}
    balances[sender]["nonce"] = balances[sender].get("nonce", 0) + 1


def get_current_nonce(sender: str, balances: Dict[str, Any]) -> int:
    return balances.get(sender, {}).get("nonce", 0)


def is_nonce_valid_for_transaction(tx: Dict[str, Any], balances: Dict[str, Any]) -> bool:
    sender = tx.get("from")
    try:
        tx_nonce = int(tx.get("nonce"))
    except:
        return False
    return check_nonce(sender, tx_nonce, balances)
