"""
Alert dispatch module via Twilio SMS.

Formats alert messages, queries active recipients from the database
(or fallback environment variables), and dispatches SMS alerts.
"""

import logging
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from twilio.rest import Client

# Load environment variables
load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger("alerts_dispatch")


def get_twilio_client():
    """
    Returns an initialized Twilio Client using:
    TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN from environment.
    Raises EnvironmentError if either is missing.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    if not account_sid or not auth_token:
        raise EnvironmentError(
            "Missing Twilio credentials. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."
        )

    return Client(account_sid, auth_token)


def format_alert_message(
    lake_name: str,
    district: str,
    alert_level: str,
    area_delta_pct: float,
    anomaly_score: float,
) -> str:
    """
    Returns a concise SMS string, max 160 characters:
    Format:
    "GLOF ALERT [{level.upper()}] {lake_name}, {district}
    Area change: +{area_delta_pct:.1f}%
    Risk score: {anomaly_score:.2f}
    glof-watch.vercel.app"
    """
    # Force sign formatting for area delta
    sign = "+" if area_delta_pct >= 0 else ""
    message = (
        f"GLOF ALERT [{alert_level.upper()}] {lake_name}, {district}\n"
        f"Area change: {sign}{area_delta_pct:.1f}%\n"
        f"Risk score: {anomaly_score:.2f}\n"
        f"glof-watch.vercel.app"
    )
    # Truncate to 160 just in case
    return message[:160]


def send_sms_alert(to_number: str, message: str) -> bool:
    """
    Sends SMS via Twilio.
    Reads TWILIO_FROM_NUMBER from environment.
    Returns True on success, False on failure.
    Logs message SID on success, logs error on failure.
    Never raises — always returns bool.
    """
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    if not from_number:
        logger.error("TWILIO_FROM_NUMBER is not set in environment.")
        return False

    try:
        client = get_twilio_client()
        response = client.messages.create(
            body=message,
            from_=from_number,
            to=to_number,
        )
        logger.info("SMS sent successfully to %s. SID: %s", to_number, response.sid)
        return True
    except Exception as e:
        logger.error("Failed to send SMS to %s: %s", to_number, e)
        return False


def get_alert_recipients() -> list[str]:
    """
    Queries a table called alert_recipients from the DB.
    Returns list of phone number strings.
    If table doesn't exist or is empty, returns a fallback list
    from environment variable ALERT_RECIPIENTS (comma-separated numbers).
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            conn = psycopg2.connect(database_url)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT phone FROM alert_recipients WHERE active = TRUE;"
                    )
                    rows = cur.fetchall()
                    if rows:
                        return [r[0] for r in rows]
            except Exception as e:
                logger.warning(
                    "Failed to fetch alert_recipients table, falling back to environment: %s",
                    e,
                )
            finally:
                conn.close()
        except Exception as e:
            logger.warning(
                "Database connection error in get_alert_recipients: %s", e
            )

    # Fallback to env
    recipients_str = os.getenv("ALERT_RECIPIENTS", "")
    if recipients_str:
        return [num.strip() for num in recipients_str.split(",") if num.strip()]
    return []


def dispatch_alert(
    lake_id: int,
    lake_name: str,
    district: str,
    alert_level: str,
    area_delta_pct: float,
    anomaly_score: float,
    alert_db_id: int,
) -> int:
    """
    Full dispatch flow:
    1. Format the SMS message
    2. Get recipients list
    3. Send SMS to each recipient
    4. Update the alerts table: SET sms_sent=TRUE WHERE id=alert_db_id
    5. Return count of successful sends
    """
    message = format_alert_message(
        lake_name=lake_name,
        district=district,
        alert_level=alert_level,
        area_delta_pct=area_delta_pct,
        anomaly_score=anomaly_score,
    )

    recipients = get_alert_recipients()
    if not recipients:
        logger.warning("No alert recipients configured.")
        return 0

    success_count = 0
    for phone in recipients:
        if send_sms_alert(phone, message):
            success_count += 1

    if success_count > 0 and alert_db_id:
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            try:
                conn = psycopg2.connect(database_url)
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE alerts SET sms_sent = TRUE WHERE id = %s;",
                        (alert_db_id,),
                    )
                conn.close()
                logger.info("Updated alerts table: SET sms_sent=TRUE for ID %d", alert_db_id)
            except Exception as e:
                logger.error("Failed to update sms_sent in alerts table: %s", e)

    return success_count
