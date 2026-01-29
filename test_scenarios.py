#!/usr/bin/env python3
"""
Run three volume/fees test scenarios:

1. Open via API + close via API
2. Open via API + you close manually (app/web)
3. Open with SL/TP via API + you change SL/TP in app and close

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

    try:
        fut = client.wallet.get_futures_balance()
        print(f"Futures balance: {fut.balance} USDT\n")
    except Exception as e:
        print(f"Balance check failed: {e}", file=sys.stderr)
        return 1

    # --- Scenario 1: Open via API, close via API ---
    print("=== Scenario 1: Open via API + close via API ===")
    try:
        order1 = client.orders.create_market_order(
            symbol="DOGEUSDT",
            side="LONG",
            quantity="50",
            leverage="2",
        )
        print(f"  Opened DOGEUSDT LONG 50 @ 2x order_id={order1.order_id}")
    except Exception as e:
        print(f"  Open failed: {e}", file=sys.stderr)
    else:
        time.sleep(4)
        positions = client.positions.list_open()
        # Close the first DOGE position (the one we just opened if only one)
        for pos in positions:
            if pos.symbol == "DOGEUSDT":
                try:
                    client.positions.close(pos.position_id)
                    print(f"  Closed via API: position_id={pos.position_id}")
                    break
                except Exception as e:
                    print(f"  Close failed: {e}", file=sys.stderr)
        time.sleep(1.5)

    # --- Scenario 2: Open via API, you close manually ---
    print("\n=== Scenario 2: Open via API + you close manually ===")
    try:
        order2 = client.orders.create_market_order(
            symbol="XRPUSDT",
            side="LONG",
            quantity="10",
            leverage="2",
        )
        print(f"  Opened XRPUSDT LONG 10 @ 2x order_id={order2.order_id}")
        print("  -> Close this position manually in Mudrex app/web.")
    except Exception as e:
        print(f"  Open failed: {e}", file=sys.stderr)
    time.sleep(1.5)

    # --- Scenario 3: Open with SL/TP via API, you change SL/TP and close ---
    print("\n=== Scenario 3: Open with SL/TP via API, you change SL/TP and close ===")
    try:
        # Use ARPAUSDT with amount to meet min order value; SL/TP far from market
        asset = client.assets.get("ARPAUSDT")
        price = float(asset.price or 0.05)
        sl = f"{price * 0.5:.4f}"
        tp = f"{price * 2.0:.4f}"
        order3 = client.orders.create_market_order(
            symbol="ARPAUSDT",
            side="LONG",
            quantity="500",
            leverage="2",
            stoploss_price=sl,
            takeprofit_price=tp,
        )
        print(f"  Opened ARPAUSDT LONG 500 @ 2x with SL={sl} TP={tp} order_id={order3.order_id}")
        print("  -> In app: change SL/TP if you like, then close the position manually.")
    except Exception as e:
        print(f"  Open failed: {e}", file=sys.stderr)

    print("\n--- Summary ---")
    positions = client.positions.list_open()
    print(f"  Open positions now: {len(positions)}")
    for pos in positions:
        print(f"    {pos.symbol} position_id={pos.position_id} qty={pos.quantity}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
