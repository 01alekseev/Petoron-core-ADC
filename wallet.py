import hashlib
import sys
import inspect
import random
import secrets
from core.cube import Cube, generate_random_sequence

VALID_MOVES = {"U", "D", "L", "R", "F", "B", "U'", "D'", "L'", "R'", "F'", "B'"}

def _check_caller():
    stack = inspect.stack()
    for frame in stack:
        if frame.filename.endswith("interface.py"):
            return True
    raise PermissionError("Unauthorized module access: Wallet can be used only via interface.py")

def validate_moves_sequence(seq):
    if not isinstance(seq, list):
        return False
    if len(seq) != 16:
        return False
    return all(move in VALID_MOVES for move in seq)

class Wallet:
    def __init__(self, sequence_a, sequence_b, salt=None):
        _check_caller()

        if not validate_moves_sequence(sequence_a) or not validate_moves_sequence(sequence_b):
            raise ValueError("Invalid wallet sequences: each sequence must be a list of 16 valid moves")

        if sequence_a == sequence_b:
            raise ValueError("Cube A and Cube B must not be identical")

        self.sequence_a = sequence_a
        self.sequence_b = sequence_b

        self.cube_a = Cube()
        for move in sequence_a:
            self.cube_a = self.cube_a.apply_move(move)

        self.cube_b = Cube()
        for move in sequence_b:
            self.cube_b = self.cube_b.apply_move(move)

        self.salt = salt or secrets.token_hex(8)

        combined_state = self._combined_cube_state()
        salted_input = (combined_state + self.salt).encode()
        self.address = hashlib.sha256(salted_input).hexdigest()

    def _combined_cube_state(self):
        state_a = self.cube_a.to_string()
        state_b = self.cube_b.to_string()
        if secrets.randbelow(2):
            return state_a + state_b
        else:
            return state_b + state_a

    def get_address(self):
        return self.address

    def get_public_key(self):
        return ' | '.join([' '.join(self.sequence_a), ' '.join(self.sequence_b)])

    def sign(self, data: bytes) -> bytes:
        key_material = self.sequence_a + self.sequence_b
        if secrets.randbelow(2):
            key_material = self.sequence_b + self.sequence_a
        salted_key = ''.join(key_material) + self.salt
        return hashlib.sha256(salted_key.encode() + data).digest()

    def export(self):
        return {
            "address": self.get_address(),
            "sequence_a": self.sequence_a,
            "sequence_b": self.sequence_b,
            "salt": self.salt
        }

def _generate_fake_padding():
    return [random.choice(list(VALID_MOVES)) for _ in range(random.randint(0, 3))]

def create_wallet():
    _check_caller()

    while True:
        seq_a = generate_random_sequence()
        seq_b = generate_random_sequence()
        if seq_a != seq_b:
            break

    if not validate_moves_sequence(seq_a) or not validate_moves_sequence(seq_b):
        raise RuntimeError("Generated wallet sequences length mismatch or invalid moves")

    # fake padding (obfuscation)
    fake_prefix_a = _generate_fake_padding()
    fake_suffix_a = _generate_fake_padding()
    fake_prefix_b = _generate_fake_padding()
    fake_suffix_b = _generate_fake_padding()

    final_seq_a = fake_prefix_a + seq_a + fake_suffix_a
    final_seq_b = fake_prefix_b + seq_b + fake_suffix_b

    trimmed_a = final_seq_a[-16:]
    trimmed_b = final_seq_b[-16:]

    salt = secrets.token_hex(8)
    wallet = Wallet(trimmed_a, trimmed_b, salt=salt)

    print("✅ Wallet created!")
    print(f"🧩 Cube A: {' '.join(trimmed_a)}")
    print(f"🧩 Cube B: {' '.join(trimmed_b)}")
    print(f"🔑 Address: {wallet.get_address()}")
    print("⚠️ Save both sequences. Without them, access is impossible.\n")

    return wallet

if __name__ == "__main__":
    create_wallet()
