import os
import socket
import time
import random
import threading
import pickle
from datetime import datetime

from core.serialization import load_peers_bin, save_peers_bin
from core.peers_trust import register_peer, is_peer_trusted, get_trusted_peers

PEERS_FILE = "storage/peers.bin"
LOG_FILE = "logs/autopeer.log"
PEER_TIMEOUT = 3
PEER_TTL_SEC = 300

os.makedirs("network", exist_ok=True)
os.makedirs("logs", exist_ok=True)

_lock = threading.Lock()

def log(message: str):
    timestamp = datetime.utcnow().isoformat()
    entry = f"[{timestamp}] 🌐 {message}"
    print(entry)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

def get_own_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "0.0.0.0"

def is_valid_peer(ip: str, port: int) -> bool:
    try:
        socket.inet_aton(ip)
        return ip != "0.0.0.0" and port > 0
    except:
        return False

def update_peers(ip: str, port: int):
    try:
        peers = load_peers_bin()
    except:
        peers = []

    found = False
    now = int(time.time())

    for peer in peers:
        if peer.get("host") == ip and peer.get("port") == port:
            peer["last_seen"] = now
            found = True
            break

    if not found:
        peers.append({"host": ip, "port": port, "last_seen": now})
        log(f"➕ Added peer: {ip}:{port}")

    save_peers_bin(peers)

def ping_peer(ip: str, port: int) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=PEER_TIMEOUT) as s:
            s.sendall(b"PING")
            resp = s.recv(4)
            return resp == b"PONG"
    except:
        return False

def measure_latency(ip: str, port: int) -> float:
    try:
        start = time.time()
        with socket.create_connection((ip, port), timeout=PEER_TIMEOUT) as s:
            s.sendall(b"PING")
            resp = s.recv(4)
            if resp == b"PONG":
                return time.time() - start
    except:
        pass
    return PEER_TIMEOUT + 1

def clean_dead_peers():
    try:
        peers = load_peers_bin()
    except:
        peers = []

    alive = []
    now = int(time.time())

    for peer in peers:
        ip = peer.get("host")
        port = peer.get("port")
        last_seen = peer.get("last_seen", 0)

        if now - last_seen > PEER_TTL_SEC:
            log(f"⏱️ Peer expired by TTL: {ip}:{port}")
            continue

        latency = measure_latency(ip, port)
        connected = random.randint(30, 600)
        is_stable = latency < 0.8

        trusted = register_peer(ip, latency, connected, is_stable)

        if trusted and ping_peer(ip, port):
            alive.append({"host": ip, "port": port, "last_seen": now})
        else:
            log(f"❌ Peer not trusted or not responding: {ip}:{port}")

    if len(alive) != len(peers):
        save_peers_bin(alive)
        log(f"🧹 Cleaned up dead peers. {len(alive)} remaining.")

def announce_self_to_peers(own_ip: str, port: int = 5007):
    try:
        peers = load_peers_bin()
    except:
        peers = []

    announce_msg = pickle.dumps({
        "type": "peer_announce",
        "data": f"{own_ip}:{port}"
    })

    for peer in peers:
        try:
            ip = peer.get("host")
            port = peer.get("port")
            with socket.create_connection((ip, port), timeout=2) as s:
                s.sendall(announce_msg)
        except:
            continue

def _autopeer_loop():
    own_ip = get_own_ip()
    log(f"🚀 Autopeer started. Own IP: {own_ip}")
    announce_self_to_peers(own_ip)

    while True:
        clean_dead_peers()
        time.sleep(30 + random.uniform(-5, 5))

def start_autopeer():
    with _lock:
        thread = threading.Thread(target=_autopeer_loop, daemon=True)
        thread.start()
