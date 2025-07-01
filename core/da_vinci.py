# 🧠 Made for people - Petoron (ADC) by Ivan Alekseev 2025

import hashlib
DA_VINCI_SIGNATURE = "adsp.peteron.protectednetworkonly"
EXPECTED_HASH = hashlib.sha256(DA_VINCI_SIGNATURE.encode("utf-8")).hexdigest()
def verify_davinci() -> bool:
    actual_hash = hashlib.sha256(DA_VINCI_SIGNATURE.encode("utf-8")).hexdigest()
    return actual_hash == EXPECTED_HASH
