"""
alerts.py — Real-time asynchronous alert evaluation and webhook dispatch.

When a scored transaction exceeds a high-confidence risk threshold, this
module fires a non-blocking webhook notification to an external receiver
(e.g., Slack, PagerDuty, or an internal SOC dashboard) so that the primary
/transactions/score response is never delayed by network latency.
"""

import os
import asyncio
import logging
from typing import Optional
import httpx

logging.basicConfig(level=logging.INFO)

# Configurable via environment variable; defaults to None (disabled).
ALERT_WEBHOOK_URL: Optional[str] = os.getenv("ALERT_WEBHOOK_URL")

# Risk threshold above which a webhook alert is fired.
HIGH_CONFIDENCE_THRESHOLD: float = float(os.getenv("ALERT_THRESHOLD", "0.85"))


async def _dispatch_webhook(payload: dict) -> None:
    """
    Posts the structured alert payload to the configured webhook URL.
    Wrapped in its own coroutine so it can be launched as a fire-and-forget
    background task via ``asyncio.create_task()``.

    Retry strategy: single attempt with a generous 10-second timeout.
    Failures are logged but never propagate back to the caller.
    """
    if not ALERT_WEBHOOK_URL:
        logging.debug("ALERT_WEBHOOK_URL is not configured — skipping webhook dispatch.")
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(ALERT_WEBHOOK_URL, json=payload)
            if response.status_code < 300:
                logging.info(
                    f"[AlertEngine] Webhook dispatched successfully for tx {payload.get('tx_id')} "
                    f"(HTTP {response.status_code})"
                )
            else:
                logging.warning(
                    f"[AlertEngine] Webhook returned non-success status {response.status_code} "
                    f"for tx {payload.get('tx_id')}: {response.text[:200]}"
                )
    except httpx.TimeoutException:
        logging.error(
            f"[AlertEngine] Webhook timed out for tx {payload.get('tx_id')} — "
            f"target URL: {ALERT_WEBHOOK_URL}"
        )
    except Exception as e:
        logging.error(
            f"[AlertEngine] Webhook dispatch failed for tx {payload.get('tx_id')}: {e}",
            exc_info=True,
        )


def evaluate_and_dispatch_alert(
    tx_id: str,
    amount: float,
    fraud_score: float,
    is_flagged: bool,
    shap_reasons: Optional[list] = None,
) -> None:
    """
    Evaluates whether a scored transaction warrants a real-time alert.

    Criteria (either triggers the alert):
      - fraud_score >= HIGH_CONFIDENCE_THRESHOLD (default 0.85)
      - is_flagged is True (model exceeded its own decision threshold)

    If triggered, an ``asyncio.create_task()`` fires the webhook in the
    background so that the calling endpoint returns immediately.
    """
    if not (fraud_score >= HIGH_CONFIDENCE_THRESHOLD or is_flagged):
        return  # Below alert threshold — no action required.

    severity = "CRITICAL" if fraud_score >= 0.95 else (
        "HIGH" if fraud_score >= HIGH_CONFIDENCE_THRESHOLD else "MEDIUM"
    )

    payload = {
        "event": "FRAUD_ALERT",
        "severity": severity,
        "tx_id": str(tx_id),
        "amount": amount,
        "fraud_score": round(fraud_score, 6),
        "is_flagged": is_flagged,
        "shap_reasons": shap_reasons or [],
    }

    logging.info(
        f"[AlertEngine] {severity} alert triggered for tx {tx_id} "
        f"(score={fraud_score:.4f}, amount={amount:.2f})"
    )

    # Fire-and-forget: launch webhook dispatch as a background task.
    # This ensures the /transactions/score response is never blocked.
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_dispatch_webhook(payload))
    except RuntimeError:
        # No running event loop (e.g., called from a sync context during testing).
        logging.warning("[AlertEngine] No running event loop — webhook dispatch skipped.")
