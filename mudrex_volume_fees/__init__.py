"""
Mudrex Futures Volume & Fees Calculator
======================================

Calculates API-sourced trading volume and estimated fees for Mudrex Futures.
Uses the Mudrex Trading API (https://docs.trade.mudrex.com/docs) via the
mudrex-api-trading-python-sdk.

Example:
    >>> from mudrex import MudrexClient
    >>> from mudrex_volume_fees import VolumeFeesCalculator
    >>> client = MudrexClient(api_secret="...")
    >>> calc = VolumeFeesCalculator(client=client, alpha_tier=0)
    >>> report = calc.calculate(since="2025-01-01", until="2025-01-30", symbol="BTCUSDT")
"""

from mudrex_volume_fees.calculator import VolumeFeesCalculator
from mudrex_volume_fees.tiers import AlphaTier, FEE_RATES

__all__ = ["VolumeFeesCalculator", "AlphaTier", "FEE_RATES"]
