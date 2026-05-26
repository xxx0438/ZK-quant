"""Weekly settlement cron entry.

Deploy as:
  - Fly.io cron machine (recommended)
  - GitHub Actions scheduled workflow
  - Railway cron service

Schedule: Monday 00:00 UTC.
"""
import asyncio
import logging
import sys

from app.core.logging import setup_logging
from app.db.session import SessionLocal
from app.services.payout_settlement import run_weekly_settlement

async def main():
    setup_logging(level="INFO")
    log = logging.getLogger("echo.cron.settlement")
    log.info("settlement_starting")

    async with SessionLocal() as db:
        try:
            batch = await run_weekly_settlement(db)
            log.info(
                "settlement_complete",
                extra={
                    "batch_id": str(batch.id),
                    "status": batch.status,
                    "total_cents": batch.total_payouts_cents,
                    "recipients": batch.recipient_count,
                },
            )
            return 0
        except Exception as e:
            log.exception("settlement_crashed", extra={"error": str(e)})
            return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
