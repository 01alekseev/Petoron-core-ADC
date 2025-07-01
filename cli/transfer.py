import argparse
import socket
import time
from decimal import Decimal
from core.security import sign_message
from core.transactions import hash_transaction
from core.serialization import serialize_msg

DEFAULT_P2P_PORT = 5007

def create_transaction(sender, recipient, amount, privkey_hex, nonce, fee):
    timestamp = int(time.time())
    tx = {
        "from": sender,
        "to": recipient,
        "amount": str(Decimal(amount)),
        "timestamp": timestamp,
        "nonce": nonce,
        "public_key": "",
        "signature": "",
        "hash": "",
        "fee": str(Decimal(fee))
    }

    message = f"{sender}{recipient}{amount}{timestamp}{nonce}{fee}".encode()
    signature = sign_message(privkey_hex, message)
    tx["signature"] = signature
    tx["hash"] = hash_transaction(tx)

    return tx

def send_transaction(tx, peer_ip, peer_port=DEFAULT_P2P_PORT):
    try:
        with socket.create_connection((peer_ip, peer_port), timeout=5) as s:
            msg = {
                "type": "transaction",
                "data": tx
            }
            s.sendall(serialize_msg(msg))
        print(f"[OK] Transaction sent to {peer_ip}:{peer_port}")
    except Exception as e:
        print(f"[ERROR] Failed to send transaction: {e}")

def main():
    parser = argparse.ArgumentParser(description="Send a Petoron transaction")
    parser.add_argument("--from", dest="sender", required=True, help="Sender address")
    parser.add_argument("--to", required=True, help="Recipient address")
    parser.add_argument("--amount", required=True, help="Amount to send (decimal)")
    parser.add_argument("--private-key", required=True, help="Sender's private key (hex)")
    parser.add_argument("--nonce", required=True, help="Unique nonce for transaction")
    parser.add_argument("--fee", default="0.0001", help="Transaction fee (default: 0.0001)")
    parser.add_argument("--peer", default="127.0.0.1", help="Peer IP to send to (default: localhost)")
    parser.add_argument("--port", type=int, default=DEFAULT_P2P_PORT, help="Peer port (default: 5007)")

    args = parser.parse_args()

    tx = create_transaction(
        sender=args.sender,
        recipient=args.to,
        amount=args.amount,
        privkey_hex=args.private_key,
        nonce=args.nonce,
        fee=args.fee
    )

    print("[INFO] Transaction created:")
    for k, v in tx.items():
        print(f"  {k}: {v}")

    send_transaction(tx, args.peer, args.port)

if __name__ == "__main__":
    main()
