from __future__ import annotations

import asyncio

from loguru import logger
from sqlalchemy import select

from src.app.celery_app import celery_app
from src.app.models.db_models.payment import PaymentORM, PaymentStatus
from src.app.tasks.utils import postgres_session


@celery_app.task(
    name="check_payment_status_task",
    bind=True,
    max_retries=10,
    default_retry_delay=60,  # seconds
)
def check_payment_status_task(self, payment_id: int) -> None:  # type: ignore[no-untyped-def]
    """Check acquiring payment status via async DB/API code."""

    async def _check() -> bool:
        async with postgres_session() as session:
            from src.app.services.payment import PaymentStatusChecker

            checker = PaymentStatusChecker(session)
            return await checker.check_and_update(payment_id=payment_id)

    try:
        is_final = asyncio.run(_check())
    except Exception as exc:
        logger.exception("Exception in check_payment_status_task")
        raise self.retry(exc=exc, countdown=30) from exc

    if not is_final:
        logger.info(
            "Payment {} not final, will retry",
            payment_id,
        )
        raise self.retry(countdown=30)

    logger.info(
        "Payment {} final, check_payment_status_task done",
        payment_id,
    )


@celery_app.task(name="enqueue_payment_status_checks_task")
def enqueue_payment_status_checks_task() -> None:
    """Celery task to enqueue check_payment_status_task for all non-final payments.
    Runs on schedule (e.g. every 3 hours). Selects payments not in Completed/Rejected
    with bank_payment_id set, and enqueues one check_payment_status_task per payment.
    """

    async def _enqueue() -> list[int]:
        async with postgres_session() as session:
            result = await session.execute(
                select(PaymentORM.id).where(
                    ~PaymentORM.payment_status.in_(
                        [
                            PaymentStatus.Completed.value,
                            PaymentStatus.Rejected.value,
                        ]
                    ),
                    PaymentORM.bank_payment_id.isnot(None),
                )
            )
            return [row[0] for row in result.all()]

    # Run async code from sync task
    payment_ids = asyncio.run(_enqueue())

    for payment_id in payment_ids:
        check_payment_status_task.apply_async(args=(payment_id,))
    logger.info(
        "enqueue_payment_status_checks_task done: enqueued {} payment(s)",
        len(payment_ids),
    )
