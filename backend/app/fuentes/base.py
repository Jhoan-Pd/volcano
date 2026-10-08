"""Abstracción de fuentes de datos externas.

Patrón Strategy + Adapter:
- Strategy: los servicios dependen de la interfaz `FuenteDatos`, no de una API concreta.
  Se puede cambiar Open-Meteo por IDEAM, o pytrends por un CSV, sin tocar el servicio.
- Adapter: cada implementación traduce el formato propio de la fuente (JSON de Open-Meteo,
  DataFrame de pytrends, JSON Socrata) a una lista de diccionarios con las columnas de NUESTRAS tablas.

Implementaciones:
    OpenMeteoFuente  (Fase 1)  -> registros_clima
    TrendsFuente     (Fase 2)  -> tendencias_busqueda
    SivigilaFuente   (Fase 2)  -> casos_oficiales
    FarmaciaFuente   (Fase 2)  -> índice de ventas desde reportes_farmacia
"""
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("predictor.fuentes")


class FuenteDatosError(Exception):
    """La fuente externa no respondió o devolvió datos inválidos."""


class FuenteDatos(ABC):
    #: Nombre corto que se guarda en la columna `fuente` de cada registro
    nombre: str = "desconocida"

    @abstractmethod
    def obtener(self, **parametros: Any) -> list[dict[str, Any]]:
        """Descarga los datos y los devuelve normalizados (lista de filas listas para la BD)."""

    def disponible(self) -> bool:
        """Chequeo rápido de salud; por defecto intenta una consulta mínima."""
        try:
            self.verificar()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fuente %s no disponible: %s", self.nombre, exc)
            return False

    def verificar(self) -> None:  # pragma: no cover - las subclases lo sobrescriben
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} nombre={self.nombre!r}>"
