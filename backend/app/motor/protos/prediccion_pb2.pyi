from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class NivelRiesgo(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    NIVEL_DESCONOCIDO: _ClassVar[NivelRiesgo]
    VERDE: _ClassVar[NivelRiesgo]
    AMARILLO: _ClassVar[NivelRiesgo]
    NARANJA: _ClassVar[NivelRiesgo]
    ROJO: _ClassVar[NivelRiesgo]
NIVEL_DESCONOCIDO: NivelRiesgo
VERDE: NivelRiesgo
AMARILLO: NivelRiesgo
NARANJA: NivelRiesgo
ROJO: NivelRiesgo

class Vacio(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class EstadoMotor(_message.Message):
    __slots__ = ("version", "modelos_en_memoria", "entrenando", "activo_desde_s", "rpcs_atendidas")
    VERSION_FIELD_NUMBER: _ClassVar[int]
    MODELOS_EN_MEMORIA_FIELD_NUMBER: _ClassVar[int]
    ENTRENANDO_FIELD_NUMBER: _ClassVar[int]
    ACTIVO_DESDE_S_FIELD_NUMBER: _ClassVar[int]
    RPCS_ATENDIDAS_FIELD_NUMBER: _ClassVar[int]
    version: str
    modelos_en_memoria: int
    entrenando: bool
    activo_desde_s: float
    rpcs_atendidas: int
    def __init__(self, version: _Optional[str] = ..., modelos_en_memoria: _Optional[int] = ..., entrenando: _Optional[bool] = ..., activo_desde_s: _Optional[float] = ..., rpcs_atendidas: _Optional[int] = ...) -> None: ...

class SolicitudPrediccion(_message.Message):
    __slots__ = ("municipio_id", "enfermedad_id")
    MUNICIPIO_ID_FIELD_NUMBER: _ClassVar[int]
    ENFERMEDAD_ID_FIELD_NUMBER: _ClassVar[int]
    municipio_id: int
    enfermedad_id: int
    def __init__(self, municipio_id: _Optional[int] = ..., enfermedad_id: _Optional[int] = ...) -> None: ...

class Umbrales(_message.Message):
    __slots__ = ("amarillo", "naranja", "rojo")
    AMARILLO_FIELD_NUMBER: _ClassVar[int]
    NARANJA_FIELD_NUMBER: _ClassVar[int]
    ROJO_FIELD_NUMBER: _ClassVar[int]
    amarillo: float
    naranja: float
    rojo: float
    def __init__(self, amarillo: _Optional[float] = ..., naranja: _Optional[float] = ..., rojo: _Optional[float] = ...) -> None: ...

class PuntoPronostico(_message.Message):
    __slots__ = ("anio", "semana_epi", "etiqueta", "horizonte", "casos_esperados", "limite_inferior", "limite_superior", "nivel", "umbrales")
    ANIO_FIELD_NUMBER: _ClassVar[int]
    SEMANA_EPI_FIELD_NUMBER: _ClassVar[int]
    ETIQUETA_FIELD_NUMBER: _ClassVar[int]
    HORIZONTE_FIELD_NUMBER: _ClassVar[int]
    CASOS_ESPERADOS_FIELD_NUMBER: _ClassVar[int]
    LIMITE_INFERIOR_FIELD_NUMBER: _ClassVar[int]
    LIMITE_SUPERIOR_FIELD_NUMBER: _ClassVar[int]
    NIVEL_FIELD_NUMBER: _ClassVar[int]
    UMBRALES_FIELD_NUMBER: _ClassVar[int]
    anio: int
    semana_epi: int
    etiqueta: str
    horizonte: int
    casos_esperados: float
    limite_inferior: float
    limite_superior: float
    nivel: NivelRiesgo
    umbrales: Umbrales
    def __init__(self, anio: _Optional[int] = ..., semana_epi: _Optional[int] = ..., etiqueta: _Optional[str] = ..., horizonte: _Optional[int] = ..., casos_esperados: _Optional[float] = ..., limite_inferior: _Optional[float] = ..., limite_superior: _Optional[float] = ..., nivel: _Optional[_Union[NivelRiesgo, str]] = ..., umbrales: _Optional[_Union[Umbrales, _Mapping]] = ...) -> None: ...

class Pronostico(_message.Message):
    __slots__ = ("municipio_id", "municipio", "enfermedad_id", "enfermedad", "algoritmo", "modelo_id", "semana_base", "nivel_max", "puntos", "duracion_ms", "desde_cache")
    MUNICIPIO_ID_FIELD_NUMBER: _ClassVar[int]
    MUNICIPIO_FIELD_NUMBER: _ClassVar[int]
    ENFERMEDAD_ID_FIELD_NUMBER: _ClassVar[int]
    ENFERMEDAD_FIELD_NUMBER: _ClassVar[int]
    ALGORITMO_FIELD_NUMBER: _ClassVar[int]
    MODELO_ID_FIELD_NUMBER: _ClassVar[int]
    SEMANA_BASE_FIELD_NUMBER: _ClassVar[int]
    NIVEL_MAX_FIELD_NUMBER: _ClassVar[int]
    PUNTOS_FIELD_NUMBER: _ClassVar[int]
    DURACION_MS_FIELD_NUMBER: _ClassVar[int]
    DESDE_CACHE_FIELD_NUMBER: _ClassVar[int]
    municipio_id: int
    municipio: str
    enfermedad_id: int
    enfermedad: str
    algoritmo: str
    modelo_id: int
    semana_base: str
    nivel_max: NivelRiesgo
    puntos: _containers.RepeatedCompositeFieldContainer[PuntoPronostico]
    duracion_ms: float
    desde_cache: bool
    def __init__(self, municipio_id: _Optional[int] = ..., municipio: _Optional[str] = ..., enfermedad_id: _Optional[int] = ..., enfermedad: _Optional[str] = ..., algoritmo: _Optional[str] = ..., modelo_id: _Optional[int] = ..., semana_base: _Optional[str] = ..., nivel_max: _Optional[_Union[NivelRiesgo, str]] = ..., puntos: _Optional[_Iterable[_Union[PuntoPronostico, _Mapping]]] = ..., duracion_ms: _Optional[float] = ..., desde_cache: _Optional[bool] = ...) -> None: ...

class SolicitudEntrenamiento(_message.Message):
    __slots__ = ("enfermedad_id",)
    ENFERMEDAD_ID_FIELD_NUMBER: _ClassVar[int]
    enfermedad_id: int
    def __init__(self, enfermedad_id: _Optional[int] = ...) -> None: ...

class ProgresoEntrenamiento(_message.Message):
    __slots__ = ("etapa", "mensaje", "porcentaje", "enfermedad", "algoritmo", "mae", "mae_base")
    class Etapa(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ETAPA_DESCONOCIDA: _ClassVar[ProgresoEntrenamiento.Etapa]
        INICIO: _ClassVar[ProgresoEntrenamiento.Etapa]
        DATASET: _ClassVar[ProgresoEntrenamiento.Etapa]
        CANDIDATO: _ClassVar[ProgresoEntrenamiento.Etapa]
        MODELO_LISTO: _ClassVar[ProgresoEntrenamiento.Etapa]
        PREDICCIONES: _ClassVar[ProgresoEntrenamiento.Etapa]
        ALERTAS: _ClassVar[ProgresoEntrenamiento.Etapa]
        AVISO: _ClassVar[ProgresoEntrenamiento.Etapa]
        FIN: _ClassVar[ProgresoEntrenamiento.Etapa]
        ERROR: _ClassVar[ProgresoEntrenamiento.Etapa]
    ETAPA_DESCONOCIDA: ProgresoEntrenamiento.Etapa
    INICIO: ProgresoEntrenamiento.Etapa
    DATASET: ProgresoEntrenamiento.Etapa
    CANDIDATO: ProgresoEntrenamiento.Etapa
    MODELO_LISTO: ProgresoEntrenamiento.Etapa
    PREDICCIONES: ProgresoEntrenamiento.Etapa
    ALERTAS: ProgresoEntrenamiento.Etapa
    AVISO: ProgresoEntrenamiento.Etapa
    FIN: ProgresoEntrenamiento.Etapa
    ERROR: ProgresoEntrenamiento.Etapa
    ETAPA_FIELD_NUMBER: _ClassVar[int]
    MENSAJE_FIELD_NUMBER: _ClassVar[int]
    PORCENTAJE_FIELD_NUMBER: _ClassVar[int]
    ENFERMEDAD_FIELD_NUMBER: _ClassVar[int]
    ALGORITMO_FIELD_NUMBER: _ClassVar[int]
    MAE_FIELD_NUMBER: _ClassVar[int]
    MAE_BASE_FIELD_NUMBER: _ClassVar[int]
    etapa: ProgresoEntrenamiento.Etapa
    mensaje: str
    porcentaje: float
    enfermedad: str
    algoritmo: str
    mae: float
    mae_base: float
    def __init__(self, etapa: _Optional[_Union[ProgresoEntrenamiento.Etapa, str]] = ..., mensaje: _Optional[str] = ..., porcentaje: _Optional[float] = ..., enfermedad: _Optional[str] = ..., algoritmo: _Optional[str] = ..., mae: _Optional[float] = ..., mae_base: _Optional[float] = ...) -> None: ...

class FiltroAlertas(_message.Message):
    __slots__ = ("municipio_id",)
    MUNICIPIO_ID_FIELD_NUMBER: _ClassVar[int]
    municipio_id: int
    def __init__(self, municipio_id: _Optional[int] = ...) -> None: ...

class Alerta(_message.Message):
    __slots__ = ("id", "municipio_id", "municipio", "enfermedad_id", "enfermedad", "semana", "nivel", "origen", "mensaje")
    ID_FIELD_NUMBER: _ClassVar[int]
    MUNICIPIO_ID_FIELD_NUMBER: _ClassVar[int]
    MUNICIPIO_FIELD_NUMBER: _ClassVar[int]
    ENFERMEDAD_ID_FIELD_NUMBER: _ClassVar[int]
    ENFERMEDAD_FIELD_NUMBER: _ClassVar[int]
    SEMANA_FIELD_NUMBER: _ClassVar[int]
    NIVEL_FIELD_NUMBER: _ClassVar[int]
    ORIGEN_FIELD_NUMBER: _ClassVar[int]
    MENSAJE_FIELD_NUMBER: _ClassVar[int]
    id: int
    municipio_id: int
    municipio: str
    enfermedad_id: int
    enfermedad: str
    semana: str
    nivel: NivelRiesgo
    origen: str
    mensaje: str
    def __init__(self, id: _Optional[int] = ..., municipio_id: _Optional[int] = ..., municipio: _Optional[str] = ..., enfermedad_id: _Optional[int] = ..., enfermedad: _Optional[str] = ..., semana: _Optional[str] = ..., nivel: _Optional[_Union[NivelRiesgo, str]] = ..., origen: _Optional[str] = ..., mensaje: _Optional[str] = ...) -> None: ...

class EventoAlerta(_message.Message):
    __slots__ = ("tipo", "alerta", "momento")
    class Tipo(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        TIPO_DESCONOCIDO: _ClassVar[EventoAlerta.Tipo]
        ACTIVA: _ClassVar[EventoAlerta.Tipo]
        NUEVA: _ClassVar[EventoAlerta.Tipo]
        ACTUALIZADA: _ClassVar[EventoAlerta.Tipo]
        CERRADA: _ClassVar[EventoAlerta.Tipo]
    TIPO_DESCONOCIDO: EventoAlerta.Tipo
    ACTIVA: EventoAlerta.Tipo
    NUEVA: EventoAlerta.Tipo
    ACTUALIZADA: EventoAlerta.Tipo
    CERRADA: EventoAlerta.Tipo
    TIPO_FIELD_NUMBER: _ClassVar[int]
    ALERTA_FIELD_NUMBER: _ClassVar[int]
    MOMENTO_FIELD_NUMBER: _ClassVar[int]
    tipo: EventoAlerta.Tipo
    alerta: Alerta
    momento: str
    def __init__(self, tipo: _Optional[_Union[EventoAlerta.Tipo, str]] = ..., alerta: _Optional[_Union[Alerta, _Mapping]] = ..., momento: _Optional[str] = ...) -> None: ...

class FilaReporteFarmacia(_message.Message):
    __slots__ = ("fila", "farmacia_id", "anio", "semana_epi", "categoria", "unidades")
    FILA_FIELD_NUMBER: _ClassVar[int]
    FARMACIA_ID_FIELD_NUMBER: _ClassVar[int]
    ANIO_FIELD_NUMBER: _ClassVar[int]
    SEMANA_EPI_FIELD_NUMBER: _ClassVar[int]
    CATEGORIA_FIELD_NUMBER: _ClassVar[int]
    UNIDADES_FIELD_NUMBER: _ClassVar[int]
    fila: int
    farmacia_id: int
    anio: int
    semana_epi: int
    categoria: str
    unidades: int
    def __init__(self, fila: _Optional[int] = ..., farmacia_id: _Optional[int] = ..., anio: _Optional[int] = ..., semana_epi: _Optional[int] = ..., categoria: _Optional[str] = ..., unidades: _Optional[int] = ...) -> None: ...

class ErrorFila(_message.Message):
    __slots__ = ("fila", "mensaje")
    FILA_FIELD_NUMBER: _ClassVar[int]
    MENSAJE_FIELD_NUMBER: _ClassVar[int]
    fila: int
    mensaje: str
    def __init__(self, fila: _Optional[int] = ..., mensaje: _Optional[str] = ...) -> None: ...

class ResumenCarga(_message.Message):
    __slots__ = ("filas_recibidas", "filas_rechazadas", "semanas_creadas", "semanas_actualizadas", "semanas_rechazadas", "errores")
    FILAS_RECIBIDAS_FIELD_NUMBER: _ClassVar[int]
    FILAS_RECHAZADAS_FIELD_NUMBER: _ClassVar[int]
    SEMANAS_CREADAS_FIELD_NUMBER: _ClassVar[int]
    SEMANAS_ACTUALIZADAS_FIELD_NUMBER: _ClassVar[int]
    SEMANAS_RECHAZADAS_FIELD_NUMBER: _ClassVar[int]
    ERRORES_FIELD_NUMBER: _ClassVar[int]
    filas_recibidas: int
    filas_rechazadas: int
    semanas_creadas: int
    semanas_actualizadas: int
    semanas_rechazadas: int
    errores: _containers.RepeatedCompositeFieldContainer[ErrorFila]
    def __init__(self, filas_recibidas: _Optional[int] = ..., filas_rechazadas: _Optional[int] = ..., semanas_creadas: _Optional[int] = ..., semanas_actualizadas: _Optional[int] = ..., semanas_rechazadas: _Optional[int] = ..., errores: _Optional[_Iterable[_Union[ErrorFila, _Mapping]]] = ...) -> None: ...

class Escenario(_message.Message):
    __slots__ = ("id", "municipio_id", "enfermedad_id", "delta_temperatura_c", "cambio_lluvia_pct", "cambio_busquedas_pct", "cambio_farmacias_pct", "ceniza")
    ID_FIELD_NUMBER: _ClassVar[int]
    MUNICIPIO_ID_FIELD_NUMBER: _ClassVar[int]
    ENFERMEDAD_ID_FIELD_NUMBER: _ClassVar[int]
    DELTA_TEMPERATURA_C_FIELD_NUMBER: _ClassVar[int]
    CAMBIO_LLUVIA_PCT_FIELD_NUMBER: _ClassVar[int]
    CAMBIO_BUSQUEDAS_PCT_FIELD_NUMBER: _ClassVar[int]
    CAMBIO_FARMACIAS_PCT_FIELD_NUMBER: _ClassVar[int]
    CENIZA_FIELD_NUMBER: _ClassVar[int]
    id: str
    municipio_id: int
    enfermedad_id: int
    delta_temperatura_c: float
    cambio_lluvia_pct: float
    cambio_busquedas_pct: float
    cambio_farmacias_pct: float
    ceniza: bool
    def __init__(self, id: _Optional[str] = ..., municipio_id: _Optional[int] = ..., enfermedad_id: _Optional[int] = ..., delta_temperatura_c: _Optional[float] = ..., cambio_lluvia_pct: _Optional[float] = ..., cambio_busquedas_pct: _Optional[float] = ..., cambio_farmacias_pct: _Optional[float] = ..., ceniza: _Optional[bool] = ...) -> None: ...

class ResultadoEscenario(_message.Message):
    __slots__ = ("id", "municipio_id", "enfermedad_id", "base", "escenario", "nivel_max", "variacion_pct", "resumen", "duracion_ms", "error")
    ID_FIELD_NUMBER: _ClassVar[int]
    MUNICIPIO_ID_FIELD_NUMBER: _ClassVar[int]
    ENFERMEDAD_ID_FIELD_NUMBER: _ClassVar[int]
    BASE_FIELD_NUMBER: _ClassVar[int]
    ESCENARIO_FIELD_NUMBER: _ClassVar[int]
    NIVEL_MAX_FIELD_NUMBER: _ClassVar[int]
    VARIACION_PCT_FIELD_NUMBER: _ClassVar[int]
    RESUMEN_FIELD_NUMBER: _ClassVar[int]
    DURACION_MS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    id: str
    municipio_id: int
    enfermedad_id: int
    base: _containers.RepeatedCompositeFieldContainer[PuntoPronostico]
    escenario: _containers.RepeatedCompositeFieldContainer[PuntoPronostico]
    nivel_max: NivelRiesgo
    variacion_pct: float
    resumen: str
    duracion_ms: float
    error: str
    def __init__(self, id: _Optional[str] = ..., municipio_id: _Optional[int] = ..., enfermedad_id: _Optional[int] = ..., base: _Optional[_Iterable[_Union[PuntoPronostico, _Mapping]]] = ..., escenario: _Optional[_Iterable[_Union[PuntoPronostico, _Mapping]]] = ..., nivel_max: _Optional[_Union[NivelRiesgo, str]] = ..., variacion_pct: _Optional[float] = ..., resumen: _Optional[str] = ..., duracion_ms: _Optional[float] = ..., error: _Optional[str] = ...) -> None: ...
