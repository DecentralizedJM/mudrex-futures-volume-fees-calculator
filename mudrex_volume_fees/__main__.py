"""Allow running as python -m mudrex_volume_fees."""

from mudrex_volume_fees.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
