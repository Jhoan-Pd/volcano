"""Importa todos los modelos para que Alembic y SQLAlchemy los registren en Base.metadata."""
from app.db.base import Base
from app.models.catalogos import Enfermedad, Municipio
from app.models.datos import CasoOficial, EventoVolcanico, RegistroClima, TendenciaBusqueda
from app.models.farmacias import Farmacia, ReporteFarmacia
from app.models.prediccion import Alerta, ModeloEntrenado, Prediccion
from app.models.seguridad import Rol, Usuario

__all__ = [
    "Alerta",
    "Base",
    "CasoOficial",
    "Enfermedad",
    "EventoVolcanico",
    "Farmacia",
    "ModeloEntrenado",
    "Municipio",
    "Prediccion",
    "RegistroClima",
    "ReporteFarmacia",
    "Rol",
    "TendenciaBusqueda",
    "Usuario",
]
