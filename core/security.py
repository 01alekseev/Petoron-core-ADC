import hashlib
import os
from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def double_sha256(data: bytes) -> str:
    return hashlib.sha256(hashlib.sha256(data).digest()).hexdigest()

def sign_message(private_key_hex: str, message: bytes) -> str:
    sk = SigningKey.from_string(bytes.fromhex(private_key_hex), curve=SECP256k1)
    signature = sk.sign(message)
    return signature.hex()

def verify_signature(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=SECP256k1)
        vk.verify(bytes.fromhex(signature_hex), message)
        return True
    except BadSignatureError:
        return False
    except Exception:
        return False

def generate_keypair() -> tuple[str, str]:
    sk = SigningKey.generate(curve=SECP256k1)
    pk = sk.get_verifying_key()
    return sk.to_string().hex(), pk.to_string().hex()

def file_hash(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    with open(path, "rb") as f:
        return sha256(f.read())

def file_hash_match(path: str, expected_hash: str) -> bool:
    actual = file_hash(path)
    return actual == expected_hash

def verify_block_signature(block_data: bytes, signature_hex: str, public_key_hex: str) -> bool:
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=SECP256k1)
        vk.verify(bytes.fromhex(signature_hex), block_data)
        return True
    except BadSignatureError:
        return False
    except Exception:
        return False
