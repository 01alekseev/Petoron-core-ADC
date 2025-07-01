import os
import core.prelaunch
from decimal import Decimal
from core.serialization import load_chain

def format_decimal(val):
    try:
        return str(Decimal(val).quantize(Decimal("0.00000001")))
    except:
        return "0.00000000"

def display_block(block):
    print(f"\n📦 Block #{block.get('index', '?')}")
    print(f"🕒 Timestamp   : {block.get('timestamp', '?')}")
    print(f"🔗 Prev Hash  : {block.get('previous_hash', '?')}")
    print(f"🧮 Nonce      : {block.get('nonce', 'N/A')}")
    print(f"🧬 Hash       : {block.get('hash', '?')}")
    print(f"👷 Miner      : {block.get('miner', 'SYSTEM')}")

    txs = block.get("transactions", [])
    if not txs:
        print("— No transactions —")
        return

    print(f"💸 Transactions ({len(txs)}):")
    for i, tx in enumerate(txs, start=1):
        sender = tx.get("from", "N/A")
        recipient = tx.get("to", "N/A")
        amount = format_decimal(tx.get("amount", "0"))
        fee = format_decimal(tx.get("fee", "0"))
        tx_hash = tx.get("hash", "N/A")
        signature = tx.get("signature", "")
        print(f"  #{i} {sender} → {recipient} | {amount} ADC (fee {fee})")
        print(f"     ↳ Hash     : {tx_hash}")
        if signature:
            print(f"     ↳ Signature: {signature[:20]}...")

def show_full_chain():
    chain = load_chain()
    if not chain:
        print("❌ Blockchain is empty.")
        return
    print(f"\n✅ Total blocks in chain: {len(chain)}")
    for block in chain:
        display_block(block)

if __name__ == "__main__":
    show_full_chain()

