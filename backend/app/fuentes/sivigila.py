"""Adaptador de SIVIGILA (INS) publicado en datos.gov.co mediante la API Socrata (SODA).

Dataset `4hyg-wa9d` "Datos de Vigilancia en Salud Pública de Colombia". Columnas usadas:
    cod_eve      código del evento INS (210 dengue, 220 dengue grave, 345/348 IRAG...)
    cod_dpto_o   departamento de ocurrencia (52 = Nariño)
    cod_mun_o    municipio de ocurrencia (DIVIPOLA de 5 dígitos)
    ano, semana  año y semana epidemiológica
    conteo       casos de esa semana

Limitaciones que se documentan en la sustentación:
- El dataset llega hasta 2022 (actualizado por última vez en oct. 2024).
- Solo trae semanas con casos: las semanas ausentes de un año cubierto valen 0.
- La morbilidad por IRA y EDA (eventos colectivos 995/998) NO está en este dataset; por eso
  esas enfermedades siguen con datos simulados y el mapeo es configurable por enfermedad.

Decisión: se agrega en el servidor de Socrata ($select + $group) para descargar pocas filas,
y se pagina con $limit/$offset por si la consulta crece.
"""
import time
from typing import Any

import httpx

from app.core.config import settings
from app.fuentes.base import FuenteDatos, FuenteDatosError, logger

TAM_PAGINA = 50_000


class SivigilaFuente(FuenteDatos):
    nombre = "SIVIGILA (datos.gov.co)"

    def __init__(self, cliente: httpx.Client | None = None, url: str | None = None, app_token: str | None = None,
                 timeout: float | None = None):
        self._cliente = cliente
        self.url = url or settings.SOCRATA_URL
        self.app_token = app_token if app_token is not None else settings.SOCRATA_APP_TOKEN
        self._timeout = timeout or max(settings.HTTP_TIMEOUT_SEGUNDOS, 40)

    def _get(self, params: dict[str, Any], reintentos: int = 2) -> list[dict[str, Any]]:
        headers = {"X-App-Token": self.app_token} if self.app_token else {}
        ultimo: Exception | None = None
        for intento in range(reintentos + 1):
            try:
                if self._cliente is not None:
                    resp = self._cliente.get(self.url, params=params, headers=headers)
                else:
                    with httpx.Client(timeout=self._timeout) as c:
                        resp = c.get(self.url, params=params, headers=headers)
                if resp.status_code == 200:
                    datos = resp.json()
                    if not isinstance(datos, list):
                        raise FuenteDatosError("Respuesta de Socrata con formato inesperado")
                    return datos
                ultimo = FuenteDatosError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                if resp.status_code < 500 and resp.status_code != 429:
                    break
            except (httpx.HTTPError, ValueError) as exc:
                ultimo = exc
            time.sleep(1.0 * (intento + 1))
        raise FuenteDatosError(f"datos.gov.co no respondió: {ultimo}")

    @staticmethod
    def consulta(codigos_evento: list[str], cod_departamento: str, desde_anio: int) -> dict[str, str]:
        if not codigos_evento or not all(c.isdigit() for c in codigos_evento):
            raise ValueError("Los códigos de evento deben ser numéricos")
        lista = ",".join(f"'{c}'" for c in codigos_evento)
        return {
            "$select": "cod_eve,cod_mun_o,ano,semana,sum(conteo) as casos",
            "$where": f"cod_dpto_o='{int(cod_departamento)}' AND cod_eve in({lista}) AND ano >= '{int(desde_anio)}'",
            "$group": "cod_eve,cod_mun_o,ano,semana",
            "$order": "ano,semana,cod_mun_o",
        }

    @staticmethod
    def adaptar(fila: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return {
                "cod_eve": str(fila["cod_eve"]).strip(),
                "cod_divipola": str(int(float(fila["cod_mun_o"]))).zfill(5),
                "anio": int(float(fila["ano"])),
                "semana_epi": int(float(fila["semana"])),
                "casos": round(float(fila.get("casos", fila.get("sum_conteo", 0)) or 0)),
            }
        except (KeyError, TypeError, ValueError):
            return None  # fila incompleta: se descarta

    def obtener(self, *, codigos_evento: list[str], cod_departamento: str | None = None,
                desde_anio: int = 2020, **_: Any) -> list[dict[str, Any]]:
        """Casos por (evento, municipio, año, semana) de todo el departamento."""
        params = self.consulta(codigos_evento, cod_departamento or settings.SIVIGILA_DEPARTAMENTO, desde_anio)
        filas: list[dict[str, Any]] = []
        offset = 0
        while True:
            lote = self._get({**params, "$limit": TAM_PAGINA, "$offset": offset})
            filas += [f for f in (self.adaptar(x) for x in lote) if f is not None and 1 <= f["semana_epi"] <= 53]
            if len(lote) < TAM_PAGINA:
                break
            offset += TAM_PAGINA
        logger.info("SIVIGILA eventos %s: %d filas", ",".join(codigos_evento), len(filas))
        return filas

    def verificar(self) -> None:  # pragma: no cover - red
        self._get({"$select": "count(*)", "$where": "cod_dpto_o='52'", "$limit": 1})
