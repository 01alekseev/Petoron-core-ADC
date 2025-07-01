from typing import List, Dict
from core.serialization import calculate_block_hash

CHECKPOINT_INTERVAL = 50

def calculate_checkpoints(chain: List[dict], interval: int = CHECKPOINT_INTERVAL) -> Dict[int, str]:
    checkpoints = {}
    for block in chain:
        if block["index"] % interval == 0:
            checkpoints[block["index"]] = block["hash"]
    return checkpoints

def verify_chain_checkpoints(chain: List[dict], interval: int = CHECKPOINT_INTERVAL) -> bool:
    for block in chain:
        if block["index"] % interval == 0:
            recalculated = calculate_block_hash(block)
            if block["hash"] != recalculated:
                return False
    return True

def get_latest_checkpoint(chain: List[dict], interval: int = CHECKPOINT_INTERVAL) -> tuple[int, str]:
    checkpoints = calculate_checkpoints(chain, interval)
    if not checkpoints:
        return (0, "")
    max_index = max(checkpoints.keys())
    return (max_index, checkpoints[max_index])
