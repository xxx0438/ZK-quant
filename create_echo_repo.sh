#!/bin/bash
# Echo Protocol v4.1 — One-command repository scaffolder
# Usage: bash create_echo_repo.sh

set -e

REPO_NAME="echo-protocol"

if [ -d "$REPO_NAME" ]; then
  echo "Directory $REPO_NAME already exists. Aborting."
  exit 1
fi

echo "Creating $REPO_NAME directory structure..."
mkdir -p $REPO_NAME && cd $REPO_NAME

# Apps
mkdir -p apps/api/app/{core,db,routers,services} apps/api/alembic/versions apps/api/tests
mkdir -p apps/enclave/keys
mkdir -p apps/models/{factors,predictions,artifacts}
mkdir -p apps/forward-test apps/capital apps/intelligence
mkdir -p apps/web/app/{capital,methodology,dashboard,docs,legal/{terms,privacy,disclosures}}
mkdir -p apps/web/components apps/web/public

# Packages
mkdir -p packages/{canonical-data,verify-cert/src,echo-sdk-python/echo}

# Integrations
mkdir -p integrations/{eliza-plugin/src,virtuals-game}

# Research
mkdir -p research/methodology/snapshots research/notebooks

# Infra
mkdir -p infra/{terraform,github-actions}

# Docs
mkdir -p docs/postman

# CI
mkdir -p .github/workflows

# Placeholder files — you'll paste real code from v4.1 spec
touch README.md LICENSE .gitignore .env.example
touch docker-compose.yml package.json pnpm-workspace.yaml turbo.json
touch railway.toml fly.toml vercel.json

# Git init
git init
git branch -M main

cat > README.md <<'EOF'
# Echo Protocol

> The decentralized quant fund infrastructure for the agent economy.

See `docs/ARCHITECTURE.md` for full architecture.

## Quick start
```bash
cp .env.example .env
docker-compose up -d
cd apps/models && python train_btc_direction.py
open http://localhost:3000
