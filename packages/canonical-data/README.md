# echo-data

> The canonical market-state layer powering Echo Protocol.

```bash
pip install echo-data
```

## What it does

Every Echo model — running live, in backtest, or being replayed for verification — sees the **same** input schema and the **same** market view. This package owns that view.

1. **Ingest** data from Hyperliquid, CoinGecko, Arkham → Timescale + Redis
2. **Build** deterministic `Inputs` snapshots on demand
3. **Hash** every snapshot for cryptographic provenance
4. **Replay** any past snapshot exactly, byte-for-byte

## Architecture

```
sources/  →  storage/  →  snapshot.py  →  /v1/predict
              ↑                  ↓
              └── replay.py ◄────┘
                  (verifier)
```

## Usage

```python
from echo_data.client import CanonicalDataClient

client = CanonicalDataClient(database_url=..., redis_url=...)

# Build a live snapshot
inputs, snapshot_hash = await client.build_snapshot("ETH")

# Re-materialize a past one
restored = await client.replay(snapshot_hash, verify=True)
assert restored.snapshot_hash == snapshot_hash
```

## Determinism guarantees

- All floats rounded to fixed per-kind precision before hashing
- JSON canonicalized (sorted keys, no whitespace)
- Schema + source versions baked into hash
- Snapshots stored compressed in Timescale + cached in Redis for 7 days

If `replay(hash, verify=True)` returns successfully, the snapshot is byte-identical to the one that produced the prediction. This is what makes Echo's certs reproducible.
