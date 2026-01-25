#!/usr/bin/env python3
"""
Quality monitoring and Clawdbot alerting for Langfuse metrics.

Checks quality thresholds and sends alerts via Clawdbot webhook when
scores degrade below acceptable levels.

Usage:
    python alerts/quality_monitor.py

    # Via LaunchAgent (every 5 minutes):
    See com.langfuse.quality-monitor.plist
"""

from __future__ import annotations

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass
from enum import Enum

import requests
from langfuse import Langfuse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class QualityThreshold:
    """Threshold configuration for a metric."""
    metric_name: str
    min_value: Optional[float] = None  # Alert if score falls below
    max_value: Optional[float] = None  # Alert if score rises above
    description: str = ""


# Quality thresholds - adjust based on your requirements
THRESHOLDS = [
    QualityThreshold(
        metric_name="faithfulness",
        min_value=0.6,
        description="Faithfulness score indicates how well answers are grounded in context",
    ),
    QualityThreshold(
        metric_name="relevancy",
        min_value=0.7,
        description="Relevancy score indicates how well answers address the question",
    ),
    QualityThreshold(
        metric_name="hallucination",
        max_value=0.3,
        description="Hallucination score indicates unsupported claims (lower is better)",
    ),
]


def get_langfuse_client() -> Optional[Langfuse]:
    """Initialize Langfuse client."""
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "http://localhost:3002")

    if not public_key or not secret_key:
        logger.error("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY required")
        return None

    try:
        return Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
    except Exception as e:
        logger.error(f"Failed to connect to Langfuse: {e}")
        return None


def get_average_score(
    langfuse: Langfuse,
    metric_name: str,
    hours: int = 1,
) -> Optional[float]:
    """
    Get average score for a metric over the specified time period.

    Note: This uses the Langfuse API. For production, consider querying
    ClickHouse directly for better performance.
    """
    from_timestamp = datetime.utcnow() - timedelta(hours=hours)

    try:
        # Fetch scores for the metric
        # Note: The actual API may vary - check Langfuse documentation
        scores = langfuse.get_scores(
            name=metric_name,
            from_timestamp=from_timestamp,
            limit=1000,
        )

        if not scores or not hasattr(scores, "data") or not scores.data:
            logger.debug(f"No scores found for {metric_name}")
            return None

        values = [s.value for s in scores.data if s.value is not None]
        if not values:
            return None

        return sum(values) / len(values)

    except Exception as e:
        logger.error(f"Failed to fetch scores for {metric_name}: {e}")
        return None


def send_clawdbot_alert(
    webhook_url: str,
    metric_name: str,
    current_value: float,
    threshold: QualityThreshold,
    severity: AlertSeverity = AlertSeverity.WARNING,
) -> bool:
    """
    Send alert to Clawdbot webhook.

    Payload format follows Clawdbot notification structure.
    """
    langfuse_host = os.getenv("LANGFUSE_HOST", "http://localhost:3002")

    # Determine threshold value for message
    threshold_value = threshold.min_value if threshold.min_value else threshold.max_value
    direction = "below" if threshold.min_value else "above"

    payload = {
        "type": "quality_alert",
        "severity": severity.value,
        "title": f"RAG {metric_name.title()} Score Degraded",
        "message": (
            f"The {metric_name} score has dropped {direction} the acceptable threshold.\n"
            f"Current: {current_value:.2f}\n"
            f"Threshold: {threshold_value:.2f}\n"
            f"{threshold.description}"
        ),
        "metadata": {
            "metric": metric_name,
            "current_value": current_value,
            "threshold": threshold_value,
            "direction": direction,
        },
        "links": [
            {
                "label": "View in Langfuse",
                "url": f"{langfuse_host}/project/default/scores?metric={metric_name}",
            },
            {
                "label": "View Dashboard",
                "url": "http://localhost:3001/d/rag-quality",
            },
        ],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "langfuse-quality-monitor",
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        logger.info(f"Alert sent successfully for {metric_name}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send alert: {e}")
        return False


def check_thresholds_and_alert(
    langfuse: Langfuse,
    webhook_url: str,
    hours: int = 1,
) -> dict:
    """
    Check all quality thresholds and send alerts for violations.

    Returns:
        Summary of checks and alerts sent
    """
    summary = {
        "checked": 0,
        "violations": 0,
        "alerts_sent": 0,
        "details": [],
    }

    for threshold in THRESHOLDS:
        summary["checked"] += 1

        avg_score = get_average_score(langfuse, threshold.metric_name, hours)

        if avg_score is None:
            logger.info(f"No data for {threshold.metric_name}, skipping")
            summary["details"].append({
                "metric": threshold.metric_name,
                "status": "no_data",
            })
            continue

        violated = False
        severity = AlertSeverity.WARNING

        # Check min threshold (score should be above this)
        if threshold.min_value is not None and avg_score < threshold.min_value:
            violated = True
            # Critical if significantly below threshold
            if avg_score < threshold.min_value * 0.7:
                severity = AlertSeverity.CRITICAL

        # Check max threshold (score should be below this)
        if threshold.max_value is not None and avg_score > threshold.max_value:
            violated = True
            # Critical if significantly above threshold
            if avg_score > threshold.max_value * 1.5:
                severity = AlertSeverity.CRITICAL

        detail = {
            "metric": threshold.metric_name,
            "value": avg_score,
            "threshold_min": threshold.min_value,
            "threshold_max": threshold.max_value,
            "violated": violated,
        }

        if violated:
            summary["violations"] += 1
            logger.warning(
                f"Threshold violation: {threshold.metric_name} = {avg_score:.2f} "
                f"(min: {threshold.min_value}, max: {threshold.max_value})"
            )

            if webhook_url:
                if send_clawdbot_alert(webhook_url, threshold.metric_name, avg_score, threshold, severity):
                    summary["alerts_sent"] += 1
                    detail["alert_sent"] = True
        else:
            logger.info(f"{threshold.metric_name}: {avg_score:.2f} (OK)")

        summary["details"].append(detail)

    return summary


def main():
    """Main entry point for quality monitoring."""
    logger.info("Starting quality monitor")

    # Get configuration
    webhook_url = os.getenv("CLAWDBOT_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("CLAWDBOT_WEBHOOK_URL not set, alerts will be logged only")

    check_hours = int(os.getenv("QUALITY_CHECK_HOURS", "1"))

    # Connect to Langfuse
    langfuse = get_langfuse_client()
    if not langfuse:
        logger.error("Failed to initialize Langfuse client")
        sys.exit(1)

    # Check thresholds
    summary = check_thresholds_and_alert(langfuse, webhook_url, check_hours)

    # Output summary
    print(json.dumps(summary, indent=2, default=str))

    # Exit with code based on violations
    if summary["violations"] > 0:
        sys.exit(2)  # Non-zero but not error, indicates violations found


if __name__ == "__main__":
    main()
