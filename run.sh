#!/usr/bin/env bash
# Run Mudrex Volume & Fees bot (all times IST).
# Set MUDREX_API_SECRET or pass --api-secret.
cd "$(dirname "$0")"
python3 -m mudrex_volume_fees "$@"
