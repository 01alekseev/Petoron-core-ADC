import os
import core.prelaunch
import time
import threading
import struct
from collections import deque
from typing import List, Set, Dict

from core.pow import hash_transaction, mine_transaction_pow

MICRO_POW_PREFIX = "000"
MEMPOOL_FILE = "storage/mempool.bin"
LOST_TX_LOG = "logs/mempool_lost.log"

class Mempool:
    def __init__(self):
        self.pool: deque = deque()
        self.hashes: Set[str] = set()
        self.lock = threading.Lock()
        self.expiry_seconds = 300
        self.load_mempool_bin()

    def add_transaction(self, tx: Dict, source_ip: str = ""):
        tx_hash = tx.get("hash")
        if not tx_hash or not tx_hash.startswith(MICRO_POW_PREFIX):
            return
        with self.lock:
            if tx_hash in self.hashes:
                return
            self.pool.append({
                "tx": tx,
                "received_at": time.time(),
                "ip": source_ip,
                "retry_count": 0
            })
            self.hashes.add(tx_hash)
            self.save_mempool_bin()

    def get_pending_transactions(self, max_count: int = 1000) -> List[Dict]:
        now = time.time()
        with self.lock:
            txs = [
                entry["tx"]
                for entry in self.pool
                if now - entry["received_at"] <= self.expiry_seconds
            ]
        return txs[:max_count]

    def remove_transactions(self, tx_hashes: Set[str]):
        with self.lock:
            self.pool = deque([
                entry for entry in self.pool
                if entry["tx"].get("hash") not in tx_hashes
            ])
            self.hashes.difference_update(tx_hashes)
            self.save_mempool_bin()

    def clear_expired_transactions(self):
        now = time.time()
        changed = False
        with self.lock:
            new_pool = deque()
            for entry in self.pool:
                age = now - entry["received_at"]
                if age <= self.expiry_seconds:
                    new_pool.append(entry)
                else:
                    tx_hash = entry["tx"].get("hash")
                    if tx_hash:
                        self.hashes.discard(tx_hash)
                        self.log_lost_transaction(entry["tx"])
                        changed = True
            self.pool = new_pool
        if changed:
            self.save_mempool_bin()

    def retry_failed_transactions(self):
        now = time.time()
        with self.lock:
            for entry in list(self.pool):
                age = now - entry["received_at"]
                if age > 30 and age <= self.expiry_seconds:
                    entry["retry_count"] += 1
                    if entry["retry_count"] <= 3:
                        entry["tx"] = mine_transaction_pow(entry["tx"], prefix=MICRO_POW_PREFIX)
            self.save_mempool_bin()

    def log_lost_transaction(self, tx: Dict):
        try:
            os.makedirs(os.path.dirname(LOST_TX_LOG), exist_ok=True)
            with open(LOST_TX_LOG, "a") as f:
                f.write(f"LOST TX: {tx.get('hash')} → {tx.get('to')} | {tx.get('amount')}\n")
        except Exception as e:
            print(f"[LOG ERROR] Failed to log lost tx: {e}")

    def get_all(self) -> List[Dict]:
        with self.lock:
            return [
                {
                    "tx": entry["tx"],
                    "ip": entry.get("ip", "unknown"),
                    "received_at": entry["received_at"],
                    "retry_count": entry.get("retry_count", 0)
                }
                for entry in self.pool
            ]

    def loop(self):
        while True:
            self.clear_expired_transactions()
            self.retry_failed_transactions()
            time.sleep(5)

    def save_mempool_bin(self):
        with self.lock:
            with open(MEMPOOL_FILE, "wb") as f:
                f.write(struct.pack("<H", len(self.pool)))
                for entry in self.pool:
                    tx = entry["tx"]
                    ip = entry.get("ip", "")
                    received = entry.get("received_at", time.time())
                    retry = entry.get("retry_count", 0)
                    f.write(struct.pack("<H", len(tx)))
                    for k, v in tx.items():
                        f.write(self._encode_str(k))
                        f.write(self._encode_str(str(v)))
                    f.write(self._encode_str(ip))
                    f.write(struct.pack("<d", received))
                    f.write(struct.pack("<B", retry))

    def load_mempool_bin(self):
        if not os.path.exists(MEMPOOL_FILE):
            return
        try:
            with open(MEMPOOL_FILE, "rb") as f:
                data = f.read()
            offset = 0
            count = struct.unpack_from("<H", data, offset)[0]
            offset += 2
            for _ in range(count):
                tx = {}
                num_fields = struct.unpack_from("<H", data, offset)[0]
                offset += 2
                for _ in range(num_fields):
                    k, offset = self._decode_str(data, offset)
                    v, offset = self._decode_str(data, offset)
                    tx[k] = v
                ip, offset = self._decode_str(data, offset)
                received_at = struct.unpack_from("<d", data, offset)[0]
                offset += 8
                retry_count = struct.unpack_from("<B", data, offset)[0]
                offset += 1
                tx_hash = tx.get("hash")
                if tx_hash:
                    self.pool.append({
                        "tx": tx,
                        "received_at": received_at,
                        "ip": ip,
                        "retry_count": retry_count
                    })
                    self.hashes.add(tx_hash)
        except Exception as e:
            print(f"Failed to load mempool.bin: {e}")

    def _encode_str(self, s: str) -> bytes:
        b = s.encode("utf-8")
        return struct.pack("<H", len(b)) + b

    def _decode_str(self, data: bytes, offset: int) -> tuple[str, int]:
        length = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        val = data[offset:offset+length].decode("utf-8")
        return val, offset + length

global_mempool = Mempool()

threading.Thread(target=global_mempool.loop, daemon=True).start()
