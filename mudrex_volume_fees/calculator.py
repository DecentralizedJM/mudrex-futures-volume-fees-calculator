"""
Volume and fee calculator for Mudrex Futures API-sourced orders.

Fetches raw order history from the Mudrex API (Order history: https://docs.trade.mudrex.com),
filters by time/symbol and optionally by order source (API vs manual), and computes
notional volume and estimated fees by alpha tier.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from mudrex_volume_fees.tiers import AlphaTier, get_fee_rate


# Keys the API might use for order source (API vs web/ios/android)
SOURCE_KEYS = ("source", "order_source", "origin")


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        if value > 1e12:
            value = value / 1000
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return None


def _is_api_sourced(order: Dict[str, Any]) -> bool:
    """True if order appears to be API-sourced. If no source field, returns True (count all)."""
    for key in SOURCE_KEYS:
        v = order.get(key)
        if v is None:
            continue
        s = str(v).upper()
        if s in ("API", "1", "TRUE"):
            return True
        if s in ("WEB", "IOS", "ANDROID", "MANUAL", "0", "FALSE"):
            return False
    return True  # unknown -> include (all-volume mode when API doesn't expose source)


def _order_volume_contribution(order: Dict[str, Any]) -> float:
    """Notional volume for one order: filled_quantity * price."""
    filled = order.get("filled_quantity") or order.get("filled_size") or "0"
    price = order.get("price") or order.get("order_price") or "0"
    try:
        return float(filled) * float(price)
    except (ValueError, TypeError):
        return 0.0


def _order_is_filled(order: Dict[str, Any]) -> bool:
    status = (order.get("status") or "").upper()
    return status in ("FILLED", "PARTIALLY_FILLED")


def fetch_raw_order_history(
    client: Any,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch raw order history from Mudrex API (Order history endpoint).
    Returns list of raw order dicts so we can read source/order_source if present.
    """
    out: List[Dict[str, Any]] = []
    page = 1
    per_page = 100
    while True:
        resp = client.get("/futures/orders/history", {"page": page, "per_page": per_page})
        data = resp.get("data", resp)
        if isinstance(data, list):
            items = data
        else:
            items = data.get("items", data.get("data", []))
        if not items:
            break
        for item in items:
            if isinstance(item, dict):
                out.append(item)
        if limit and len(out) >= limit:
            return out[:limit]
        if len(items) < per_page:
            break
        page += 1
    return out


class VolumeFeesCalculator:
    """
    Calculate API volume and estimated fees for Mudrex Futures.

    Uses an existing MudrexClient so it integrates with any user pybot.
    Volume = notional (filled_quantity * price) per filled order; only orders
    with API source are counted when the API returns a source field.
    """

    def __init__(
        self,
        client: Any,
        alpha_tier: Union[int, AlphaTier] = 0,
        count_only_api_sourced: bool = True,
    ):
        """
        Args:
            client: MudrexClient instance (from mudrex SDK).
            alpha_tier: 0 = Non-Alpha (0.05%), 1--6 = Alpha 1--6.
            count_only_api_sourced: If True, only count orders where source is API
                (when API provides source). If False, count all filled orders in range.
        """
        self._client = client
        self._alpha_tier = AlphaTier(int(alpha_tier))
        self._count_only_api_sourced = count_only_api_sourced

    def calculate(
        self,
        since: Optional[Union[datetime, str]] = None,
        until: Optional[Union[datetime, str]] = None,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Compute volume and estimated fees for the given filters.

        Args:
            since: Start of time range (inclusive). datetime or ISO date string.
            until: End of time range (inclusive). datetime or ISO date string.
            symbol: Optional symbol filter (e.g. "BTCUSDT", "XAUTUSDT").
            limit: Optional max number of history orders to fetch (default: all).

        Returns:
            Dict with: total_volume, estimated_fees, fee_rate_pct, order_count,
            by_symbol (volume per symbol), source_available (whether source was used).
        """
        raw_orders = fetch_raw_order_history(self._client, limit=limit)
        since_dt = _parse_dt(since) if since else None
        until_dt = _parse_dt(until) if until else None
        symbol_norm = (symbol or "").strip().upper() or None

        total_volume = 0.0
        by_symbol: Dict[str, float] = {}
        order_count = 0
        source_available = False

        for order in raw_orders:
            created = _parse_dt(order.get("created_at"))
            if since_dt and created and created < since_dt:
                continue
            if until_dt and created and created > until_dt:
                continue
            sym = (order.get("symbol") or order.get("asset_id") or "").strip()
            if symbol_norm and sym.upper() != symbol_norm:
                continue
            if not _order_is_filled(order):
                continue
            if self._count_only_api_sourced and not _is_api_sourced(order):
                continue  # skip non-API when filtering by source
            # Track if we ever saw a source-like field
            for k in SOURCE_KEYS:
                if order.get(k) is not None:
                    source_available = True
                    break
            vol = _order_volume_contribution(order)
            if vol <= 0:
                continue
            total_volume += vol
            order_count += 1
            if sym:
                by_symbol[sym] = by_symbol.get(sym, 0.0) + vol

        fee_rate = get_fee_rate(self._alpha_tier)
        estimated_fees = total_volume * (fee_rate / 100.0)

        return {
            "total_volume": total_volume,
            "estimated_fees": estimated_fees,
            "fee_rate_pct": fee_rate,
            "order_count": order_count,
            "by_symbol": by_symbol,
            "source_available": source_available,
        }
