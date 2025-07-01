import os
import core.prelaunch  # если нужно, оставляем

import random
import hashlib

FACES = ['W', 'R', 'B', 'O', 'G', 'Y']
TURNS = ['U', 'D', 'L', 'R', 'F', 'B']
WRAPPERS = ["", "'"]

def generate_random_sequence(length: int = 16) -> list:
    sequence = []
    for _ in range(length):
        turn = random.choice(TURNS)
        wrapper = random.choice(WRAPPERS)
        move = f"{turn}{wrapper}" if wrapper else turn
        sequence.append(move)
    return sequence

def sequence_to_state_secure(sequence: list) -> str:
    seed = ' '.join(sequence)
    hash_digest = hashlib.sha256(seed.encode()).digest()

    state = []
    while len(state) < 54:
        for byte in hash_digest:
            if len(state) < 54:
                state.append(FACES[byte % len(FACES)])
        hash_digest = hashlib.sha256(hash_digest).digest()
    return ''.join(state)

class Cube:
    def __init__(self, sequence=None):
        self.sequence = sequence or []
        self.state = sequence_to_state_secure(self.sequence)

    def apply_move(self, move: str):
        return Cube(sequence=self.sequence + [move])

    def to_string(self) -> str:
        return self.state

