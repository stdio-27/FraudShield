"""
alerts.py — Real-time asynchronous alert evaluation and webhook dispatch.

When a scored transaction reaches the high-confidence threshold, a webhook is
posted to an external receiver (Slack, PagerDuty, SOC dashboard, ...) from a
background task so /transactions/score is never delayed by network latency.
Every flagged transaction is still persisted as a FraudAlert row regardless.
"""

import asyncio
import logging
import os
from typing import Optional
from urllib.parse import urlparse

import httpx

from . import config

logger = logging.getLogger(__name__)

ALERT_WEBHOOK_URL: Optional[str] = os.getenv("ALERT_WEBHOOK_URL") or None
if ALERT_WEBHOOK_URL and urlparse(ALERT_WEBHOOK_URL).scheme not in ("http", "https"):
    logger.error("ALERT_WEBHOOK_URL must be an http(s) URL; webhook alerts disabled.")
    ALERT_WEBHOOK_URL = None

# fraud_score at or above this value fires a webhook.
HIGH_CONFIDENCE_THRESHOLD: float = config.env_float("ALERT_THRESHOLD", 0.85)
CRITICAL_THRESHOLD: float = 0.95

_MAX_ATTEMPTS = 3
_client: Optional[httpx.AsyncClient] = None
# Strong references: the event loop only keeps weak ones, so an unreferenced
# fire-and-forget task can be garbage-collected before it completes.
_background_tasks: set = set()


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=10.0)
    return _client


async def close_client() -> None:
    """Drain in-flight webhooks (briefly) and close the shared HTTP client."""
    global _client
    if _background_tasks:
        await asyncio.wait(list(_background_tasks), timeout=5)
    if _client is not None:
        await _client.aclose()
        _client = None


def _safe_target() -> str:
    parsed = urlparse(ALERT_WEBHOOK_URL or "")
    return parsed.netloc or "unknown"  # never log the path: it often embeds a secret token


async def _dispatch_webhook(payload: dict) -> None:
    """POST the alert, retrying transient failures. Never raises."""
    if not ALERT_WEBHOOK_URL:
        return

    tx_id = payload.get("tx_id")
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = await _get_client().post(ALERT_WEBHOOK_URL, json=payload)
            if response.status_code < 300:
                logger.info("[AlertEngine] Webhook delivered for tx %s (HTTP %s)", tx_id, response.status_code)
                return
            if response.status_code < 500 and response.status_code != 429:
                logger.warning(
                    "[AlertEngine] Webhook rejected for tx %s: HTTP %s (not retrying)",
                    tx_id, response.status_code,
                )
                return
            logger.warning("[AlertEngine] Webhook HTTP %s for tx %s (attempt %s)", response.status_code, tx_id, attempt)
        except httpx.HTTPError as exc:
            logger.warning(
                "[AlertEngine] Webhook error for tx %s to %s (attempt %s): %s",
                tx_id, _safe_target(), attempt, type(exc).__name__,
            )
        except Exception:
            logger.exception("[AlertEngine] Unexpected webhook failure for tx %s", tx_id)
            return

        if attempt < _MAX_ATTEMPTS:
            await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

    logger.error("[AlertEngine] Giving up on webhook for tx %s after %s attempts", tx_id, _MAX_ATTEMPTS)


def evaluate_and_dispatch_alert(
    tx_id,
    amount: float,
    fraud_score: float,
    is_flagged: bool,
    shap_reasons: Optional[list] = None,
) -> None:
    """Fire a background webhook when ``fraud_score >= ALERT_THRESHOLD``. Never raises."""
    if fraud_score < HIGH_CONFIDENCE_THRESHOLD:
        return

    severity = "CRITICAL" if fraud_score >= CRITICAL_THRESHOLD else "HIGH"
    payload = {
        "event": "FRAUD_ALERT",
        "severity": severity,
        "tx_id": str(tx_id),
        "amount": amount,
        "fraud_score": round(fraud_score, 6),
        "is_flagged": is_flagged,
        "shap_reasons": shap_reasons or [],
    }
    logger.info("[AlertEngine] %s alert for tx %s (score=%.4f, amount=%.2f)", severity, tx_id, fraud_score, amount)

    if not ALERT_WEBHOOK_URL:
        return

    try:
        task = asyncio.get_running_loop().create_task(_dispatch_webhook(payload))
    except RuntimeError:
        logger.warning("[AlertEngine] No running event loop — webhook dispatch skipped.")
        return
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
