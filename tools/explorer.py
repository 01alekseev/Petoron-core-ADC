import os
import core.prelaunch
import argparse
from decimal import Decimal
from core.serialization import load_chain

def format_tx(tx):
    return {
        "from": tx.get("from"),
        "to": tx.get("to"),
        "amount": str(tx.get("amount")),
        "fee": str(tx.get("fee", 0)),
        "hash": tx.get("hash"),
        "prev_tx_hash": tx.get("prev_tx_hash"),
        "signature": (tx.get("signature") or "")[:12] + "...",
        "public_key": (tx.get("public_key") or "")[:12] + "..."
    }

def print_tx(block_index, tx):
    print(f"\n🧾 Transaction in Block #{block_index}")
    print(f"   From         : {tx.get('from')}")
    print(f"   To           : {tx.get('to')}")
    print(f"   Amount       : {tx.get('amount')}")
    print(f"   Fee          : {tx.get('fee', 0)}")
    print(f"   Hash         : {tx.get('hash')}")
    if tx.get("prev_tx_hash"):
        print(f"   Prev Hash 🧬 : {tx.get('prev_tx_hash')}")
    print(f"   Signature    : {(tx.get('signature') or '')[:64]}...")
    print(f"   Public Key   : {(tx.get('public_key') or '')[:64]}...")

def search_by_hash(chain, tx_hash):
    for block in chain:
        for tx in block.get("transactions", []):
            if tx.get("hash") == tx_hash:
                return block["index"], tx
    return None, None

def search_by_index(chain, tx_index):
    count = 0
    for block in chain:
        for tx in block.get("transactions", []):
            if count == tx_index:
                return block["index"], tx
            count += 1
    return None, None

def search_by_address(chain, address):
    matches = []
    for block in chain:
        for tx in block.get("transactions", []):
            if tx.get("from") == address or tx.get("to") == address:
                matches.append((block["index"], tx))
    return matches

def main():
    parser = argparse.ArgumentParser(description="🔍 Petoron Explorer")
    parser.add_argument("--hash", help="🔑 Search transaction by hash")
    parser.add_argument("--index", type=int, help="🔢 Search by global transaction index")
    parser.add_argument("--address", help="📮 Search all transactions for address")
    args = parser.parse_args()

    chain = load_chain()
    if not chain:
        print("⚠️ Chain is empty or not found.")
        return

    if args.hash:
        block_index, tx = search_by_hash(chain, args.hash)
        if tx:
            print_tx(block_index, tx)
        else:
            print("❌ Transaction not found by hash.")

    elif args.index is not None:
        block_index, tx = search_by_index(chain, args.index)
        if tx:
            print_tx(block_index, tx)
        else:
            print("❌ Transaction not found by index.")

    elif args.address:
        results = search_by_address(chain, args.address)
        if results:
            print(f"\n✅ Found {len(results)} transactions for address: {args.address}")
            for block_index, tx in results:
                print_tx(block_index, tx)
        else:
            print("❌ No transactions found for this address.")

    else:
        print("⚠️ Please specify one of the arguments: --hash, --index, or --address")

if __name__ == "__main__":
    main()

