#!/usr/bin/env python3
"""
Local edge-case test: runs the calculator with a mock client so we can
trigger H1/H2/H3/H4/H7 without a real API secret. Writes to .cursor/debug.log.
"""

from datetime import datetime


class MockClient:
    """Minimal client that returns controlled order/fee history."""

    def get(self, endpoint: str, params: dict):
        if "orders/history" in endpoint:
            # Page 1: mix of valid, missing created_at, and odd data
            page = params.get("page", 1)
            if page == 1:
                return {
                    "data": {
                        "items": [
                            {
                                "order_id": "ord-1",
                                "symbol": "BTCUSDT",
                                "status": "FILLED",
                                "filled_quantity": "0.001",
                                "price": "50000",
                                "created_at": "2025-01-15T12:00:00Z",
                                "source": "API",
                            },
                            {
                                "order_id": "ord-2",
                                "symbol": "ETHUSDT",
                                "status": "FILLED",
                                "filled_quantity": "0.1",
                                "price": "3000",
                                "created_at": None,  # missing -> H1
                            },
                            {
                                "order_id": "ord-3",
                                "symbol": "BTCUSDT",
                                "status": "OPEN",
                                "filled_quantity": "0",
                                "price": "50000",
                                "created_at": "2025-01-20T00:00:00",
                            },
                        ]
                    }
                }
            return {"data": {"items": []}}

    @property
    def fees(self):
        return self

    def get_history(self, limit=None, symbol=None):
        # Fee with missing created_at -> H7 (use simple objects with .created_at, .fee_amount)
        class F:
            pass
        f1, f2 = F(), F()
        f1.fee_amount = "0.25"
        f1.created_at = "2025-01-15T12:01:00Z"
        f2.fee_amount = "0.10"
        f2.created_at = None  # missing -> H7
        return [f1, f2]


def main():
    from mudrex_volume_fees import VolumeFeesCalculator

    client = MockClient()
    calc = VolumeFeesCalculator(client=client, alpha_tier=2, count_only_api_sourced=True)
    report = calc.calculate(
        since="2025-01-01",
        until="2025-01-31",
        symbol=None,
        limit=50,
        include_actual_fees=True,
    )
    print("Report:", report)
    print("total_volume:", report["total_volume"])
    print("order_count:", report["order_count"])
    print("actual_fees" in report and report.get("actual_fees"))


if __name__ == "__main__":
    main()
