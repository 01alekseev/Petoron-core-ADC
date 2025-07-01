import os
import socket
import struct
import threading
import time
import random
from pathlib import Path

PEERS_FILE = "storage/peers.bin"
NOISE_INTERVAL = 20  # seconds
NOISE_TYPES = ["PING", "FAKE_TX", "EMPTY_BLOCK", "RANDOM"]

def load_peers():
    if not Path(PEERS_FILE).exists():
        return []
    with open(PEERS_FILE, "rb") as f:
        data = f.read()
    offset = 0
    count = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    peers = []
    for _ in range(count):
        length = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        peer = data[offset:offset + length].decode(errors="ignore")
        offset += length
        try:
            ip, port = peer.split(":")
            peers.append((ip, int(port)))
        except:
            continue
    return peers

def generate_ping():
    return b"PING"

def generate_fake_tx():
    payload = os.urandom(random.randint(64, 128))
    return b"FAKE_TX:" + payload

def generate_empty_block():
    dummy_index = random.randint(1000, 9999)
    dummy_hash = os.urandom(32).hex().encode()
    return b"EMPTY_BLOCK:" + struct.pack("<I", dummy_index) + dummy_hash

def generate_noise():
    t = random.choice(NOISE_TYPES)
    if t == "PING":
        return generate_ping()
    elif t == "FAKE_TX":
        return generate_fake_tx()
    elif t == "EMPTY_BLOCK":
        return generate_empty_block()
    return os.urandom(random.randint(64, 128))

def send_noise(ip, port):
    try:
        with socket.create_connection((ip, port), timeout=2) as s:
            noise = generate_noise()
            s.sendall(noise)
    except:
        pass

def noise_loop():
    while True:
        peers = load_peers()
        for ip, port in peers:
            if random.random() < 0.5:
                threading.Thread(target=send_noise, args=(ip, port), daemon=True).start()
        time.sleep(NOISE_INTERVAL + random.uniform(-5, 5))

def start_obfuscator():
    thread = threading.Thread(target=noise_loop, daemon=True)
    thread.start()
