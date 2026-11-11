"""Alert e-mails (Strategy pattern).

The alert service depends on `EmailNotifier`, not on Resend: tests use an in-memory notifier and,
without an API key, `NullNotifier` sends nothing and the platform keeps working (the alert still
shows up in the dashboard banner and on the live WebSocket feed).
"""
import html
import logging
from abc import ABC, abstractmethod

import httpx

from volcano.shared.config import settings

logger = logging.getLogger("volcano.email")


class EmailNotifier(ABC):
    @abstractmethod
    def send(self, recipients: list[str], subject: str, html_body: str) -> bool:
        """Returns True when the provider accepted the e-mail."""


class NullNotifier(EmailNotifier):
    def send(self, recipients, subject, html_body):
        logger.info("E-mail not sent (no RESEND_API_KEY): %s", subject)
        return False


class ResendNotifier(EmailNotifier):
    """Adapter of Resend's REST API (https://resend.com/docs/api-reference/emails/send-email)."""

    def __init__(self, api_key: str, sender: str, url: str = settings.RESEND_URL,
                 client: httpx.Client | None = None):
        self.api_key = api_key
        self.sender = sender
        self.url = url
        self.client = client or httpx.Client(timeout=settings.HTTP_TIMEOUT_SECONDS)

    def send(self, recipients, subject, html_body):
        if not recipients:
            return False
        try:
            r = self.client.post(self.url, headers={"Authorization": f"Bearer {self.api_key}"},
                                 json={"from": self.sender, "to": recipients, "subject": subject, "html": html_body})
            r.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.warning("Resend rejected the e-mail «%s»: %s", subject, exc)
            return False


def default_notifier() -> EmailNotifier:
    if settings.RESEND_API_KEY:
        return ResendNotifier(settings.RESEND_API_KEY, settings.ALERT_EMAIL_SENDER)
    return NullNotifier()


LEVEL_COLORS = {"ORANGE": "#ec835a", "RED": "#d03b3b"}


def alerts_html(alerts: list[dict], url: str) -> str:
    """Plain HTML body (e-mail clients do not support modern CSS). The text is Spanish."""
    rows = "".join(
        f"<tr><td style='padding:6px 10px;border-bottom:1px solid #eee'>"
        f"<span style='display:inline-block;padding:2px 8px;border-radius:10px;color:#fff;"
        f"background:{LEVEL_COLORS.get(a['level'], '#888')}'>{html.escape(a['level_text'])}</span></td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{html.escape(a['message'])}</td></tr>"
        for a in alerts)
    return (
        "<div style='font-family:Arial,sans-serif;color:#171614'>"
        "<h2 style='margin:0 0 8px'>Alerta temprana · Predictor de Brotes Nariño</h2>"
        f"<p>Se detectaron {len(alerts)} situación(es) de riesgo alto o muy alto:</p>"
        f"<table style='border-collapse:collapse;font-size:14px'>{rows}</table>"
        f"<p style='margin-top:16px'><a href='{html.escape(url)}'>Abrir el dashboard</a></p>"
        "<p style='color:#7d7b75;font-size:12px'>Proyecto académico. Las predicciones son orientativas y no "
        "reemplazan la vigilancia oficial del INS ni de la Secretaría de Salud.</p></div>"
    )
