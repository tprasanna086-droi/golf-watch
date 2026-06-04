"""
Twilio SMS dispatch for GLOF risk alerts.

Loads configuration from environment variables, formats concise alert messages,
and sends notifications when severity meets the configured minimum threshold.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_BACKEND_ROOT / ".env")

logger = logging.getLogger(__name__)

SMS_MAX_LENGTH = 160
SEVERITY_ORDER = ("watch", "warning", "emergency")


@dataclass
class SMSConfig:
    """Twilio credentials and dispatch rules for GLOF SMS alerts."""

    account_sid: str
    auth_token: str
    from_number: str
    recipients: list[str]
    min_severity: str = "warning"


def _severity_rank(severity: str) -> int:
    """Return numeric rank for severity comparison (higher = more severe)."""
    normalized = severity.strip().lower()
    try:
        return SEVERITY_ORDER.index(normalized)
    except ValueError:
        logger.warning("Unknown severity %r; treating as lowest rank", severity)
        return -1


def load_sms_config() -> SMSConfig:
    """
    Load Twilio SMS settings from environment variables.

    Required: ``TWILIO_ACCOUNT_SID``, ``TWILIO_AUTH_TOKEN``, ``TWILIO_FROM_NUMBER``,
    ``TWILIO_RECIPIENTS`` (comma-separated E.164 numbers).
    Optional: ``SMS_MIN_SEVERITY`` (default ``warning``).

    Raises:
        ValueError: If any required variable is missing or empty.
    """
    missing: list[str] = []

    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    if not account_sid:
        missing.append("TWILIO_ACCOUNT_SID")

    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    if not auth_token:
        missing.append("TWILIO_AUTH_TOKEN")

    from_number = os.getenv("TWILIO_FROM_NUMBER", "").strip()
    if not from_number:
        missing.append("TWILIO_FROM_NUMBER")

    recipients_raw = os.getenv("TWILIO_RECIPIENTS", "").strip()
    if not recipients_raw:
        missing.append("TWILIO_RECIPIENTS")

    if missing:
        raise ValueError(
            "Missing required SMS environment variable(s): "
            + ", ".join(missing)
        )

    recipients = [
        number.strip()
        for number in recipients_raw.split(",")
        if number.strip()
    ]
    if not recipients:
        raise ValueError(
            "TWILIO_RECIPIENTS must contain at least one phone number"
        )

    min_severity = os.getenv("SMS_MIN_SEVERITY", "warning").strip().lower()
    if min_severity not in SEVERITY_ORDER:
        raise ValueError(
            f"SMS_MIN_SEVERITY must be one of {SEVERITY_ORDER}; got {min_severity!r}"
        )

    return SMSConfig(
        account_sid=account_sid,
        auth_token=auth_token,
        from_number=from_number,
        recipients=recipients,
        min_severity=min_severity,
    )


def format_alert_message(
    lake_name: str,
    severity: str,
    area_km2: float,
    area_delta_km2: float,
    z_score: float,
    contributing_factors: list[str],
) -> str:
    """
    Build a concise GLOF alert SMS body (target length ≤ 160 characters).

    Truncates the first contributing factor when needed to stay within the limit.
    """
    severity_label = severity.strip().upper()
    delta_sign = "+" if area_delta_km2 >= 0 else ""
    header = f"GLOF ALERT [{severity_label}] - {lake_name}, Nepal"
    area_line = (
        f"Area: {area_km2:.2f} km² ({delta_sign}{area_delta_km2:.2f} km²)"
    )
    score_line = f"Risk score: {z_score:.1f}"
    footer = "glof.watch"

    factor = contributing_factors[0] if contributing_factors else "Anomaly detected"
    base_lines = [header, area_line, score_line]

    def _assemble(factor_text: str) -> str:
        return "\n".join([*base_lines, factor_text, footer])

    message = _assemble(factor)
    if len(message) <= SMS_MAX_LENGTH:
        return message

    prefix = "\n".join(base_lines) + "\n"
    suffix = f"\n{footer}"
    max_factor_len = SMS_MAX_LENGTH - len(prefix) - len(suffix)
    if max_factor_len < 1:
        return message[:SMS_MAX_LENGTH]

    truncated_factor = factor[:max_factor_len].rstrip()
    if len(truncated_factor) < len(factor) and max_factor_len >= 2:
        truncated_factor = truncated_factor[: max_factor_len - 1].rstrip() + "…"

    final_message = prefix + truncated_factor + suffix
    if len(final_message) > SMS_MAX_LENGTH:
        return final_message[:SMS_MAX_LENGTH]
    return final_message


def send_alert_sms(
    config: SMSConfig,
    lake_name: str,
    severity: str,
    area_km2: float,
    area_delta_km2: float,
    z_score: float,
    contributing_factors: list[str],
) -> list[str]:
    """
    Send a GLOF alert SMS to all configured recipients when severity is high enough.

    Returns:
        Twilio message SIDs for successful sends, or an empty list if skipped or none sent.
    """
    if _severity_rank(severity) < _severity_rank(config.min_severity):
        logger.info(
            "Skipping SMS for %s: severity %s below min_severity %s",
            lake_name,
            severity,
            config.min_severity,
        )
        return []

    body = format_alert_message(
        lake_name=lake_name,
        severity=severity,
        area_km2=area_km2,
        area_delta_km2=area_delta_km2,
        z_score=z_score,
        contributing_factors=contributing_factors,
    )
    logger.info(
        "Dispatching GLOF SMS for %s (%s) to %d recipient(s), %d chars",
        lake_name,
        severity,
        len(config.recipients),
        len(body),
    )

    client = Client(config.account_sid, config.auth_token)
    message_sids: list[str] = []

    for recipient in config.recipients:
        logger.info("Sending GLOF alert SMS to %s", recipient)
        try:
            message = client.messages.create(
                body=body,
                from_=config.from_number,
                to=recipient,
            )
            logger.info(
                "SMS sent to %s successfully (SID %s)",
                recipient,
                message.sid,
            )
            message_sids.append(message.sid)
        except TwilioRestException as exc:
            logger.error(
                "Twilio error sending SMS to %s: %s (status %s)",
                recipient,
                exc.msg,
                exc.status,
            )
        except Exception as exc:
            logger.exception(
                "Unexpected error sending SMS to %s: %s",
                recipient,
                exc,
            )

    return message_sids


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sample = format_alert_message(
        lake_name="Imja Lake",
        severity="emergency",
        area_km2=1.92,
        area_delta_km2=0.15,
        z_score=5.3,
        contributing_factors=[
            "Rapid area growth: +0.15 km² vs historical mean",
        ],
    )
    print(sample)
    print(f"({len(sample)} characters)")
