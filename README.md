# Echo Protocol

> **The decentralized quant fund infrastructure for the agent economy.**
>
> Verified quant signals. Cryptographically attested. Settled on-chain.

[![Status](https://img.shields.io/badge/status-pre--alpha-orange)]()
[![API](https://img.shields.io/badge/API-v0.4.2-emerald)]()

---

## 🧭 What is this?

Echo Protocol is **API-first infrastructure** for quantitative trading signals, with three core pieces:

1. **Signals API** — pay-per-call access to verified factor & prediction models
2. **Quant Marketplace** — external quants upload models, earn 70% revenue share in USDC
3. **Echo Capital** — autonomous on-chain allocator that trades the best signals on Hyperliquid, with full attribution back to source models

Every prediction returns a cryptographic **performance certificate** (TEE-attested in production). Every dollar of revenue routes through an append-only ledger with weekly USDC settlement on Base.

```
User pays $0.10 per /v1/predict call
    │
    ├─── 70¢ ──► Quant (the model author)        [USDC on Base, weekly]
    ├─── 20¢ ──► Echo Capital (allocator AUM)    [trades signals on Hyperliquid]
    └─── 10¢ ──► Protocol                        [infra + ops]
```

---

## ⚠️ Status: Pre-Alpha

**This is honest about what works and what doesn't.** See [PROJECT_STATUS.md](#-current-completeness) below.

| Component | Status |
|---|---|
| API + Auth + Billing | ✅ Production-ready code |
| Marketplace backend | ✅ Complete |
| Marketplace frontend | ✅ Complete |
| Allocator agent (Hyperliquid) | ✅ Code complete, untested with real funds |
| **Model runtime (load user-uploaded models)** | 🔴 **Not implemented** |
| **TEE enclave service** | 🔴 **Not implemented** (mock endpoint only) |
| **Quant SDK** | 🔴 **Not implemented** |
| **Canonical data layer** | 🔴 **Not implemented** |

**Translation**: the plumbing is real. The "machine that runs untrusted quant code in a TEE" is not. See [What's Missing](#-whats-actually-missing) for the unvarnished gap analysis.

---

## ✨ Features (Implemented)

### Backend (`apps/api`)
- **FastAPI** with async SQLAlchemy 2.0 / asyncpg / Redis
- **Three auth modes**: API key, JWT session, wallet sign-in (SIWE-lite)
- **Atomic billing**: hold → confirm/release pattern, idempotency keys, distributed locks via Redis Lua
- **Coinbase Commerce** integration for USDC top-ups (any crypto, no KYC friction)
- **Token-bucket rate limiting** per user + per endpoint
- **Stripe-style error envelopes** with namespaced error codes
- **Structured JSON logging** with request_id tracing, Sentry hookup
- **Production safety**: config validator hard-fails on placeholder secrets, dev defaults to localhost
- **Alembic migrations** with async env, 5 migrations applied
- **CORS regex** support for subdomain wildcards (`https://*.echo.ai`)
- **Healthcheck (`/health`) + readiness (`/ready`)** with per-dependency timeouts

### Marketplace (v4.2 M1)
- `QuantProfile`, `RevenueLedger`, `SettlementBatch`, `ModelSubmission` schema
- Quant onboarding flow: register → upload → submit
- **Presigned S3 PUT URLs** for direct browser-to-S3 uploads (R2 compatible)
- **SHA256 integrity verification** (browser computes, backend verifies)
- **Automated review pipeline** (artifact check → enclave backtest → threshold gates)
- **Per-prediction revenue split** (70/20/10) written to append-only ledger
- **Weekly USDC batched settlement** on Base via web3.py
- Quant earnings API with per-model breakdown
- GitHub Actions cron for Monday 00:00 UTC payouts

### Allocator Agent (v4.2 M2, `apps/capital-allocator`)
- **Redis pub/sub** signal consumer
- **Fractional-Kelly position sizer** (configurable Kelly fraction, position cap)
- **4-layer risk manager**:
  - per-asset gross exposure
  - portfolio gross/net leverage
  - per-model capacity utilization
  - daily-drawdown circuit breaker (auto-halts the agent)
- **Hyperliquid executor** (testnet + mainnet) with mock fallback for dev
- **Signal → trade attribution table** linking every fill to the originating model
- **Public attribution feed** (Redis publish + `/v1/capital/*` REST)
- Graceful shutdown, async signal handlers

### Frontend (`apps/web`)
- **Next.js 14** App Router
- **Server proxy** (`/api/echo/*`) keeps JWT in httpOnly cookie, never in JS
- **wagmi + RainbowKit** wallet connection
- **Tailwind + shadcn-style** UI primitives
- **React Query** for live data (30s refetch)
- Pages: `/quant`, `/quant/register`, `/quant/dashboard`, `/quant/dashboard/upload`, `/quant/dashboard/earnings`
- Drag-and-drop upload with browser SHA256 + S3 direct PUT
- Legal pages: `/legal/terms`, `/legal/privacy`, `/legal/disclosures`

### DevOps
- **Multi-stage Dockerfile** with healthcheck
- **Railway / Fly.io / Vercel** deployment configs
- **GitHub Actions** CI (pytest + ruff + black + web build)
- **GitHub Actions** weekly settlement cron
- **Postman collection** for API exploration

---

## 🏗️ Architecture

```
                            ┌─────────────────┐
                            │   Next.js Web   │
                            │  /quant/*       │
                            │  /capital       │
                            └────────┬────────┘
                                     │ /api/echo/* (proxy)
                                     ▼
┌──────────────────────────────────────────────────────────────┐
│                   FastAPI (apps/api)                          │
│                                                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  auth    │  │ predict  │  │  quant   │  │   billing    │  │
│  │ /v1/auth │  │/v1/pred… │  │ /v1/qua… │  │ /v1/billing  │  │
│  └──────────┘  └────┬─────┘  └──────────┘  └──────┬───────┘  │
│                     │ publish                       │          │
│                     │                               │ webhook  │
│  ┌──────────────────┼──────────────────┐            │          │
│  │  Postgres        │  Redis           │            │          │
│  │  - users         │  - holds         │     ┌──────▼──────┐   │
│  │  - models        │  - rate limits   │     │  Coinbase   │   │
│  │  - certs         │  - signal bus    │◄────│  Commerce   │   │
│  │  - revenue_ledger│  - public feed   │     └─────────────┘   │
│  │  - allocator_*   │                  │                       │
│  └──────────────────┴──────────────────┘                       │
└────────────────────────┬───────────────────────────────────────┘
                         │  echo:signals (Redis pub/sub)
                         ▼
┌──────────────────────────────────────────────────────────────┐
│         Capital Allocator (apps/capital-allocator)             │
│                                                                │
│  signal_consumer → sizer → risk_manager → executor             │
│                                              │                 │
│                                              ▼                 │
│                                       ┌─────────────┐          │
│                                       │ Hyperliquid │          │
│                                       │  (Base L2)  │          │
│                                       └─────────────┘          │
└──────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│         Weekly Settlement (apps/payouts) — cron                │
│   sum unsettled RevenueLedger → batched USDC.transfer on Base │
└──────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
echo-protocol/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── app/
│   │   │   ├── core/           # errors, logging, middleware, ratelimit, balance
│   │   │   ├── db/             # models, session
│   │   │   ├── routers/        # auth, predict, quant, billing, capital, ...
│   │   │   ├── services/       # coinbase_commerce, model_review, artifact_storage,
│   │   │   │                   #   payout_settlement, geoip, kyc
│   │   │   ├── auth.py
│   │   │   ├── config.py
│   │   │   └── main.py
│   │   ├── alembic/            # 5 migrations: initial, seed, deposit_source,
│   │   │                       #              marketplace, allocator
│   │   ├── tests/              # pytest scaffold
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   │
│   ├── capital-allocator/      # Echo Capital trading agent
│   │   ├── app/
│   │   │   ├── executor/       # base + hyperliquid (+ mock)
│   │   │   ├── db/models.py
│   │   │   ├── signal_bus.py
│   │   │   ├── sizer.py
│   │   │   ├── risk_manager.py
│   │   │   ├── attribution.py
│   │   │   ├── state.py
│   │   │   └── main.py
│   │   ├── tests/test_sizer.py
│   │   ├── Dockerfile
│   │   └── fly.toml
│   │
│   ├── payouts/                # Weekly USDC settlement cron
│   │   └── weekly_settlement.py
│   │
│   ├── web/                    # Next.js 14 frontend
│   │   ├── app/
│   │   │   ├── quant/          # marketplace pages
│   │   │   ├── api/echo/       # server-side proxy
│   │   │   └── legal/          # terms / privacy / disclosures
│   │   ├── components/         # ui/ + quant/
│   │   ├── lib/                # echo-client, format, auth
│   │   ├── middleware.ts
│   │   └── package.json
│   │
│   ├── enclave/                # 🔴 STUB — TEE backtest service (not implemented)
│   ├── models/                 # 🟡 5 hardcoded internal models only
│   ├── forward-test/           # 🟡 scaffold
│   └── intelligence/           # 🟡 scaffold
│
├── packages/
│   ├── canonical-data/         # 🔴 STUB — data layer (not implemented)
│   ├── verify-cert/            # 🔴 STUB — public cert verifier (not implemented)
│   └── echo-sdk-python/        # 🔴 STUB — quant SDK (not implemented)
│
├── integrations/
│   ├── eliza-plugin/           # 🔴 STUB
│   └── virtuals-game/          # 🔴 STUB
│
├── docs/
│   └── postman/                # API collection
│
├── .github/workflows/          # ci.yml, deploy.yml, weekly-settlement.yml
├── docker-compose.yml
├── railway.toml
├── vercel.json
└── README.md (this file)
```

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Docker + Docker Compose
- Python 3.11+
- Node.js 20+
- (Optional) `pnpm` or `npm`

### 1. Clone and configure

```bash
git clone https://github.com/echo-protocol/echo
cd echo
cp .env.example .env
# Generate a JWT secret
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(48))" >> .env
```

### 2. Bring up infrastructure

```bash
docker-compose up -d postgres redis
```

### 3. Run API

```bash
cd apps/api
pip install -e ".[dev]"
alembic upgrade head      # applies all 5 migrations
uvicorn app.main:app --reload --port 8000
```

Visit:
- `http://localhost:8000/docs` — OpenAPI
- `http://localhost:8000/health` — liveness
- `http://localhost:8000/ready` — readiness

### 4. Run Allocator (optional, uses mock executor in dev)

```bash
cd apps/capital-allocator
pip install -e .
alembic upgrade head
python -m app.main
```

The allocator auto-detects `ENVIRONMENT=development` and uses a **mock executor** that simulates fills (no real trades).

### 5. Run Frontend

```bash
cd apps/web
npm install
npm run dev
```

Visit `http://localhost:3000/quant`.

### 6. End-to-end smoke test

```bash
# Sign up + get API key
curl -X POST http://localhost:8000/v1/auth/signup \
  -H "content-type: application/json" \
  -d '{"email":"dev@local","password":"supersecret1234"}'

# Save the api_key from response, then:
export ECHO_KEY=echo_sk_test_...

# Top up via Coinbase Commerce (dev mode returns a fake URL)
curl -X POST http://localhost:8000/v1/billing/topup \
  -H "authorization: Bearer $ECHO_KEY" \
  -H "content-type: application/json" \
  -d '{"amount_usd":100}'

# Manually credit balance for testing:
psql $DATABASE_URL -c "UPDATE users SET balance_usd_cents = 10000;"

# Make a prediction
curl -X POST http://localhost:8000/v1/predict \
  -H "authorization: Bearer $ECHO_KEY" \
  -H "content-type: application/json" \
  -d '{"model":"whale-netflow-eth"}'
```

---

## 🔌 API Highlights

### Auth
```http
POST /v1/auth/signup            { email, password }       → { api_key, session_token }
POST /v1/auth/login             { email, password }       → { session_token }
POST /v1/auth/wallet/nonce      { address }               → { message, nonce }
POST /v1/auth/wallet/verify     { address, signature, nonce, issued_at }
GET  /v1/auth/keys              (auth)                    → list of keys
POST /v1/auth/keys              (auth)                    → new api key
```

### Predict (the core)
```http
POST /v1/predict
  Authorization: Bearer echo_sk_live_...
  Idempotency-Key: ...optional...
  { "model": "whale-netflow-eth", "inputs": {} }

  → 200
  {
    "id": "pred_...",
    "model": "whale-netflow-eth",
    "prediction": { ... },
    "performance_cert": {
      "cert_id": "cert_...",
      "backtest_metrics": { "sharpe": 1.41, ... },
      "live_metrics": { "sharpe_30d": 1.41, ... },
      "verified_by": "aws-nitro-enclave",   // 🔴 stub source today
      "attestation_url": "https://api.echo.ai/v1/certs/cert_..."
    },
    "cost_usd": 0.10,
    "balance_usd": 99.90,
    "disclaimer": "Quantitative output only. NOT investment advice. ..."
  }
```

### Billing
```http
POST /v1/billing/topup          (auth)   { amount_usd: 100 }  → { checkout_url }
POST /v1/billing/coinbase/webhook        (server-to-server, HMAC verified)
```

### Quant Marketplace
```http
POST /v1/quant/register             (auth)  { handle, payout_address, ... }
POST /v1/quant/models/upload-url    (auth)  { proposed_model_id, artifact_type }
POST /v1/quant/models/submit        (auth)  { artifact_url, artifact_sha256, ... }
GET  /v1/quant/models               (auth)
GET  /v1/quant/earnings             (auth)
```

### Capital (public)
```http
GET  /v1/capital/positions       → open allocator positions, with attribution
GET  /v1/capital/recent-trades   → last N trades + originating signal
GET  /v1/capital/daily-pnl       → 30-day PnL series
```

Full OpenAPI at `/docs`. Postman collection in `docs/postman/`.

---

## 🛠️ Configuration

All config is environment-driven. See [`.env.example`](.env.example) for the full list.

**Critical production variables:**

| Variable | Purpose |
|---|---|
| `JWT_SECRET` | ≥32 chars; generate with `secrets.token_urlsafe(48)` |
| `DATABASE_URL` | `postgresql+asyncpg://...` |
| `REDIS_URL` | `redis://...` |
| `COINBASE_COMMERCE_API_KEY` | from commerce.coinbase.com dashboard |
| `COINBASE_COMMERCE_WEBHOOK_SECRET` | for HMAC verification |
| `BASE_RPC_URL` | Base mainnet RPC (Alchemy/Quicknode recommended) |
| `ECHO_TREASURY_ADDRESS` | hot wallet for settlement |
| `SETTLEMENT_PRIVATE_KEY` | (GH secret only) signs USDC transfers |
| `HYPERLIQUID_WALLET_ADDRESS` | allocator vault address |
| `HYPERLIQUID_PRIVATE_KEY` | allocator signing key |
| `S3_*` | object storage for model artifacts |
| `SENTRY_DSN` | error tracking (strongly recommended) |

The config layer **hard-fails on startup** if any of these are placeholders in production.

---

## 🚢 Deployment

### Recommended Stack
- **API** → Fly.io or Railway (Docker, 2 vCPU, 1 GB RAM minimum)
- **Database** → Supabase or Neon (Postgres 16, with `pool_pre_ping`)
- **Redis** → Upstash or Railway Redis
- **Allocator** → Fly.io (1 vCPU, 512 MB, single instance, no public ingress)
- **Frontend** → Vercel
- **Object storage** → Cloudflare R2 (S3-compatible)
- **Weekly settlement** → GitHub Actions scheduled workflow

### One-command deploy

```bash
# API
fly deploy --config apps/api/fly.toml

# Allocator
fly deploy --config apps/capital-allocator/fly.toml

# Frontend
vercel --prod
```

See `railway.toml`, `apps/*/fly.toml`, and `vercel.json` for full configs.

---

## 🧪 Testing

```bash
# API tests
cd apps/api && pytest tests/ -v

# Allocator tests
cd apps/capital-allocator && pytest tests/ -v
```

CI runs both on every push.

---

## 📊 Current Completeness

**Honest scorecard** — see [What's Missing](#-whats-actually-missing) for the full gap analysis.

| Layer | What's done | Real completeness |
|---|---|---|
| API / Auth / Billing | hold/confirm/release, JWT, wallet sign-in, idempotency, rate limiting, Coinbase Commerce | **90%** ✅ |
| Marketplace (backend) | quant profiles, revenue ledger, weekly USDC settlement, automated review pipeline | **80%** ✅ |
| Marketplace (frontend) | register, upload, dashboard, earnings | **60%** 🟡 |
| Allocator | Hyperliquid executor, Kelly sizer, 4-layer risk, attribution feed | **70%** ✅ |
| **Model Runtime** | only 5 hardcoded models | **5%** 🔴 |
| **TEE Enclave** | endpoint stub only | **10%** 🔴 |
| **Quant SDK** | nothing yet | **0%** 🔴 |
| **Canonical Data Layer** | nothing yet | **5%** 🔴 |
| Compliance / Legal | ToS, privacy, disclosures, sanctioned-country geo-block | **30%** 🟡 |
| Operations / Governance | basic logging, no dispute resolution, no quant grading | **5%** 🔴 |

**Aggregate honest score: ~35% of "real marketplace".**

The plumbing is solid. The hard parts (running untrusted user-uploaded code safely, providing data to those models, giving quants a way to build) are not yet built.

---

## 🚧 What's Actually Missing

### 🔴 P0 — Blockers (cannot onboard real quants without these)

1. **TEE Enclave Service** — `apps/enclave/` is a stub. Either real AWS Nitro Enclave or (more pragmatically) a hardened Docker sandbox + signed reproducibility hashes. ~2–3 weeks.
2. **Model Runtime** — the system that takes a user-uploaded artifact, loads it safely, runs `predict()`, and returns. Resource limits, format standard (ONNX recommended), caching, isolation. ~4–6 weeks.
3. **Quant SDK + CLI** — `pip install echo-quant` with `Model` base class, `echo-cli backtest/package/submit`. ~2 weeks.
4. **Canonical Data Layer** — real-time + historical data so quants have something to train on and `/v1/predict` has something to feed models. ~3–4 weeks.

### 🟠 P1 — Marketplace health

5. Public `/marketplace` browse page + `/quants/[handle]` profiles
6. Flexible per-model pricing (quant sets it, Echo takes %)
7. Mandatory 30-day forward-test before listing
8. Quant onboarding docs + example repository + staging environment

### 🟡 P2 — Operations & compliance

9. Dispute resolution + refund mechanism
10. Quant cold-start incentives (Echo Capital auto-allocates to new models)
11. User incentives (free tier, subscription pricing)
12. KYC (Persona/Sumsub), tax forms (1099-NEC), sanctions screening

### 🟢 P3 — Long-term trust

13. Public `verify.echo.ai` cert verifier
14. Echo Capital as ERC-4626 vault (LP-tokenized fund)
15. Marketplace health dashboard (GMV, active quants, model lifecycle metrics)

**Total to full marketplace: ~10–12 months full-time.**

---

## 🛣️ Roadmap

### v4.2 (current)
- ✅ Marketplace M1 (revenue ledger + USDC settlement)
- ✅ Marketplace M2 (Hyperliquid allocator)
- ⏳ Marketplace M3 (Agent federation: Eliza/Virtuals/MCP plugins)

### v4.3 (next — pick one path)
- **Path A (curated):** Skip the marketplace, hand-pick 5–10 quants, build deep verification + attribution. Fastest to revenue + real numbers for VC.
- **Path B (open marketplace):** Build Quant SDK + Model Runtime + Canonical Data + TEE. ~6 months but defensible moat.
- **Path C (B2B first):** Sell "Quant Performance Verification" as a standalone service to existing funds. Generate cashflow, then build marketplace.

### v5.0 (future)
- ZK-proof of model integrity (replace TEE attestation)
- Echo Capital → ERC-4626 tokenized vault, accept LPs
- DAO governance of model curation
- Solana expansion for HFT-grade signals

---

## 🤝 Contributing

This is pre-alpha. We're not accepting external PRs yet — but we are looking for:

- **Quant collaborators** willing to test the (yet-to-be-built) SDK on real models
- **Security researchers** to red-team the TEE attestation flow (when built)
- **DevOps engineers** with Hyperliquid + on-chain settlement experience

Reach out: `hello@echo.ai`

---

## ⚖️ Legal

- [Terms of Service](apps/web/app/legal/terms/page.tsx)
- [Privacy Policy](apps/web/app/legal/privacy/page.tsx)
- [Risk Disclosures](apps/web/app/legal/disclosures/page.tsx)

**Not investment advice.** Echo Protocol provides quantitative data APIs. Outputs are signals and factors, not recommendations. Past performance — including cryptographic certificates of past backtests — does not guarantee future results.

Echo Capital is a separate private investment vehicle. Public on-chain wallet activity is shown for transparency and does NOT constitute a public offering or solicitation.

---

## 🙏 Acknowledgments

Built on the shoulders of:
- **FastAPI** (Sebastián Ramírez and contributors)
- **SQLAlchemy** + **Alembic**
- **Hyperliquid SDK** (Hyperliquid Labs)
- **wagmi** + **viem** (Wagmi devs)
- **Next.js** (Vercel)
- **Coinbase Commerce** (USDC rails without KYC friction)

---

<div align="center">

**Echo Protocol** · The decentralized quant fund infrastructure for the agent economy

[Docs](https://docs.echo.ai) · [Status](https://status.echo.ai) · [Twitter](https://twitter.com/echo_protocol) · [Discord](https://discord.gg/echo)

</div>
