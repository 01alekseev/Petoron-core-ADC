import os
import platform
import random
import socket
import subprocess
import sys
import time
import getpass
import readline
import pickle
import threading
from decimal import Decimal, getcontext, ROUND_DOWN

from wallet import Wallet
from core.serialization import (
    load_balances, save_balances,
    load_peers_bin, load_chain
)
from core.transactions import (
    create_transaction,
    sign_transaction,
    hash_transaction,
    verify_transaction_with_balance
)
from core.mempool import global_mempool
from core.limits import calculate_fee, get_total_supply
from core.da_vinci import verify_davinci

VERSION = "Petoron CLI v1.0.17"
getcontext().prec = 18
getcontext().rounding = ROUND_DOWN

PEERS_FILE = "storage/peers.bin"
VALID_MOVES = {"U", "D", "L", "R", "F", "B", "U'", "D'", "L'", "R'", "F'", "B'"}
ROLE = os.environ.get("PETORON_ROLE", "CLIENT").strip().upper()
LOCK_FILE = "interface.lock"


def format_decimal(value):
    return Decimal(value).quantize(Decimal("0.00000000"), rounding=ROUND_DOWN).__format__(".8f")


def generate_sequence():
    return [random.choice(list(VALID_MOVES)) for _ in range(16)]


def clear_sensitive_data(*args):
    for item in args:
        if isinstance(item, list):
            for i in range(len(item)):
                item[i] = None
        elif isinstance(item, str):
            item = None


def get_balance(address: str) -> str:
    balances = load_balances()
    bal = balances.get(address, {"balance": Decimal("0")})["balance"]
    return format_decimal(bal)


def is_valid_petoron_address(address: str) -> bool:
    return isinstance(address, str) and len(address) == 64 and all(c in "0123456789abcdef" for c in address.lower())


def load_peers():
    return load_peers_bin()


def is_connected_to_network(timeout=1):
    peers = load_peers()
    for peer in peers:
        try:
            ip, port = peer.split(":")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect((ip, int(port)))
                return True
        except:
            time.sleep(1)
            continue
    return False


def broadcast_transaction_to_peers(tx: dict):
    payload = pickle.dumps({"type": "tx", "data": tx})
    peers = load_peers()
    for peer in peers:
        try:
            ip, port = peer.split(":")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect((ip, int(port)))
                s.sendall(payload)
        except:
            pass


def create_wallet():
    seq1 = generate_sequence()
    seq2 = generate_sequence()
    while seq1 == seq2:
        seq2 = generate_sequence()
    wallet = Wallet(seq1, seq2)
    address = wallet.get_address()
    balances = load_balances()
    if address not in balances:
        balances[address] = {"balance": Decimal("0")}
        save_balances(balances)
    print("First Combination:", " ".join(seq1))
    print("Second Combination:", " ".join(seq2))
    print("Address:", address)
    print(f"Balance: {get_balance(address)} ADC")
    clear_sensitive_data(seq1, seq2)


def restore_wallet():
    attempts = 0
    while attempts < 3:
        raw_a = getpass.getpass("Enter first combination: ").strip()
        raw_b = getpass.getpass("Enter second combination: ").strip()
        seq1 = raw_a.split()
        seq2 = raw_b.split()
        if seq1 == seq2 or len(seq1) != 16 or len(seq2) != 16:
            print("Invalid credentials.")
            attempts += 1
            time.sleep(1.5)
            clear_sensitive_data(seq1, seq2, raw_a, raw_b)
            continue
        if not all(m in VALID_MOVES for m in seq1 + seq2):
            print("Invalid credentials.")
            attempts += 1
            time.sleep(1.5)
            clear_sensitive_data(seq1, seq2, raw_a, raw_b)
            continue
        break
    else:
        print("Too many failed attempts.")
        clear_sensitive_data(seq1, seq2, raw_a, raw_b)
        return

    temp_wallet = Wallet(seq1, seq2)
    address = temp_wallet.get_address()
    balances = load_balances()
    if address not in balances:
        print("Wallet not found.")
        clear_sensitive_data(seq1, seq2, raw_a, raw_b)
        return
    wallet = temp_wallet
    print(f"Address: {address}")
    print(f"Balance: {get_balance(address)} ADC")
    clear_sensitive_data(raw_a, raw_b)
    while True:
        print("1 — Send ADC")
        print("2 — Exit Wallet")
        choice = input("Select option: ").strip()
        if choice == "1":
            if not is_connected_to_network():
                print("🔴 Connect to Petoron network to send transactions.")
            else:
                send_coins(wallet)
        elif choice == "2":
            break


def send_coins(wallet=None):
    balances = load_balances()
    sender_address = wallet.get_address()
    sender_balance = Decimal(balances.get(sender_address, {"balance": Decimal("0")})["balance"])
    if sender_balance == 0:
        print("🔴 Insufficient balance.")
        return
    while True:
        to_address = input("Enter recipient address: ").strip()
        if not is_valid_petoron_address(to_address):
            print("Invalid address format.")
            time.sleep(1)
            continue
        if to_address == sender_address:
            print("Cannot send to your own address.")
            time.sleep(1)
            continue
        if to_address not in balances:
            print("Unknown address.")
            time.sleep(1)
            continue
        break
    while True:
        amount_str = input("Enter amount to send: ").strip()
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError
        except:
            print("Invalid amount.")
            time.sleep(1)
            continue
        total_minted = get_total_supply()
        fee = calculate_fee(amount, total_minted)
        total = amount + fee
        if total > sender_balance:
            print("Not enough balance including fee.")
            time.sleep(1)
            continue
        break
    confirmation = input(f"Send {format_decimal(amount)} ADC to {to_address}? Type 'YES': ").strip()
    if confirmation != "YES":
        return
    combo_b_input = getpass.getpass("Enter second combination to sign: ")
    seq2 = combo_b_input.strip().split()
    if len(seq2) != 16 or not all(m in VALID_MOVES for m in seq2):
        print("Invalid second combination.")
        clear_sensitive_data(seq2, combo_b_input)
        return
    try:
        wallet_b = Wallet(wallet.cube_a, seq2)
    except Exception:
        print("Failed to create wallet with second combination.")
        clear_sensitive_data(seq2, combo_b_input)
        return
    tx = create_transaction(sender_address, to_address, amount, wallet_b)
    tx["hash"] = hash_transaction(tx)
    if not verify_transaction_with_balance(tx, balances):
        print("Transaction verification failed.")
        clear_sensitive_data(seq2, combo_b_input)
        return
    global_mempool.add(tx)
    broadcast_transaction_to_peers(tx)
    print(f"✅ Sent {format_decimal(amount)} ADC to {to_address} (fee: {format_decimal(fee)} ADC)")
    print(f"🔑 Hash: {tx['hash']}")
    clear_sensitive_data(seq2, combo_b_input)


def start_miner_with_address():
    miner_address = input("Enter miner address: ").strip()
    if not is_valid_petoron_address(miner_address):
        print("Invalid miner address.")
        return
    file_paths = [
        "storage/chain.bin",
        "storage/balances.bin",
        "storage/daily_rewards.bin"
    ]
    total_bytes = sum(os.path.getsize(p) for p in file_paths if os.path.exists(p))
    downloaded = 0
    while downloaded < total_bytes:
        time.sleep(0.2)
        downloaded = sum(os.path.getsize(p) for p in file_paths if os.path.exists(p))
        percent = (downloaded / total_bytes) * 100 if total_bytes else 100
        print(f"Syncing... {percent:.1f}%", end="\r")
    try:
        os.remove("network/miner.lock")
    except FileNotFoundError:
        pass
    subprocess.Popen(
        [sys.executable, "network/miner.py", "--address", miner_address]
    )
    print(f"Miner launched for: {miner_address}")

    def update_balance_loop():
        while os.path.exists("network/miner.lock"):
            print(f"Balance: {get_balance(miner_address)} ADC")
            time.sleep(120)

    threading.Thread(target=update_balance_loop, daemon=True).start()
    while True:
        print("0 — Stop Mining")
        action = input("Select: ").strip()
        if action == "0":
            try:
                os.remove("network/miner.lock")
            except FileNotFoundError:
                pass
            print("Stopped mining.")
            break


def view_history():
    chain = load_chain()
    if not chain:
        print("No chain data found.")
        return

    search = input("Enter address or transaction hash: ").strip().lower()
    if len(search) == 64 and all(c in "0123456789abcdef" for c in search):
        found_tx = []
        for block in chain:
            for tx in block.get("transactions", []):
                if tx.get("hash") == search:
                    found_tx.append((block["index"], tx))
        if not found_tx:
            print("Transaction not found.")
            return
        for idx, tx in found_tx:
            print(f"\n📦 Block #{idx}")
            for k, v in tx.items():
                print(f"  {k}: {v}")
        return

    found = []
    for block in chain:
        for tx in block.get("transactions", []):
            if tx.get("from") == search or tx.get("to") == search:
                found.append((block["index"], tx))

    if not found:
        print("No transactions found for that address.")
        return

    print(f"Found {len(found)} transactions for address: {search}")
    for idx, tx in found:
        print(f"\n📦 Block #{idx}")
        print(f"  From:    {tx.get('from')}")
        print(f"  To:      {tx.get('to')}")
        print(f"  Amount:  {tx.get('amount')}")
        print(f"  Fee:     {tx.get('fee')}")
        print(f"  Time:    {tx.get('timestamp')}")
        print(f"  Hash:    {tx.get('hash')}")
        print(f"  Nonce:   {tx.get('nonce')}")
        print(f"  Signature: {tx.get('signature')[:32]}...")


def main():
    if os.path.exists(LOCK_FILE):
        age = time.time() - os.path.getmtime(LOCK_FILE)
        if age > 600:
            print("⚠️ Removing stale lock file.")
            os.remove(LOCK_FILE)
        else:
            print("⚠️ Another CLI session is active.")
            sys.exit(1)

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    try:
        if not verify_davinci():
            print("Da Vinci verification failed.")
            return
        if is_connected_to_network():
            print("Connected.")
        else:
            print("No peers.")
        while True:
            if ROLE == "SERVER":
                print("1 — Start miner")
                print("2 — Skip (stay online)")
                print("3 — Exit and stop network")
                choice = input("Select option: ").strip()
                if choice == "1":
                    start_miner_with_address()
                elif choice == "2":
                    print("🟢 Staying connected. CLI exited.")
                    break
                elif choice == "3":
                    print("🔴 Stopping network services...")
                    os.system("./stop_all.sh")
                    break
                else:
                    print("Invalid option.")
            else:
                print("1 — Create wallet")
                print("2 — Restore wallet")
                print("3 — View history")
                print("4 — Skip (stay online)")
                choice = input("Select option: ").strip()
                if choice == "1":
                    create_wallet()
                elif choice == "2":
                    restore_wallet()
                elif choice == "3":
                    view_history()
                elif choice == "4":
                    print("🟢 Staying connected. CLI exited.")
                    break
                else:
                    print("Invalid option.")
    finally:
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except:
                pass


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "get-balance":
        addr = sys.argv[2]
        if is_valid_petoron_address(addr):
            print(f"Balance: {get_balance(addr)} ADC")
        else:
            print("Invalid address.")
        sys.exit(0)
    main()
