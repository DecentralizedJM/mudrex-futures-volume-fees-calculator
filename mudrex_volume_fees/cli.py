#!/usr/bin/env python3
"""
CLI for Mudrex Futures Volume & Fees Calculator.

Usage:
  python -m mudrex_volume_fees --api-secret YOUR_SECRET --since 2025-01-01 --until 2025-01-30
  python -m mudrex_volume_fees --api-secret YOUR_SECRET --symbol BTCUSDT --alpha-tier 2

API secret can also be set via MUDREX_API_SECRET.
"""

import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Calculate API volume and estimated fees for Mudrex Futures (docs.trade.mudrex.com)"
    )
    parser.add_argument(
        "--api-secret",
        default=os.environ.get("MUDREX_API_SECRET"),
        help="Mudrex API secret (or set MUDREX_API_SECRET)",
    )
    parser.add_argument(
        "--since",
        metavar="DATE",
        help="Start date (YYYY-MM-DD or ISO datetime)",
    )
    parser.add_argument(
        "--until",
        metavar="DATE",
        help="End date (YYYY-MM-DD or ISO datetime)",
    )
    parser.add_argument(
        "--symbol",
        metavar="SYMBOL",
        help="Filter by symbol (e.g. BTCUSDT, XAUTUSDT)",
    )
    parser.add_argument(
        "--alpha-tier",
        type=int,
        default=0,
        choices=range(7),
        metavar="0-6",
        help="Alpha tier: 0=Non-Alpha (0.05%%), 1=Alpha1 (0.048%%), ..., 6=Alpha6 (0.030%%)",
    )
    parser.add_argument(
        "--all-volume",
        action="store_true",
        help="Count all filled orders (do not filter by API source)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of order history records to fetch (default: all)",
    )
    args = parser.parse_args()

    if not args.api_secret:
        print("Error: --api-secret or MUDREX_API_SECRET is required", file=sys.stderr)
        return 1

    try:
        from mudrex import MudrexClient
        from mudrex_volume_fees import VolumeFeesCalculator
    except ImportError as e:
        print(f"Error: {e}. Install: pip install -e .", file=sys.stderr)
        return 1

    client = MudrexClient(api_secret=args.api_secret)
    calc = VolumeFeesCalculator(
        client=client,
        alpha_tier=args.alpha_tier,
        count_only_api_sourced=not args.all_volume,
    )
    report = calc.calculate(
        since=args.since,
        until=args.until,
        symbol=args.symbol or None,
        limit=args.limit,
    )

    print("Mudrex Futures Volume & Fees Report")
    print("------------------------------------")
    if args.since or args.until:
        print(f"  Period: {args.since or 'start'} to {args.until or 'now'}")
    if args.symbol:
        print(f"  Symbol: {args.symbol}")
    print(f"  Alpha tier: {args.alpha_tier} ({report['fee_rate_pct']}% fee)")
    print(f"  Order count: {report['order_count']}")
    print(f"  Total volume (notional): ${report['total_volume']:,.2f}")
    print(f"  Estimated fees: ${report['estimated_fees']:,.2f}")
    if report.get("by_symbol"):
        print("  By symbol:")
        for sym, vol in sorted(report["by_symbol"].items(), key=lambda x: -x[1]):
            print(f"    {sym}: ${vol:,.2f}")
    if not report.get("source_available"):
        print("  Note: Order source not in API response; all filled orders in range were counted.")
    return 0


def run() -> None:
    """Entry point for console script."""
    sys.exit(main())


if __name__ == "__main__":
    run()
