import os
import core.prelaunch

import time
from collections import defaultdict, deque

TX_WINDOW_SECONDS = 60
TX_MAX_PER_ADDRESS = 5
class AntiSpam:
    def __init__(self):
        self.history = defaultdict(deque)
    def check_and_register(self, sender: str, timestamp: int) -> bool:
        q = self.history[sender]
        now = timestamp or int(time.time())
        while q and now - q[0] > TX_WINDOW_SECONDS:
            q.popleft()
        if len(q) >= TX_MAX_PER_ADDRESS:
            return False
        q.append(now)
        return True
global_antispam = AntiSpam()
