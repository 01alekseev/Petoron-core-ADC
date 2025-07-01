import os

def ensure_storage():
    if not os.path.exists("storage"):
        os.makedirs("storage")

def ensure_files():
    essential_files = ["chain.bin", "balances.bin"]
    for f in essential_files:
        path = os.path.join("storage", f)
        if not os.path.isfile(path):
            with open(path, "wb") as fp:
                fp.write(b"")

ensure_storage()
ensure_files()

