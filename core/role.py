import os

def is_server_node() -> bool:
    return os.environ.get("PETORON_ROLE", "").lower() == "server"
