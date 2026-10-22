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

    @property
    def rango(self) -> int:
        """Posición en la escala (0 = verde … 3 = rojo): permite comparar niveles."""
        return list(NivelRiesgo).index(self)

    @property
    def etiqueta(self) -> str:
        return _ETIQUETAS_NIVEL[self]

    @property
    def es_alerta(self) -> bool:
        """Alto o muy alto: los niveles que generan una alerta temprana."""
        return self.rango >= NivelRiesgo.NARANJA.rango

    @classmethod
    def peor(cls, niveles) -> "NivelRiesgo":
        """El nivel más alto de una colección (VERDE si está vacía). Acepta Enum o texto."""
        return max((cls(n) for n in niveles), key=lambda n: n.rango, default=cls.VERDE)


_ETIQUETAS_NIVEL = {NivelRiesgo.VERDE: "Bajo", NivelRiesgo.AMARILLO: "Moderado", NivelRiesgo.NARANJA: "Alto",
                    NivelRiesgo.ROJO: "Muy alto"}


class OrigenAlerta(StrEnum):
    OBSERVADO = "OBSERVADO"  # los casos de la última semana ya superan el umbral
    PREDICHO = "PREDICHO"    # el modelo lo anticipa en las próximas 4 semanas


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
