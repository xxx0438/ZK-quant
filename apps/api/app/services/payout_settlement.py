"""Revenue ledger writes + weekly batched USDC settlement on Base.

record_revenue_split() — called per prediction
run_weekly_settlement() — called by cron / scheduler
"""
import logging
import os
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3
from eth_account import Account

from app.config import settings
from app.db.models import (
    Model,
    QuantProfile,
    RevenueLedger,
    SettlementBatch,
)

logger = logging.getLogger("echo.settlement")

# ─── Split policy ───
CAPITAL_SHARE_BPS = 2000        # 20% to Echo Capital
DEFAULT_QUANT_BPS = 7000        # 70% to quant
# Remaining 10% → protocol

async def record_revenue_split(
    db: AsyncSession,
    prediction_id: str,
    model: Model,
    gross_cents: int,
) -> RevenueLedger:
    """Append a ledger row for this prediction's revenue split."""
    quant_bps = 0
    quant_id: Optional[uuid.UUID] = None

    if model.quant_user_id:
        result = await db.execute(
            select(QuantProfile).where(QuantProfile.user_id == model.quant_user_id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            quant_bps = profile.revenue_share_bps
            quant_id = profile.id

    capital_bps = CAPITAL_SHARE_BPS
    protocol_bps = 10000 - quant_bps - capital_bps
    if protocol_bps < 0:
        # Shouldn't happen with valid configs; clamp defensively
        protocol_bps = 0
        capital_bps = 10000 - quant_bps

    quant_cents = gross_cents * quant_bps // 10000
    capital_cents = gross_cents * capital_bps // 10000
    protocol_cents = gross_cents - quant_cents - capital_cents  # rounding remainder

    entry = RevenueLedger(
        id=uuid.uuid4(),
        prediction_id=prediction_id,
        model_id=model.id,
        quant_profile_id=quant_id,
        gross_cents=gross_cents,
        quant_cents=quant_cents,
        capital_cents=capital_cents,
        protocol_cents=protocol_cents,
    )
    db.add(entry)
    await db.commit()
    return entry

# ─────────────── On-chain settlement ───────────────

# Minimal USDC ABI
USDC_ABI = [
    {
        "name": "transfer",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "bool"}],
    },
    {
        "name": "decimals",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint8"}],
    },
]

MIN_PAYOUT_CENTS = 1000  # $10 minimum to settle

async def run_weekly_settlement(db: AsyncSession) -> SettlementBatch:
    """Compute owed amounts, submit on-chain USDC transfers, mark ledger as settled.

    Strategy: simple sequential transfers (one tx per recipient). For high volume,
    upgrade to a Multicall contract. Each batch is one SettlementBatch row.
    """
    batch = SettlementBatch(id=uuid.uuid4(), status="pending")
    db.add(batch)
    await db.flush()

    # Sum unsettled per quant
    pending = await db.execute(
        select(
            QuantProfile.id.label("profile_id"),
            QuantProfile.payout_address,
            func.sum(RevenueLedger.quant_cents).label("owed_cents"),
        )
        .join(RevenueLedger, RevenueLedger.quant_profile_id == QuantProfile.id)
        .where(RevenueLedger.settled_at.is_(None))
        .group_by(QuantProfile.id, QuantProfile.payout_address)
        .having(func.sum(RevenueLedger.quant_cents) >= MIN_PAYOUT_CENTS)
    )
    rows = pending.all()

    if not rows:
        batch.status = "confirmed"
        batch.confirmed_at = datetime.utcnow()
        await db.commit()
        logger.info("settlement_no_payouts", extra={"batch_id": str(batch.id)})
        return batch

    # Onchain setup
    settlement_key = os.getenv("SETTLEMENT_PRIVATE_KEY")
    if not settlement_key:
        batch.status = "failed"
        batch.error = "SETTLEMENT_PRIVATE_KEY not configured"
        await db.commit()
        raise RuntimeError(batch.error)

    w3 = Web3(Web3.HTTPProvider(settings.base_rpc_url))
    acct = Account.from_key(settlement_key)
    usdc = w3.eth.contract(
        address=Web3.to_checksum_address(settings.usdc_address_base),
        abi=USDC_ABI,
    )
    decimals = usdc.functions.decimals().call()
    scale = Decimal(10) ** decimals

    total_payouts = 0
    successful_tx_hashes = []

    try:
        nonce = w3.eth.get_transaction_count(acct.address, "pending")

        for row in rows:
            recipient = Web3.to_checksum_address(row.payout_address)
            owed_cents = int(row.owed_cents)
            # cents → USDC base units
            amount_units = int(Decimal(owed_cents) / Decimal(100) * scale)

            tx = usdc.functions.transfer(recipient, amount_units).build_transaction(
                {
                    "from": acct.address,
                    "nonce": nonce,
                    "gas": 100_000,
                    "maxFeePerGas": w3.to_wei("0.1", "gwei"),
                    "maxPriorityFeePerGas": w3.to_wei("0.01", "gwei"),
                    "chainId": 8453,  # Base mainnet
                }
            )
            signed = acct.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt.status != 1:
                logger.error(
                    "payout_tx_failed",
                    extra={"recipient": recipient, "tx": tx_hash.hex()},
                )
                continue

            tx_hex = tx_hash.hex()
            successful_tx_hashes.append(tx_hex)
            total_payouts += owed_cents
            nonce += 1

            # Mark this quant's ledger rows settled
            await db.execute(
                update(RevenueLedger)
                .where(
                    RevenueLedger.quant_profile_id == row.profile_id,
                    RevenueLedger.settled_at.is_(None),
                )
                .values(
                    settled_at=datetime.utcnow(),
                    settlement_tx=tx_hex,
                    settlement_batch_id=batch.id,
                )
            )
            await db.execute(
                update(QuantProfile)
                .where(QuantProfile.id == row.profile_id)
                .values(total_paid_cents=QuantProfile.total_paid_cents + owed_cents)
            )

            logger.info(
                "payout_sent",
                extra={
                    "profile_id": str(row.profile_id),
                    "recipient": recipient,
                    "amount_cents": owed_cents,
                    "tx": tx_hex,
                },
            )

        batch.status = "confirmed"
        batch.confirmed_at = datetime.utcnow()
        batch.submitted_at = datetime.utcnow()
        batch.total_payouts_cents = total_payouts
        batch.recipient_count = len(successful_tx_hashes)
        batch.tx_hash = ",".join(successful_tx_hashes)
        await db.commit()
        return batch

    except Exception as e:
        batch.status = "failed"
        batch.error = str(e)
        await db.commit()
        logger.exception("settlement_failed", extra={"batch_id": str(batch.id)})
        raise
