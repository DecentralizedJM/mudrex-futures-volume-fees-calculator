# Mudrex Futures Volume & Fees Calculator

Calculate **API-sourced trading volume** and **estimated fees** for Mudrex Futures. Uses the [Mudrex Futures API](https://docs.trade.mudrex.com/docs) via the [mudrex-api-trading-python-sdk](https://github.com/DecentralizedJM/mudrex-api-trading-python-sdk).

## Features

- **Volume** = notional value (filled quantity × price), not margin. E.g. $2 margin at 10x → $20 open volume; close → $40 total volume.
- **API-only volume**: When the API returns order source, only orders executed via API are counted. Open via API + close via API = full volume; open via API + close manually = only open volume.
- **Alpha tier fees**: User selects tier (0–6) for correct fee rate. Non-Alpha 0.05%, Alpha 1–6 from 0.048% down to 0.030%.
- **Filters**: Time range (`since` / `until`) and symbol (e.g. `BTCUSDT`, `XAUTUSDT`).
- **Integration**: Works with any pybot by passing an existing `MudrexClient` instance.

## API source limitation

The Mudrex API may or may not return a `source` / `order_source` field in [order history](https://docs.trade.mudrex.com/docs). If it does, the calculator counts only API-sourced orders. If it does not, all filled orders in the selected range are counted (“all volume” mode). You can also use `--all-volume` to always count all filled orders.

## Installation

```bash
git clone https://github.com/DecentralizedJM/mudrex-futures-volume-fees-calculator.git
cd mudrex-futures-volume-fees-calculator
pip install -e .
```

Dependency: [mudrex-api-trading-python-sdk](https://github.com/DecentralizedJM/mudrex-api-trading-python-sdk) (installed automatically).

## Usage

### CLI

```bash
# Set API secret via env
export MUDREX_API_SECRET=your-api-secret

# Volume and fees for a date range
python -m mudrex_volume_fees --since 2025-01-01 --until 2025-01-30

# Filter by symbol (e.g. BTCUSDT, XAUTUSDT)
python -m mudrex_volume_fees --since 2025-01-01 --until 2025-01-30 --symbol BTCUSDT

# Set alpha tier (0=Non-Alpha, 1–6=Alpha 1–6)
python -m mudrex_volume_fees --since 2025-01-01 --alpha-tier 2

# Count all filled orders (do not filter by API source)
python -m mudrex_volume_fees --since 2025-01-01 --all-volume
```

### From your bot (pybot)

```python
from mudrex import MudrexClient
from mudrex_volume_fees import VolumeFeesCalculator

client = MudrexClient(api_secret="your-api-secret")
calc = VolumeFeesCalculator(client=client, alpha_tier=2)

report = calc.calculate(
    since="2025-01-01",
    until="2025-01-30",
    symbol="BTCUSDT",  # optional
)

print(report["total_volume"])    # notional volume in USD
print(report["estimated_fees"]) # fees at your alpha tier
print(report["order_count"])
print(report["by_symbol"])       # volume per symbol
# When include_actual_fees=True (default), report also has actual_fees, actual_fee_count from fee history
```

## Alpha tiers

| Tier | Name      | Fee  |
|------|-----------|------|
| 0    | Non-Alpha | 0.05% |
| 1    | Alpha 1   | 0.048% |
| 2    | Alpha 2   | 0.045% |
| 3    | Alpha 3   | 0.045% |
| 4    | Alpha 4   | 0.040% |
| 5    | Alpha 5   | 0.035% |
| 6    | Alpha 6   | 0.030% |

## References

- [Mudrex API docs](https://docs.trade.mudrex.com/docs)
- [mudrex-api-trading-python-sdk](https://github.com/DecentralizedJM/mudrex-api-trading-python-sdk)
