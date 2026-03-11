from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx
from loguru import logger
from src.app.core.config import settings
from src.app.core.constants import PAYMENT_BANK_ID


class AcquiringStartError(Exception):
    pass


class AcquiringCheckError(Exception):
    """Errors when checking payment status in bank acquiring API."""


class AcquiringPaymentNotFoundError(Exception):
    """Bank acquiring API returned 'payment not found'."""


class AcquiringClient:
    def __init__(
        self,
        start_url: str | None = None,
        check_url: str | None = None,
    ) -> None:
        self._start_url = start_url or settings.ACQUIRING_START_URL
        self._check_url = check_url or settings.ACQUIRING_CHECK_URL

    async def start_payment(self, order_id: int, amount: Decimal) -> str:
        payload = {"order_id": order_id, "amount": str(amount)}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(self._start_url, json=payload)
        except httpx.HTTPError as exc:
            logger.opt(exception=True).error(
                "Acquiring start_payment HTTP error: order_id={}, amount={}",
                order_id,
                amount,
            )
            raise AcquiringStartError from exc

        if response.status_code != 200:  # noqa: PLR2004
            logger.error(
                "Acquiring start_payment non-200: order_id={}, status={}, body={!r}",
                order_id,
                response.status_code,
                response.text[:500],
            )
            raise AcquiringStartError

        # API: success -> unique payment ID, failure -> error string
        # Be tolerant to response formats (plain string or JSON).
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            data = response.json()
            if isinstance(data, str):
                logger.error(
                    "Acquiring start_payment JSON response is string: order_id={}, data={!r}",
                    order_id,
                    data[:200] if isinstance(data, str) else data,
                )
                raise AcquiringStartError
            if isinstance(data, dict):
                payment_id = data.get(PAYMENT_BANK_ID, None)
                if isinstance(payment_id, str) and payment_id:
                    logger.debug(
                        "Acquiring start_payment success: order_id={}, bank_payment_id={}",
                        order_id,
                        payment_id,
                    )
                    return payment_id
            logger.error(
                "Acquiring start_payment invalid JSON body: order_id={}, data={!r}",
                order_id,
                data if isinstance(data, dict) else type(data).__name__,
            )
            raise AcquiringStartError

        text = response.text.strip()
        if not text:
            logger.error(
                "Acquiring start_payment empty response: order_id={}",
                order_id,
            )
            raise AcquiringStartError
        # Bank may return either an ID (success) or an arbitrary error string.
        # Heuristic: IDs are typically single-token values without whitespace.
        if any(ch.isspace() for ch in text):
            logger.error(
                "Acquiring start_payment response has whitespace (error?): order_id={}, text={!r}",
                order_id,
                text[:200],
            )
            raise AcquiringStartError
        if len(text) > 255:  # noqa: PLR2004
            logger.error(
                "Acquiring start_payment response too long: order_id={}, len={}",
                order_id,
                len(text),
            )
            raise AcquiringStartError
        logger.debug(
            "Acquiring start_payment success (plain text): order_id={}, bank_payment_id={}",
            order_id,
            text,
        )
        return text

    async def check_payment(self, bank_payment_id: str) -> dict[str, Any]:
        """Check payment status in bank acquiring API by its unique ID."""
        payload: dict[str, Any] = {PAYMENT_BANK_ID: bank_payment_id}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(self._check_url, json=payload)
        except httpx.HTTPError as exc:
            logger.opt(exception=True).error(
                "Acquiring check_payment HTTP error: bank_payment_id={}",
                bank_payment_id,
            )
            raise AcquiringCheckError from exc

        if response.status_code != 200:  # noqa: PLR2004
            logger.error(
                "Acquiring check_payment non-200: bank_payment_id={}, status={}, body={!r}",
                bank_payment_id,
                response.status_code,
                response.text[:500],
            )
            raise AcquiringCheckError

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            logger.error(
                "Acquiring check_payment non-JSON response: bank_payment_id={}, content_type={}",
                bank_payment_id,
                content_type,
            )
            raise AcquiringCheckError
        data = response.json()
        if not isinstance(data, dict):
            logger.error(
                "Acquiring check_payment response not dict: bank_payment_id={}, type={}",
                bank_payment_id,
                type(data).__name__,
            )
            raise AcquiringCheckError
        if data == {"error": "Payment not found"}:
            logger.debug(
                "Acquiring check_payment payment not found: bank_payment_id={}",
                bank_payment_id,
            )
            raise AcquiringPaymentNotFoundError
        return data
