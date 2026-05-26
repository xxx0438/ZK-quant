# Echo Protocol

> The decentralized quant fund infrastructure for the agent economy.

Echo is a three-part infrastructure stack:

- **Marketplace** — API for AI agents to buy verifiable trading signals
- **Capital** — Echo's own on-chain fund running top marketplace models  
- **Intelligence** — Data + risk analytics SaaS for funds and protocols

## Why Echo

Crypto AI agents are trading billions on-chain. They have no way to verify the signals they consume. Echo solves this with a three-layer trust stack:

1. **Canonical Data** — Echo-signed datasets prevent look-ahead bias
2. **Hardware-Attested Backtest** — Runs in AWS Nitro Enclave, results signed
3. **Continuous Live Tracking** — Echo Capital trades these models with real money

## Quick Start

```bash
# Clone and install
git clone https://github.com/echo-protocol/echo.git
cd echo
pnpm install

# Start local stack
docker-compose up -d

# Train first model
cd apps/models && python train_btc_direction.py

# Generate first performance cert
python generate_cert.py

# Open dashboard
open http://localhost:3000
