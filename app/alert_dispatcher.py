"""
Real-time alert dispatch engine.
Creates alerts in DB and dispatches to web/email/Slack per user prefs.
Safe defaults: email uses mock (stdout) unless SMTP configured.
"""
import os
import json
import logging
import requests
from datetime import datetime
from typing import Optional

from . import models
from .mail import send_instant_alert_email
from sqlalchemy.orm import Session

logger = logging.getLogger("leadradar")


def get_or_create_prefs(db: Session, user_id: int) -> models.UserNotificationPreference:
    prefs = db.query(models.UserNotificationPreference).filter(
        models.UserNotificationPreference.user_id == user_id
    ).first()
    if not prefs:
        prefs = models.UserNotificationPreference(user_id=user_id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


def create_alert(
    db,
    user_id: int,
    source_type: str,
    event: str,
    message: str,
    lead_id: Optional[int] = None,
    link_path: Optional[str] = None,
    severity: str = "info",
    commit: bool = True,
) -> models.Alert:
    alert = models.Alert(
        user_id=user_id,
        source_type=source_type,
        event=event,
        message=message,
        lead_id=lead_id,
        link_path=link_path,
        severity=severity,
    )
    db.add(alert)
    if commit:
        db.commit()
        db.refresh(alert)
    return alert


def dispatch_alert(
    db,
    alert: models.Alert,
    base_url: str = "http://57.128.215.250:8000",
    commit: bool = True,
):
    """Dispatch alert to configured channels."""
    prefs = get_or_create_prefs(db, alert.user_id)
    user = db.query(models.User).filter(models.User.id == alert.user_id).first()

    # ── Web (always) ────────────────────────────────────────────
    # Alert row in DB serves as web notification
    # (no extra action needed)

    # ── Email ────────────────────────────────────────────────────
    if prefs.new_lead_email and user and user.email:
        try:
            sent = send_instant_alert_email(
                to_email=user.email,
                subject=f"[LeadRadar] {alert.message}",
                body=alert.message,
                link=f"{base_url}{alert.link_path or '/dashboard'}",
            )
            alert.sent_email = sent
            if commit:
                db.commit()
        except Exception as e:
            logger.error(f"Email dispatch failed: {e}")

    # ── Slack ────────────────────────────────────────────────────
    if prefs.new_lead_slack and prefs.slack_webhook_url:
        try:
            sent = _send_slack_webhook(
                prefs.slack_webhook_url,
                alert,
                base_url,
            )
            alert.sent_slack = sent
            if commit:
                db.commit()
        except Exception as e:
            logger.error(f"Slack dispatch failed: {e}")


def _send_slack_webhook(webhook_url: str, alert: models.Alert, base_url: str) -> bool:
    link = f"{base_url}{alert.link_path or '/dashboard'}"
    payload = {
        "text": f"LeadRadar Alert — {alert.severity.upper()}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*LeadRadar Alert*\n{alert.message}",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{link}|View in Dashboard>",
                },
            },
        ],
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Slack webhook error: {e}")
        return False
