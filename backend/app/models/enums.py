"""Catálogos cerrados. Se guardan como texto en BD (portable entre SQLite y PostgreSQL)
y se validan con estos Enum en los esquemas Pydantic."""
from enum import StrEnum


class RolNombre(StrEnum):
    ADMIN = "ADMIN"
    FARMACIA = "FARMACIA"
    CIUDADANO = "CIUDADANO"


class NivelRiesgo(StrEnum):
    VERDE = "VERDE"
    AMARILLO = "AMARILLO"
    NARANJA = "NARANJA"
    ROJO = "ROJO"


class NivelVolcanico(StrEnum):
    # Escala de alertas del Servicio Geológico Colombiano
    VERDE = "VERDE"        # volcán activo y comportamiento estable
    AMARILLO = "AMARILLO"  # cambios en el comportamiento de la actividad
    NARANJA = "NARANJA"    # erupción probable en días o semanas
    ROJO = "ROJO"          # erupción inminente o en curso


class TipoEventoVolcanico(StrEnum):
    BOLETIN = "BOLETIN"            # boletín semanal SGC (nivel de actividad)
    CAIDA_CENIZA = "CAIDA_CENIZA"  # reporte de caída de ceniza en un municipio
    EMISION_GASES = "EMISION_GASES"
    SISMO = "SISMO"


class CategoriaProducto(StrEnum):
    ANTIGRIPALES = "ANTIGRIPALES"
    ANTIPIRETICOS = "ANTIPIRETICOS"
    SALES_REHIDRATACION = "SALES_REHIDRATACION"
    INHALADORES = "INHALADORES"
    TAPABOCAS = "TAPABOCAS"
    REPELENTES = "REPELENTES"
