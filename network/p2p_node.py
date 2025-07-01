import os
import time
import socket
import threading
import re
from datetime import datetime
from pathlib import Path
import base64
import hashlib

from core.serialization import (
    load_chain, save_chain,
    load_balances, save_balances,
    load_peers_bin, save_peers_bin,
    read_block_by_index,
    serialize_msg, deserialize_msg,
    serialize_block
)
from core.verifier import verifier_loop
from core.da_vinci import verify_davinci
from core.firewall import block_origin_check
from core.mempool import global_mempool, MICRO_POW_PREFIX
from core.transactions import (
    verify_transaction,
    hash_transaction,
    verify_transaction_with_balance,
    apply_transaction,
    validate_transaction_sequence
)
from core.blockchain import calculate_block_hash, verify_block_signature, is_peer_allowed
from network.autopeer import start_autopeer
from network.obfuscator import start_obfuscator
from pathlib import Path

if not Path("god_eye.locked").exists():
    print("⛔ Access denied. God Eye lock not present.")
    exit(1)

VERSION = "Petoron P2P v1.2.6"
LOCK_FILE = "network/node.lock"
ALIVE_FILE = "p2p_node_alive.txt"
LOG_FILE = "logs/node.log"
PEERS_FILE = "storage/peers.bin"
P2P_PORT = 5007

os.makedirs("logs", exist_ok=True)
os.makedirs("storage", exist_ok=True)
os.makedirs("network", exist_ok=True)

try:
    Path(LOCK_FILE).unlink(missing_ok=True)
except:
    pass

if Path(LOCK_FILE).exists():
    exit(0)
Path(LOCK_FILE).write_text("LOCKED")

def log(msg):
    timestamp = datetime.utcnow().isoformat() + "Z"
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def detect_ip():
    try:
        import urllib.request
        return urllib.request.urlopen("https://api.ipify.org").read().decode()
    except:
        return "0.0.0.0"

def is_valid_peer(peer: str) -> bool:
    return re.fullmatch(r"\d+\.\d+\.\d+\.\d+:\d{2,5}", peer.strip()) is not None

def update_peers():
    if os.getenv("IS_SERVER") != "1":
        log("\U0001f512 Client mode — not modifying peers.bin")
        return
    ip = detect_ip()
    if ip.startswith(("127.", "10.", "192.168.", "169.254.", "172.")) or ip.startswith("0."):
        return
    entry = f"{ip}:{P2P_PORT}"
    peers = set(p.strip() for p in load_peers_bin() if is_valid_peer(p))
    peers.add(entry)
    save_peers_bin(sorted(peers))
    log(f"✅ Server peer {entry} added to peers.bin")

def get_file_hash(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except:
        return ""

def send_file_request(filename):
    local_ip = detect_ip()
    for peer in load_peers_bin():
        if not is_valid_peer(peer):
            continue
        ip, port = peer.split(":")
        if ip == local_ip:
            continue
        try:
            with socket.create_connection((ip, int(port)), timeout=6) as s:
                msg = serialize_msg({"type": "file_request", "filename": filename})
                s.sendall(msg)
                s.shutdown(socket.SHUT_WR)
                data = bytearray()
                while True:
                    chunk = s.recv(8192)
                    if not chunk:
                        break
                    data.extend(chunk)
                if len(data) < 32:
                    log(f"⚠️ File {filename} from {ip} is too small ({len(data)} bytes)")
                    continue
                msg = deserialize_msg(data)
                if msg.get("type") == "file_response" and msg.get("filename") == filename:
                    decoded = base64.b64decode(msg["content"])
                    if len(decoded) < 32:
                        log(f"⚠️ Ignoring {filename} from {ip} — file too small ({len(decoded)} bytes)")
                        continue
                    path = f"storage/{filename}"
                    new_hash = hashlib.sha256(decoded).hexdigest()
                    old_hash = get_file_hash(path)
                    if new_hash != old_hash:
                        with open(path, "wb") as f:
                            f.write(decoded)
                        log(f"✅ Updated {filename} from {ip}")
                    else:
                        log(f"ℹ️ {filename} from {ip} is already up-to-date")
                    return True
        except Exception as e:
            log(f"❌ File request to {ip} failed: {str(e)}")
    return False

def auto_download():
    for name in ["chain.bin", "balances.bin", "daily_rewards.bin"]:
        send_file_request(name)

def sync_peers():
    local_peers = set(p.strip() for p in load_peers_bin() if is_valid_peer(p))
    for peer in local_peers:
        ip, port = peer.split(":")
        try:
            with socket.create_connection((ip, int(port)), timeout=6) as s:
                msg = serialize_msg({"type": "file_request", "filename": "peers.bin"})
                s.sendall(msg)
                s.shutdown(socket.SHUT_WR)
                data = bytearray()
                while True:
                    chunk = s.recv(8192)
                    if not chunk:
                        break
                    data.extend(chunk)
                msg = deserialize_msg(data)
                if msg.get("type") == "file_response" and msg.get("filename") == "peers.bin":
                    decoded = base64.b64decode(msg["content"])
                    new_peers = set(p.strip() for p in decoded.decode().split("\n") if is_valid_peer(p))
                    updated = local_peers.union(new_peers)
                    save_peers_bin(sorted(updated))
        except Exception as e:
            log(f"⚠️ Peer sync failed with {ip}: {e}")

def periodic_sync():
    while True:
        sync_peers()
        log("⏱ Wait 1 second before downloading other files")
        time.sleep(1)
        auto_download()
        time.sleep(120)

def handle_block(block):
    if not block_origin_check(block)[0]:
        return
    if not verify_block_signature(block):
        log("🚫 Invalid block signature — rejected")
        return
    if not is_peer_allowed(block.get("source_ip", "")):
        log("🚫 Block from unapproved peer — rejected")
        return
    chain = load_chain()
    if not chain:
        return
    if any(b.get("signature") == block.get("signature") for b in chain):
        log("🚫 Duplicate block signature — rejected")
        return
    if any(b["index"] == block["index"] for b in chain):
        return
    if block["previous_hash"] != chain[-1]["hash"]:
        return
    if block["hash"] != calculate_block_hash(block):
        return
    if not block["hash"].startswith(MICRO_POW_PREFIX):
        return
    if not validate_transaction_sequence(block.get("transactions", []))[0]:
        return
    seen = set()
    balances = load_balances()
    for tx in block["transactions"]:
        h = tx.get("hash")
        if not h or h in seen:
            return
        if hash_transaction(tx) != h:
            return
        if not verify_transaction_with_balance(tx, balances):
            return
        apply_transaction(tx, balances)
        seen.add(h)
    chain.append(block)
    save_chain(chain)
    save_balances(balances)

def handle_tx(tx, ip):
    if verify_transaction(tx) and hash_transaction(tx) == tx.get("hash"):
        global_mempool.add_transaction(tx, source_ip=ip)

def listener():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", P2P_PORT))
    except Exception as e:
        log(f"🔴 Listener failed to bind: {e}")
        return
    s.listen()
    log(f"🔌 Listening on TCP port {P2P_PORT}")
    while True:
        try:
            conn, addr = s.accept()
            ip = addr[0]
            data = bytearray()
            while True:
                chunk = conn.recv(8192)
                if not chunk:
                    break
                data.extend(chunk)
            if len(data) < 32:
                log(f"⚠️ Dropped short packet from {ip} ({len(data)} bytes)")
                conn.close()
                continue
            if not (data.startswith(b'\x80') or data.startswith(b'{') or b'"type"' in data[:64]):
                log(f"🚫 Rejected malformed or non-Petoron packet from {ip}")
                conn.close()
                continue
            try:
                msg = deserialize_msg(data)
            except Exception as e:
                log(f"❌ Failed to deserialize message from {ip}: {str(e)}")
                conn.close()
                continue
            t = msg.get("type")
            log(f"📥 Received {t} from {ip}")
            if t == "block":
                block_data = msg.get("data", {})
                block_data["source_ip"] = ip
                handle_block(block_data)
            elif t == "tx":
                handle_tx(msg.get("data", {}), ip)
            elif t == "file_request":
                name = msg.get("filename")
                path = f"storage/{name}"
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        content = f.read()
                    encoded = base64.b64encode(content).decode()
                    response = {
                        "type": "file_response",
                        "filename": name,
                        "content": encoded
                    }
                    conn.sendall(serialize_msg(response))
                    log(f"📤 Sent {name} ({len(content)} bytes) to {ip}")
                else:
                    log(f"❌ Requested file {name} not found for {ip}")
            elif t == "block_request":
                indexes = msg.get("indexes", [])
                blocks = []
                for i in indexes:
                    b = read_block_by_index(i)
                    if b:
                        blocks.append(b)
                conn.sendall(serialize_msg({"type": "block_response", "blocks": blocks}))
            elif t == "peer_announce":
                peer = msg.get("data", "")
                if is_valid_peer(peer):
                    peers = set(p.strip() for p in load_peers_bin() if is_valid_peer(p))
                    if peer not in peers:
                        peers.add(peer)
                        save_peers_bin(sorted(peers))
                        log(f"🤝 New peer announced and added: {peer}")
            conn.close()
        except Exception as e:
            log(f"⚠️ Listener error: {str(e)}")
            continue

def broadcast_block(block: dict):
    try:
        peers = load_peers_bin()
    except Exception as e:
        log(f"❌ Failed to load peers for broadcast: {e}")
        return
    msg = serialize_msg({"type": "block", "data": block})
    for peer in peers:
        if not is_valid_peer(peer):
            continue
        try:
            ip, port = peer.split(":")
            with socket.create_connection((ip, int(port)), timeout=6) as s:
                s.sendall(msg)
                log(f"📱 Block broadcasted to {ip}")
        except Exception as e:
            log(f"⚠️ Failed to broadcast to {ip}: {str(e)}")

def write_alive():
    with open(ALIVE_FILE, "w") as f:
        f.write(datetime.utcnow().isoformat() + "Z")

def start_node():
    if not verify_davinci():
        raise SystemExit("Access denied.")

    update_peers()
    auto_download()

    threading.Thread(target=verifier_loop, daemon=True).start()
    threading.Thread(target=start_autopeer, daemon=True).start()
    threading.Thread(target=start_obfuscator, daemon=True).start()
    threading.Thread(target=listener, daemon=True).start()
    threading.Thread(target=periodic_sync, daemon=True).start()

    try:
        while True:
            write_alive()
            time.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        Path(LOCK_FILE).unlink(missing_ok=True)

if __name__ == "__main__":
    start_node()
