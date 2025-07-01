PEERS_FILE = "storage/peers.bin"

try:
    with open(PEERS_FILE, "rb") as f:
        raw = f.read()

    if len(raw) <= 4:
        print("❌ peers.bin is too short or malformed.")
        exit(1)

    peers_data = raw[4:].decode("utf-8")
    peers = peers_data.strip().split(";") if ";" in peers_data else [peers_data]

    print("🌐 Discovered Peers:")
    for p in peers:
        print("  •", p)

except Exception as e:
    print(f"❌ Error reading peers.bin: {e}")

