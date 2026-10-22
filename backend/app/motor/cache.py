"""Modelos en memoria del motor.

Deserializar un artefacto y construir el dataset semanal cuesta cientos de milisegundos; la API
REST lo pagaba en cada petición. El motor es un proceso de larga vida, así que guarda un
`Pronosticador` por enfermedad y solo lo reconstruye cuando:

- cambia el modelo activo (alguien reentrenó, aquí o desde la API), o
- pasa `ttl_s` (llegaron datos nuevos con el cron aunque el modelo sea el mismo).

Cada consulta hace una sola lectura barata (id del modelo activo) para saber si la entrada
sigue vigente. Un candado por enfermedad evita que dos hilos construyan lo mismo a la vez.
"""
import threading
import time
from dataclasses import dataclass

from sqlalchemy import select

from app.core.errors import NoEncontradoError
from app.ml.dataset import ConstructorDataset
from app.ml.entrenador import Entrenador
from app.ml.pronostico import Pronosticador
from app.models import Enfermedad, ModeloEntrenado, Municipio


@dataclass(frozen=True)
class ModeloCargado:
    modelo_id: int
    algoritmo: str
    enfermedad: str
    municipios: dict[int, str]
    pronosticador: Pronosticador
    cargado_en: float


class CacheModelos:
    def __init__(self, ttl_s: float = 900.0, reloj=time.monotonic):
        self.ttl_s = ttl_s
        self._reloj = reloj
        self._entradas: dict[int, ModeloCargado] = {}
        self._candados: dict[int, threading.Lock] = {}
        self._candado_global = threading.Lock()

    def __len__(self) -> int:
        return len(self._entradas)

    def _candado(self, enfermedad_id: int) -> threading.Lock:
        with self._candado_global:
            return self._candados.setdefault(enfermedad_id, threading.Lock())

    def invalidar(self, enfermedad_id: int | None = None) -> None:
        with self._candado_global:
            if enfermedad_id is None:
                self._entradas.clear()
            else:
                self._entradas.pop(enfermedad_id, None)

    def _vigente(self, entrada: ModeloCargado | None, modelo_id: int) -> bool:
        return (entrada is not None and entrada.modelo_id == modelo_id
                and self._reloj() - entrada.cargado_en < self.ttl_s)

    def obtener(self, db, enfermedad_id: int) -> tuple[ModeloCargado, bool]:
        """(modelo cargado, venía de la caché). Lanza NoEncontradoError si no hay modelo activo."""
        fila = db.execute(select(ModeloEntrenado.id).where(
            ModeloEntrenado.enfermedad_id == enfermedad_id, ModeloEntrenado.activo.is_(True),
            ModeloEntrenado.artefacto.is_not(None)).order_by(ModeloEntrenado.id.desc()).limit(1)).first()
        if fila is None:
            raise NoEncontradoError("Esta enfermedad aún no tiene un modelo entrenado")
        modelo_id = fila[0]
        if self._vigente(self._entradas.get(enfermedad_id), modelo_id):
            return self._entradas[enfermedad_id], True
        with self._candado(enfermedad_id):
            entrada = self._entradas.get(enfermedad_id)
            if self._vigente(entrada, modelo_id):  # otro hilo la cargó mientras esperábamos
                return entrada, True
            entrada = self._cargar(db, enfermedad_id, modelo_id)
            self._entradas[enfermedad_id] = entrada
            return entrada, False

    def _cargar(self, db, enfermedad_id: int, modelo_id: int) -> ModeloCargado:
        enf = db.get(Enfermedad, enfermedad_id)
        modelo = db.get(ModeloEntrenado, modelo_id)
        df = ConstructorDataset(db).construir(enf)
        pron = Pronosticador(enf, Entrenador.deserializar(modelo.artefacto), df)
        nombres = dict(db.execute(select(Municipio.id, Municipio.nombre)).all())
        return ModeloCargado(modelo_id=modelo_id, algoritmo=modelo.algoritmo, enfermedad=enf.nombre,
                             municipios={m: nombres.get(m, str(m)) for m in pron.municipios()},
                             pronosticador=pron, cargado_en=self._reloj())
