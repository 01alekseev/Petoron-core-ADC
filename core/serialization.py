import os
import struct
import hashlib
from decimal import Decimal, InvalidOperation
from typing import List, Optional
import pickle
import re
import tempfile

from core import security
from core.peers_trust import register_peer, is_peer_trusted
from core.locks import FileLock

CHAIN_FILE = "storage/chain.bin"
BALANCES_FILE = "storage/balances.bin"
DAILY_REWARDS_FILE = "storage/daily_rewards.bin"
PEERS_FILE = "storage/peers.bin"

class DailyReward:
    def __init__(self, date: str, miner: str, amount: float):
        self.date = date
        self.miner = miner
        self.amount = amount

def serialize_msg(obj: dict) -> bytes:
    return pickle.dumps(obj)

def deserialize_msg(data: bytes) -> dict:
    return pickle.loads(data)

def encode_str(s: str) -> bytes:
    data = s.encode("utf-8")
    return struct.pack("<H", len(data)) + data

def decode_str(b: bytes, offset: int) -> tuple[str, int]:
    length = struct.unpack_from("<H", b, offset)[0]
    offset += 2
    raw = b[offset:offset + length]
    try:
        val = raw.decode("utf-8")
    except UnicodeDecodeError:
        val = raw.hex()
    return val, offset + length

def encode_decimal(val: Decimal) -> bytes:
    return encode_str(format(val, "f"))

def decode_decimal(b: bytes, offset: int) -> tuple[Decimal, int]:
    val_str, offset = decode_str(b, offset)
    try:
        return Decimal(val_str), offset
    except InvalidOperation:
        raise ValueError(f"Invalid decimal format: {val_str}")

def serialize_transaction(tx: dict) -> bytes:
    return b"".join([
        encode_str(tx.get("from", "")),
        encode_str(tx.get("to", "")),
        encode_decimal(Decimal(tx.get("amount", "0"))),
        struct.pack("<Q", tx.get("timestamp", 0)),
        encode_str(tx.get("nonce", "")),
        encode_str(tx.get("signature", "")),
        encode_str(tx.get("public_key", "")),
        encode_str(tx.get("hash", "")),
        encode_decimal(Decimal(tx.get("fee", "0")))
    ])

def deserialize_transaction(b: bytes, offset: int = 0) -> tuple[dict, int]:
    tx = {}
    tx["from"], offset = decode_str(b, offset)
    tx["to"], offset = decode_str(b, offset)
    tx["amount"], offset = decode_decimal(b, offset)
    tx["timestamp"] = struct.unpack_from("<Q", b, offset)[0]
    offset += 8
    tx["nonce"], offset = decode_str(b, offset)
    tx["signature"], offset = decode_str(b, offset)
    tx["public_key"], offset = decode_str(b, offset)
    tx["hash"], offset = decode_str(b, offset)
    tx["fee"], offset = decode_decimal(b, offset)
    return tx, offset

def serialize_block(block: dict) -> bytes:
    block_bytes = [
        struct.pack("<I", block.get("index", 0)),
        struct.pack("<Q", block.get("timestamp", 0)),
        encode_str(block.get("previous_hash", "")),
        struct.pack("<H", len(block.get("transactions", [])))
    ]
    for tx in block.get("transactions", []):
        block_bytes.append(serialize_transaction(tx))
    block_bytes.append(encode_str(block.get("hash", "")))
    block_bytes.append(encode_str(block.get("miner", "")))
    block_bytes.append(struct.pack("<Q", block.get("nonce", 0)))
    block_data = b"".join(block_bytes)
    return struct.pack("<I", len(block_data)) + block_data

def deserialize_block(b: bytes, offset: int = 0) -> tuple[dict, int]:
    block_size = struct.unpack_from("<I", b, offset)[0]
    offset += 4
    block = {}
    block["index"] = struct.unpack_from("<I", b, offset)[0]
    offset += 4
    block["timestamp"] = struct.unpack_from("<Q", b, offset)[0]
    offset += 8
    block["previous_hash"], offset = decode_str(b, offset)
    tx_count = struct.unpack_from("<H", b, offset)[0]
    offset += 2
    block["transactions"] = []
    for _ in range(tx_count):
        tx, offset = deserialize_transaction(b, offset)
        block["transactions"].append(tx)
    block["hash"], offset = decode_str(b, offset)
    block["miner"], offset = decode_str(b, offset)
    block["nonce"] = struct.unpack_from("<Q", b, offset)[0]
    offset += 8
    return block, offset

def serialize_balances(balances: dict) -> bytes:
    out = [struct.pack("<H", len(balances))]
    for address, data in balances.items():
        out.append(encode_str(address))
        out.append(encode_decimal(Decimal(data["balance"])))
    return b"".join(out)

def deserialize_balances(b: bytes) -> dict:
    offset = 0
    count = struct.unpack_from("<H", b, offset)[0]
    offset += 2
    balances = {}
    for _ in range(count):
        addr, offset = decode_str(b, offset)
        val, offset = decode_decimal(b, offset)
        balances[addr] = {"balance": val}
    return balances

def load_balances() -> dict:
    if not os.path.exists(BALANCES_FILE):
        return {}
    with open(BALANCES_FILE, "rb") as f:
        return deserialize_balances(f.read())

def save_balances(balances: dict):
    with FileLock(BALANCES_FILE):
        temp = BALANCES_FILE + ".tmp"
        with open(temp, "wb") as f:
            f.write(serialize_balances(balances))
        os.replace(temp, BALANCES_FILE)

def load_chain() -> List[dict]:
    if not os.path.exists(CHAIN_FILE):
        return []
    chain = []
    with open(CHAIN_FILE, "rb") as f:
        while True:
            size_data = f.read(4)
            if len(size_data) < 4:
                break
            block_size = struct.unpack("<I", size_data)[0]
            block_data = f.read(block_size)
            if len(block_data) < block_size:
                break
            try:
                full_block = size_data + block_data
                block, _ = deserialize_block(full_block, 0)
                chain.append(block)
            except Exception:
                break
    return chain

def append_block_to_chain(block: dict):
    refresh_chain()
    with FileLock(CHAIN_FILE):
        with open(CHAIN_FILE, "ab") as f:
            f.write(serialize_block(block))

def save_chain(chain: List[dict]):
    refresh_chain()
    with FileLock(CHAIN_FILE):
        temp = CHAIN_FILE + ".tmp"
        with open(temp, "wb") as f:
            for block in chain:
                f.write(serialize_block(block))
        os.replace(temp, CHAIN_FILE)

def read_block_by_index(index: int) -> Optional[dict]:
    if not os.path.exists(CHAIN_FILE):
        return None
    with open(CHAIN_FILE, "rb") as f:
        while True:
            size_data = f.read(4)
            if len(size_data) < 4:
                break
            block_size = struct.unpack("<I", size_data)[0]
            block_data = f.read(block_size)
            if len(block_data) < block_size:
                break
            try:
                full_block = size_data + block_data
                block, _ = deserialize_block(full_block, 0)
                if block["index"] == index:
                    return block
            except Exception:
                continue
    return None

def load_daily_rewards() -> dict:
    if not os.path.exists(DAILY_REWARDS_FILE):
        return {}
    rewards = {}
    with open(DAILY_REWARDS_FILE, "rb") as f:
        data = f.read()
    offset = 0
    while offset < len(data):
        try:
            date, offset = decode_str(data, offset)
            miner, offset = decode_str(data, offset)
            amount, offset = decode_decimal(data, offset)
            rewards[miner] = rewards.get(miner, Decimal("0")) + amount
        except Exception:
            break
    return rewards

def load_daily_rewards_bin() -> dict:
    if not os.path.exists(DAILY_REWARDS_FILE):
        return {}
    with open(DAILY_REWARDS_FILE, "rb") as f:
        try:
            return pickle.load(f)
        except:
            return {}

def save_daily_rewards_bin(rewards: dict):
    with FileLock(DAILY_REWARDS_FILE):
        temp = DAILY_REWARDS_FILE + ".tmp"
        with open(temp, "wb") as f:
            pickle.dump(rewards, f)
        os.replace(temp, DAILY_REWARDS_FILE)

def is_valid_peer(peer: str) -> bool:
    return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}:\d{2,5}$", peer.strip()))

def save_peers_bin(peers: List[str]):
    cleaned = [p.strip() for p in peers if p.strip()]
    valid = [p for p in cleaned if is_valid_peer(p)]

    trusted = []
    for peer in valid:
        try:
            ip, port = peer.split(":")
            port = int(port)
            if register_peer(ip, response_time=0.2, connected_seconds=300, is_stable=True):
                trusted.append(peer)
        except:
            continue

    unique_peers = list(set(trusted))
    with FileLock(PEERS_FILE):
        temp = PEERS_FILE + ".tmp"
        with open(temp, "wb") as f:
            f.write(struct.pack("<H", len(unique_peers)))
            for peer in unique_peers:
                f.write(encode_str(peer))
        os.replace(temp, PEERS_FILE)

def load_peers_bin() -> List[str]:
    if not os.path.exists(PEERS_FILE):
        return []
    with open(PEERS_FILE, "rb") as f:
        data = f.read()
    offset = 0
    count = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    peers = []
    for _ in range(count):
        peer, offset = decode_str(data, offset)
        if peer and is_valid_peer(peer):
            try:
                ip, port = peer.split(":")
                port = int(port)
                if is_peer_trusted(ip):
                    peers.append(peer)
            except:
                continue
    return peers

def calculate_block_hash(block: dict) -> str:
    block_copy = {
        "index": block["index"],
        "timestamp": block["timestamp"],
        "previous_hash": block["previous_hash"],
        "transactions": block["transactions"],
        "miner": block.get("miner", ""),
        "nonce": block["nonce"]
    }
    return hashlib.sha256(serialize_block(block_copy)).hexdigest()

def refresh_chain():
    try:
        from network.p2p_node import send_file_request
        send_file_request("chain.bin")
    except:
        pass
