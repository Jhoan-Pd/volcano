"""Avisar al frontend (Next.js en Vercel) que hay datos nuevos.

Los tableros de cada municipio se generan como páginas estáticas con ISR: Vercel las sirve
desde su CDN y las regenera como máximo cada hora. Cuando el cron o un reentrenamiento cambian
los datos no hace falta esperar esa hora: se llama a `/api/revalidar` (revalidación bajo
demanda) y la próxima visita ya recibe la versión nueva.

Sin REVALIDAR_SECRET no se hace nada (desarrollo local y pruebas).
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("predictor.frontend")


def revalidar_frontend() -> dict:
    if not settings.REVALIDAR_SECRET:
        return {"revalidado": False, "motivo": "REVALIDAR_SECRET no está configurado"}
    url = f"{settings.FRONTEND_URL.rstrip('/')}/api/revalidar"
    try:
        r = httpx.post(url, headers={"Authorization": f"Bearer {settings.REVALIDAR_SECRET}"}, timeout=15)
        r.raise_for_status()
        return {"revalidado": True, **r.json()}
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("No se pudo revalidar el frontend (%s): %s", url, exc)
        return {"revalidado": False, "motivo": str(exc)}
