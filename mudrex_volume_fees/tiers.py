"""
Alpha tier fee rates for Mudrex Futures.
Reference: https://docs.trade.mudrex.com/docs
"""

from enum import IntEnum
from typing import Dict


class AlphaTier(IntEnum):
    """Alpha tier index. User selects their tier for fee calculation."""

    NON_ALPHA = 0  # Base
    ALPHA_1 = 1
    ALPHA_2 = 2
    ALPHA_3 = 3
    ALPHA_4 = 4
    ALPHA_5 = 5
    ALPHA_6 = 6


# Fee rate as percentage (e.g. 0.05 means 0.05%)
FEE_RATES: Dict[AlphaTier, float] = {
    AlphaTier.NON_ALPHA: 0.05,
    AlphaTier.ALPHA_1: 0.048,
    AlphaTier.ALPHA_2: 0.045,
    AlphaTier.ALPHA_3: 0.045,
    AlphaTier.ALPHA_4: 0.040,
    AlphaTier.ALPHA_5: 0.035,
    AlphaTier.ALPHA_6: 0.030,
}


def get_fee_rate(tier: AlphaTier) -> float:
    """Return fee percentage for the given tier."""
    return FEE_RATES.get(AlphaTier(tier), FEE_RATES[AlphaTier.NON_ALPHA])
