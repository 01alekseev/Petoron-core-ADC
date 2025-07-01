import core.prelaunch
from wallet import Wallet
from core.serialization import load_balances

def check_balance():
    print("🔐 Step 1: Enter the move sequence for Cube A:")
    sequence_a = input("A: ").strip().split()
    print("🧠 Step 2: Enter the move sequence for Cube B:")
    sequence_b = input("B: ").strip().split()

    wallet = Wallet(sequence_a, sequence_b)
    address = wallet.get_address()

    balances = load_balances()
    balance_data = balances.get(address, {"balance": 0})
    balance = balance_data["balance"] if isinstance(balance_data, dict) else balance_data

    print("🔍 Wallet address:", address)
    print(f"💰 Balance: {balance} ADC")

if __name__ == "__main__":
    check_balance()
