import time
import socket
import threading
from collections import defaultdict

TRUSTED_PEERS = {}
PEER_HISTORY = defaultdict(list)
PEER_LOCK = threading.Lock()

TRUST_THRESHOLD = 3.0
BAN_DURATION = 3600

def subnet(ip):
    parts = ip.split('.')
    if len(parts) == 4:
        return '.'.join(parts[:3]) + '.0/24'
    return '0.0.0.0/0'

def evaluate_peer(ip, response_time, connected_seconds, is_stable):
    trust = 0.0

    if response_time < 0.5:
        trust += 1.0
    elif response_time < 1.0:
        trust += 0.5

    if connected_seconds > 300:
        trust += 1.0
    elif connected_seconds > 60:
        trust += 0.5

    if is_stable:
        trust += 1.0

    subnet_score = penalize_subnet(ip)
    trust -= subnet_score

    return round(trust, 3)

def penalize_subnet(ip):
    net = subnet(ip)
    with PEER_LOCK:
        count = sum(1 for peer in TRUSTED_PEERS if subnet(peer) == net)
    return max(0.0, (count - 2) * 0.5)

def register_peer(ip, response_time=0.3, connected_seconds=0, is_stable=True):
    now = time.time()
    with PEER_LOCK:
        score = evaluate_peer(ip, response_time, connected_seconds, is_stable)
        if score >= TRUST_THRESHOLD:
            TRUSTED_PEERS[ip] = {
                "score": score,
                "added": now
            }
            PEER_HISTORY[ip].append((now, score))
            return True
        else:
            if ip in TRUSTED_PEERS:
                del TRUSTED_PEERS[ip]
            return False

def is_peer_trusted(ip):
    with PEER_LOCK:
        if ip in TRUSTED_PEERS:
            if time.time() - TRUSTED_PEERS[ip]["added"] > BAN_DURATION:
                del TRUSTED_PEERS[ip]
                return False
            return True
        return False

def get_trusted_peers():
    with PEER_LOCK:
        return list(TRUSTED_PEERS.keys())

def clear_old_peers():
    now = time.time()
    with PEER_LOCK:
        for ip in list(TRUSTED_PEERS.keys()):
            if now - TRUSTED_PEERS[ip]["added"] > BAN_DURATION:
                del TRUSTED_PEERS[ip]

def log_trust_debug():
    print("=== TRUSTED PEERS ===")
    with PEER_LOCK:
        for ip, info in TRUSTED_PEERS.items():
            print(f"{ip} — score: {info['score']:.2f}, added: {int(time.time() - info['added'])}s ago")
