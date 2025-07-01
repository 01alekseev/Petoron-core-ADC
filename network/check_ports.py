# check_ports.py
# This is a helper script for Petoron network participants
# It checks if your local port (default: 5007) is open
# If the port is closed, please open it so your node can connect to the network properly.

import socket

PORT = 5007  # Default Petoron P2P port

def check_port(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

if __name__ == "__main__":
    is_open = check_port(PORT)
    if is_open:
        print(f"✅ Port {PORT} is OPEN on your local machine. You're ready to connect.")
    else:
        print(f"🛑 Port {PORT} is CLOSED. Please open the port to enable network connection.")

