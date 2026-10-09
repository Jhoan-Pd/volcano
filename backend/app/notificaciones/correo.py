"""Envío de correos de alerta (patrón Strategy).

El servicio de alertas depende de `NotificadorCorreo`, no de Resend: en las pruebas se usa
un notificador en memoria y, si no hay API key, `NotificadorNulo` (no envía nada y la
plataforma sigue funcionando; la alerta igual aparece en el banner del dashboard).
"""
import html
import logging
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings

logger = logging.getLogger("predictor.correo")


class NotificadorCorreo(ABC):
    @abstractmethod
    def enviar(self, destinatarios: list[str], asunto: str, html_cuerpo: str) -> bool:
        """Devuelve True si el proveedor aceptó el correo."""


class NotificadorNulo(NotificadorCorreo):
    def enviar(self, destinatarios, asunto, html_cuerpo):
        logger.info("Correo no enviado (sin RESEND_API_KEY): %s", asunto)
        return False


class ResendNotificador(NotificadorCorreo):
    """Adaptador de la API REST de Resend (https://resend.com/docs/api-reference/emails/send-email)."""

    def __init__(self, api_key: str, remitente: str, url: str = settings.RESEND_URL,
                 cliente: httpx.Client | None = None):
        self.api_key = api_key
        self.remitente = remitente
        self.url = url
        self.cliente = cliente or httpx.Client(timeout=settings.HTTP_TIMEOUT_SEGUNDOS)

    def enviar(self, destinatarios, asunto, html_cuerpo):
        if not destinatarios:
            return False
        try:
            r = self.cliente.post(self.url, headers={"Authorization": f"Bearer {self.api_key}"},
                                  json={"from": self.remitente, "to": destinatarios, "subject": asunto,
                                        "html": html_cuerpo})
            r.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.warning("Resend rechazó el correo «%s»: %s", asunto, exc)
            return False


def notificador_por_defecto() -> NotificadorCorreo:
    if settings.RESEND_API_KEY:
        return ResendNotificador(settings.RESEND_API_KEY, settings.ALERTAS_EMAIL_REMITENTE)
    return NotificadorNulo()


COLORES = {"NARANJA": "#ec835a", "ROJO": "#d03b3b"}


def html_alertas(alertas: list[dict], url: str) -> str:
    """Cuerpo HTML simple (los clientes de correo no soportan CSS moderno)."""
    filas = "".join(
        f"<tr><td style='padding:6px 10px;border-bottom:1px solid #eee'>"
        f"<span style='display:inline-block;padding:2px 8px;border-radius:10px;color:#fff;"
        f"background:{COLORES.get(a['nivel'], '#888')}'>{html.escape(a['nivel_texto'])}</span></td>"
        f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{html.escape(a['mensaje'])}</td></tr>"
        for a in alertas)
    return (
        "<div style='font-family:Arial,sans-serif;color:#171614'>"
        "<h2 style='margin:0 0 8px'>Alerta temprana · Predictor de Brotes Nariño</h2>"
        f"<p>Se detectaron {len(alertas)} situación(es) de riesgo alto o muy alto:</p>"
        f"<table style='border-collapse:collapse;font-size:14px'>{filas}</table>"
        f"<p style='margin-top:16px'><a href='{html.escape(url)}'>Abrir el dashboard</a></p>"
        "<p style='color:#7d7b75;font-size:12px'>Proyecto académico. Las predicciones son orientativas y no "
        "reemplazan la vigilancia oficial del INS ni de la Secretaría de Salud.</p></div>"
    )
