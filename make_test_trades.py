#!/usr/bin/env python3
"""
Place a few small test trades via API and close some; leave others for manual close.
Uses MUDREX_API_SECRET from env. Run from repo root.
"""
import os
import sys
import time

def main():
    secret = os.environ.get("MUDREX_API_SECRET")
    if not secret:
        print("Set MUDREX_API_SECRET", file=sys.stderr)
        return 1

    from mudrex import MudrexClient

    client = MudrexClient(api_secret=secret)

    # Check balance
    try:
        fut = client.wallet.get_futures_balance()
        print(f"Futures balance: {fut.balance} USDT")
    except Exception as e:
        print(f"Balance check failed: {e}", file=sys.stderr)
        return 1

    # Small test pairs (low min notional)
    pairs = [
        ("DOGEUSDT", "50", "2"),   # ~$10–20 notional at 2x
        ("XRPUSDT", "10", "2"),   # ~$20 notional at 2x
    ]

    opened = []
    for symbol, qty, lev in pairs:
        try:
            order = client.orders.create_market_order(
                symbol=symbol,
                side="LONG",
                quantity=qty,
                leverage=lev,
            )
            print(f"Opened: {symbol} qty={qty} lev={lev} order_id={order.order_id}")
            opened.append((symbol, order.order_id))
            time.sleep(1.5)  # rate limit
        except Exception as e:
            print(f"Order failed {symbol}: {e}", file=sys.stderr)

    if not opened:
        print("No orders filled. Check balance and min size.")
        return 0

    time.sleep(3)  # let fills settle
    positions = client.positions.list_open()
    print(f"\nOpen positions: {len(positions)}")

    # Close first position via API; leave rest for manual close
    closed_via_api = 0
    for pos in positions:
        if closed_via_api >= 1:
            break
        try:
            client.positions.close(pos.position_id)
            print(f"Closed via API: {pos.symbol} position_id={pos.position_id}")
            closed_via_api += 1
            time.sleep(1.5)
        except Exception as e:
            print(f"Close failed {pos.symbol}: {e}", file=sys.stderr)

    remaining = client.positions.list_open()
    if remaining:
        print(f"\n--- Close these manually (app/web) ---")
        for pos in remaining:
            print(f"  {pos.symbol} position_id={pos.position_id} qty={pos.quantity}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
