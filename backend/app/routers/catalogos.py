"""Routers CRUD de catálogos (generados con la fábrica)."""
from app.routers.crud import crear_router_crud
from app.schemas.catalogos import (
    EnfermedadCreate,
    EnfermedadOut,
    EnfermedadUpdate,
    EventoVolcanicoCreate,
    EventoVolcanicoOut,
    EventoVolcanicoUpdate,
    FarmaciaCreate,
    FarmaciaOut,
    FarmaciaUpdate,
    MunicipioCreate,
    MunicipioOut,
    MunicipioUpdate,
)
from app.services.catalogo_services import (
    EnfermedadService,
    EventoVolcanicoService,
    FarmaciaService,
    MunicipioService,
)

municipios = crear_router_crud(
    prefijo="/municipios", etiqueta="Municipios", servicio=MunicipioService,
    esquema_crear=MunicipioCreate, esquema_actualizar=MunicipioUpdate, esquema_salida=MunicipioOut,
)

enfermedades = crear_router_crud(
    prefijo="/enfermedades", etiqueta="Enfermedades", servicio=EnfermedadService,
    esquema_crear=EnfermedadCreate, esquema_actualizar=EnfermedadUpdate, esquema_salida=EnfermedadOut,
)

farmacias = crear_router_crud(
    prefijo="/farmacias", etiqueta="Farmacias", servicio=FarmaciaService,
    esquema_crear=FarmaciaCreate, esquema_actualizar=FarmaciaUpdate, esquema_salida=FarmaciaOut,
    lectura_publica=False, filtros=("municipio_id",),
)

eventos_volcanicos = crear_router_crud(
    prefijo="/eventos-volcanicos", etiqueta="Eventos volcánicos", servicio=EventoVolcanicoService,
    esquema_crear=EventoVolcanicoCreate, esquema_actualizar=EventoVolcanicoUpdate,
    esquema_salida=EventoVolcanicoOut, filtros=("municipio_id",), registrar_autor="registrado_por_id",
)
