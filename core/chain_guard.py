import os
from core.serialization import load_chain, calculate_block_hash, CHAIN_FILE
from core.checkpoints import verify_chain_checkpoints

def check_chain_integrity(verbose: bool = True) -> bool:
    if not os.path.exists(CHAIN_FILE):
        if verbose:
            print("[🆕] No chain.bin found — assuming fresh node.")
        return True

    size = os.path.getsize(CHAIN_FILE)
    if size == 0:
        if verbose:
            print("[🆕] Empty chain.bin — assuming new node.")
        return True

    chain = load_chain()
    if not chain:
        if verbose:
            print("[⚠️] Chain could not be loaded — possibly corrupted.")
        return False

    for i, block in enumerate(chain):
        expected_hash = calculate_block_hash(block)
        actual_hash = block.get("hash", "")
        if expected_hash != actual_hash:
            print(f"[❌] Invalid hash at block #{block['index']}")
            print(f"     Expected: {expected_hash}")
            print(f"     Found:    {actual_hash}")

            print("\n[🔍] Context blocks:")
            if i > 0:
                print(" ← Prev:", chain[i-1])
            print(" ✘ Corrupt:", block)
            if i + 1 < len(chain):
                print(" → Next:", chain[i+1])
            return False

    if not verify_chain_checkpoints(chain):
        if verbose:
            print("[❌] Chain checkpoint verification failed.")
        return False

    if verbose:
        print(f"[✅] Chain OK. {len(chain)} blocks verified.")
    return True

if __name__ == "__main__":
    result = check_chain_integrity()
    if not result:
        exit(1)
