"""
Volume and fee calculator for Mudrex Futures API-sourced orders.

Fetches raw order history from the Mudrex API (Order history: https://docs.trade.mudrex.com),
filters by time/symbol and optionally by order source (API vs manual), and computes
notional volume and estimated fees by alpha tier.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

# Indian Standard Time (UTC+5:30) - all date/time handling is IST-only
IST = timezone(timedelta(hours=5, minutes=30))

from mudrex_volume_fees.tiers import AlphaTier, FEE_RATES, get_fee_rate

# #region agent log
_DEBUG_LOG_PATH = os.environ.get("MUDREX_VF_DEBUG_LOG", os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".cursor", "debug.log")))
def _debug_log(hypothesis_id: str, location: str, message: str, data: Optional[Dict] = None) -> None:
    try:
        log_dir = os.path.dirname(_DEBUG_LOG_PATH)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        with open(_DEBUG_LOG_PATH, "a") as f:
            f.write(json.dumps({"sessionId": "debug-session", "hypothesisId": hypothesis_id, "location": location, "message": message, "data": data or {}, "timestamp": int(time.time() * 1000)}) + "\n")
    except Exception:
        pass
# #endregion

# Keys the API might use for order source (API vs web/ios/android)
SOURCE_KEYS = ("source", "order_source", "origin")


def _norm_dt(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize to IST for comparison; naive datetimes treated as IST."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def _parse_dt(value: Any) -> Optional[datetime]:
    # #region agent log
    if value is not None:
        if (isinstance(value, str) and (not value or value.strip() == "")) or (isinstance(value, (int, float)) and value == 0):
            _debug_log("H3", "calculator.py:_parse_dt", "edge input", {"type": type(value).__name__, "repr": repr(value)[:80]})
    # #endregion
    if value is None:
        return None
    if isinstance(value, datetime):
        return _norm_dt(value)
    # Handle numeric string (API may return Unix ms as "1738234567890")
    if isinstance(value, str) and value.strip():
        stripped = value.strip()
        if stripped.isdigit() or (stripped.replace(".", "", 1).replace("-", "", 1).isdigit()):
            try:
                value = float(stripped)
            except ValueError:
                pass
            else:
                if value > 1e12:
                    value = value / 1000
                try:
                    return datetime.fromtimestamp(value, tz=timezone.utc).astimezone(IST)
                except (ValueError, OSError):
                    pass
    if isinstance(value, (int, float)):
        if value > 1e12:
            value = value / 1000
        try:
            out = datetime.fromtimestamp(value, tz=timezone.utc).astimezone(IST)
            return out
        except (ValueError, OSError):
            return None
    if isinstance(value, str):
        try:
            # Normalize "T" and "Z" for ISO
            s = value.strip().replace("Z", "+00:00")
            if "T" not in s and " " in s and "+" not in s and s.count("-") <= 2:
                s = s.replace(" ", "T", 1)
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is not None:
                dt = dt.astimezone(IST)
            else:
                dt = dt.replace(tzinfo=IST)
            return dt
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


def _fetch_actual_fees(
    client: Any,
    since_dt: Optional[datetime] = None,
    until_dt: Optional[datetime] = None,
    symbol: Optional[str] = None,
) -> tuple:
    """
    Fetch fee history via client.fees.get_history(), filter by time/symbol client-side.
    Returns (total_actual_fees, fee_count).
    """
    try:
        fees = client.fees.get_history(limit=None, symbol=symbol)
    except Exception:
        return 0.0, 0
    total = 0.0
    count = 0
    for fee in fees:
        created = getattr(fee, "created_at", None) if hasattr(fee, "created_at") else None
        if created is None and isinstance(fee, dict):
            created = fee.get("created_at")
        created_dt = _parse_dt(created)
        # #region agent log
        if created_dt is None and (since_dt or until_dt):
            _debug_log("H7", "calculator.py:_fetch_actual_fees", "fee missing created_at with date filter", {"since": str(since_dt), "until": str(until_dt)})
        # #endregion
        # Exclude fees with missing created_at when date filter is set (H7 fix)
        if (since_dt or until_dt) and created_dt is None:
            continue
        if since_dt and created_dt:
            try:
                if _norm_dt(created_dt) < _norm_dt(since_dt):
                    continue
            except TypeError:
                pass
        if until_dt and created_dt:
            try:
                if _norm_dt(created_dt) > _norm_dt(until_dt):
                    continue
            except TypeError:
                pass
        amount = getattr(fee, "fee_amount", "0") if hasattr(fee, "fee_amount") else (fee.get("fee_amount", "0") if isinstance(fee, dict) else "0")
        try:
            total += float(amount)
            count += 1
        except (ValueError, TypeError):
            pass
    return total, count


def fetch_raw_order_history(
    client: Any,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch raw order history from Mudrex API (Order history endpoint).
    Returns list of raw order dicts so we can read source/order_source if present.
    """
    # #region agent log
    _debug_log("H0", "calculator.py:fetch_raw_order_history", "fetch started", {"limit": limit})
    # #endregion
    out: List[Dict[str, Any]] = []
    page = 1
    per_page = 100
    while True:
        resp = client.get("/futures/orders/history", {"page": page, "per_page": per_page})
        data = resp.get("data", resp) if isinstance(resp, dict) else resp
        # #region agent log
        _debug_log("H2", "calculator.py:fetch_raw_order_history", "response shape", {"resp_type": type(resp).__name__, "data_type": type(data).__name__, "page": page, "is_data_list": isinstance(data, list)})
        if not isinstance(resp, dict):
            _debug_log("H2", "calculator.py:fetch_raw_order_history", "resp not dict", {"resp_type": type(resp).__name__})
        # #endregion
        if isinstance(data, list):
            items = data
        else:
            items = data.get("items", data.get("data", [])) if isinstance(data, dict) else []
        if not isinstance(items, list):
            # #region agent log
            _debug_log("H2", "calculator.py:fetch_raw_order_history", "items not list", {"items_type": type(items).__name__})
            # #endregion
            items = []
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
        # Clamp alpha_tier to 0-6 to avoid ValueError for out-of-range (H4 fix)
        tier_val = int(alpha_tier)
        clamped = max(0, min(6, tier_val))
        self._alpha_tier = AlphaTier(clamped)
        # #region agent log
        if tier_val != clamped:
            _debug_log("H4", "calculator.py:__init__", "alpha_tier clamped to valid range", {"requested": tier_val, "clamped": clamped})
        # #endregion
        self._count_only_api_sourced = count_only_api_sourced

    def calculate(
        self,
        since: Optional[Union[datetime, str]] = None,
        until: Optional[Union[datetime, str]] = None,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
        include_actual_fees: bool = True,
    ) -> Dict[str, Any]:
        """
        Compute volume and estimated fees for the given filters.

        Args:
            since: Start of time range (inclusive). datetime or ISO date string.
            until: End of time range (inclusive). datetime or ISO date string.
            symbol: Optional symbol filter (e.g. "BTCUSDT", "XAUTUSDT").
            limit: Optional max number of history orders to fetch (default: all).
            include_actual_fees: If True, fetch fee history and include actual_fees
                in the report (filtered by same time range and symbol).

        Returns:
            Dict with: total_volume, estimated_fees, fee_rate_pct, order_count,
            by_symbol (volume per symbol), source_available (whether source was used),
            and optionally actual_fees, actual_fee_count when include_actual_fees is True.
        """
        # #region agent log
        _debug_log("H0", "calculator.py:calculate", "calculate() entered", {"since": str(since), "until": str(until), "symbol": symbol, "limit": limit})
        # #endregion
        raw_orders = fetch_raw_order_history(self._client, limit=limit)
        since_dt = _parse_dt(since) if since else None
        until_dt = _parse_dt(until) if until else None
        symbol_norm = (symbol or "").strip().upper() or None
        # #region agent log
        _debug_log("H0", "calculator.py:calculate", "after fetch", {"raw_order_count": len(raw_orders), "since_dt": str(since_dt), "until_dt": str(until_dt)})
        # #endregion

        total_volume = 0.0
        by_symbol: Dict[str, float] = {}
        order_count = 0
        source_available = False

        for order in raw_orders:
            created = _parse_dt(order.get("created_at"))
            # #region agent log
            if created is None and order.get("created_at") is not None:
                _debug_log("H3", "calculator.py:calculate", "order created_at parse returned None", {"order_id": order.get("order_id", order.get("id", ""))[:24]})
            if created is None and (since_dt or until_dt):
                _debug_log("H1", "calculator.py:calculate", "order missing created_at with date filter", {"since": str(since_dt), "until": str(until_dt), "order_id": order.get("order_id", order.get("id", ""))[:24]})
            # #endregion
            # Exclude orders with missing created_at when date filter is set (H1)
            if (since_dt or until_dt) and created is None:
                continue
            if since_dt and created:
                try:
                    if _norm_dt(created) < _norm_dt(since_dt):
                        continue
                except TypeError:
                    pass
            if until_dt and created:
                try:
                    if _norm_dt(created) > _norm_dt(until_dt):
                        continue
                except TypeError:
                    pass
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
            # #region agent log
            if created is None:
                _debug_log("H1", "calculator.py:calculate", "order with missing created_at included in volume", {"vol": vol, "order_id": order.get("order_id", order.get("id", ""))[:24]})
            # #endregion
            total_volume += vol
            order_count += 1
            if sym:
                by_symbol[sym] = by_symbol.get(sym, 0.0) + vol

        fee_rate = get_fee_rate(self._alpha_tier)
        # #region agent log
        if self._alpha_tier not in FEE_RATES:
            _debug_log("H4", "calculator.py:calculate", "alpha_tier out of range, using NON_ALPHA", {"tier": int(self._alpha_tier), "fallback_rate": fee_rate})
        # #endregion
        estimated_fees = total_volume * (fee_rate / 100.0)

        result: Dict[str, Any] = {
            "total_volume": total_volume,
            "estimated_fees": estimated_fees,
            "fee_rate_pct": fee_rate,
            "order_count": order_count,
            "by_symbol": by_symbol,
            "source_available": source_available,
        }

        # Optionally fetch actual fees from fee history (filter by time/symbol client-side)
        if include_actual_fees and hasattr(self._client, "fees"):
            actual_fees, actual_fee_count = _fetch_actual_fees(
                self._client,
                since_dt=since_dt,
                until_dt=until_dt,
                symbol=symbol_norm,
            )
            result["actual_fees"] = actual_fees
            result["actual_fee_count"] = actual_fee_count

        return result
