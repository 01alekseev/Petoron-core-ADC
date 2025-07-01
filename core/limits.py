import os
import core.prelaunch
from decimal import Decimal, getcontext
from core.serialization import load_balances

getcontext().prec = 18

TOTAL_SUPPLY = Decimal("1000000000")
CREATOR_ALLOCATION = Decimal("50000000")
FUND_ALLOCATION = Decimal("5000000")

AVAILABLE_FOR_MINING = TOTAL_SUPPLY - CREATOR_ALLOCATION - FUND_ALLOCATION  # 945 млн

SECONDS_PER_DAY = Decimal("86400")

EXPONENT = Decimal("1.5")
BASE_NETWORK_LIMIT = Decimal("100000")
MAX_PER_MINER_DAILY = Decimal("24.0")

MIN_TXS_PER_BLOCK = 100
MAX_TXS_PER_BLOCK = 64000


def dynamic_daily_limit(total_minted: Decimal) -> Decimal:
    mined = max(total_minted - CREATOR_ALLOCATION - FUND_ALLOCATION, Decimal("0"))
    remaining = max(AVAILABLE_FOR_MINING - mined, Decimal("0"))
    ratio = remaining / AVAILABLE_FOR_MINING
    daily = BASE_NETWORK_LIMIT * (ratio ** EXPONENT)
    return daily.quantize(Decimal("0.00000001"))


def calculate_reward_per_second(total_minted: Decimal, active_miners: int) -> Decimal:
    if active_miners <= 0:
        return Decimal("0.0")
    network_limit = dynamic_daily_limit(total_minted)
    per_miner_limit = min(network_limit / Decimal(active_miners), MAX_PER_MINER_DAILY)
    per_second = per_miner_limit / SECONDS_PER_DAY
    return per_second.quantize(Decimal("0.00000001"))


def calculate_fee(amount: Decimal, total_minted: Decimal) -> Decimal:
    if total_minted < TOTAL_SUPPLY:
        return Decimal("0.0")
    base_fee = amount * Decimal("0.0001")  # 0.01%
    if amount > Decimal("100000"):
        base_fee *= Decimal("0.25")        # sale 75%
    elif amount > Decimal("10000"):
        base_fee *= Decimal("0.5")         # sale 50%
    return base_fee.quantize(Decimal("0.00000001"))


def get_total_supply(balances: dict = None) -> Decimal:
    if balances is None:
        balances = load_balances()
    return sum(Decimal(user.get("balance", 0)) for user in balances.values())


def calculate_max_txs_per_block(active_miners: int = 1) -> int:
    try:
        cpu_cores = int(os.getenv("SIMULATED_CPU_CORES") or os.cpu_count() or 1)
        ram_gb = int(os.getenv("SIMULATED_RAM_GB") or 4)
    except:
        cpu_cores = 1
        ram_gb = 4

    limit = 100 * cpu_cores * ram_gb
    if active_miners > 0:
        limit = int(limit / active_miners)
    return max(MIN_TXS_PER_BLOCK, min(limit, MAX_TXS_PER_BLOCK))

