"""Carga masiva de datos desde CSV (panel de administración).

Cada tipo de archivo tiene su propio importador (patrón Strategy): valida las columnas,
convierte cada fila y la guarda con inserción o actualización (si se sube el mismo archivo
dos veces no se duplican datos). Las filas con errores no detienen la carga: se informan con
su número de línea para que el administrador las corrija.

Formatos (encabezados obligatorios en la primera fila; separador , o ;):
    casos       cod_divipola, enfermedad, anio, semana_epi, casos
    clima       cod_divipola, fecha, temp_max_c, temp_min_c, temp_media_c, precipitacion_mm, humedad_relativa_pct
    eventos     tipo, nivel_actividad, fecha_inicio, cod_divipola, intensidad_ceniza, so2_ton_dia, descripcion
    tendencias  termino, fecha_semana, indice
"""
import csv
import io
from abc import ABC, abstractmethod
from datetime import date

from sqlalchemy import func, select

from app.core.epi import etiqueta, semana_de, semanas_del_anio
from app.core.errors import ReglaNegocioError
from app.models import (
    CasoOficial,
    EventoVolcanico,
    ModeloEntrenado,
    Prediccion,
    RegistroClima,
    ReporteFarmacia,
    TendenciaBusqueda,
)
from app.models.enums import NivelVolcanico, TipoEventoVolcanico
from app.repositories.repos import (
    CasoOficialRepository,
    EnfermedadRepository,
    EventoVolcanicoRepository,
    MunicipioRepository,
    RegistroClimaRepository,
    TendenciaRepository,
)
from app.schemas.datos import ErrorFila, EstadoDatos, EstadoFuente, ResultadoImportacion

TAMANO_MAXIMO = 5 * 1024 * 1024  # 5 MB
MAX_ERRORES = 50


class FilaInvalidaError(ValueError):
    pass


def _iso(momento) -> str | None:
    return momento.isoformat() if momento else None


def _entero(valor: str, campo: str, minimo: int | None = None, maximo: int | None = None) -> int:
    try:
        n = int(float(valor.strip()))
    except (ValueError, AttributeError):
        raise FilaInvalidaError(f"«{campo}» debe ser un número entero (llegó «{valor}»)") from None
    if (minimo is not None and n < minimo) or (maximo is not None and n > maximo):
        raise FilaInvalidaError(f"«{campo}» fuera de rango ({n})")
    return n


def _decimal(valor: str | None, campo: str) -> float | None:
    if valor is None or valor.strip() == "":
        return None
    try:
        return float(valor.strip().replace(",", "."))
    except ValueError:
        raise FilaInvalidaError(f"«{campo}» debe ser numérico (llegó «{valor}»)") from None


def _fecha(valor: str, campo: str) -> date:
    try:
        return date.fromisoformat(valor.strip())
    except (ValueError, AttributeError):
        raise FilaInvalidaError(f"«{campo}» debe tener formato AAAA-MM-DD (llegó «{valor}»)") from None


class Importador(ABC):
    tipo: str
    columnas: tuple[str, ...]

    def __init__(self, db):
        self.db = db
        self.municipios = {m.codigo_divipola: m.id for m in MunicipioRepository(db).listar(limit=1000)}

    def municipio(self, cod: str) -> int:
        mid = self.municipios.get((cod or "").strip().zfill(5))
        if mid is None:
            raise FilaInvalidaError(f"Municipio con DIVIPOLA «{cod}» no está registrado")
        return mid

    @abstractmethod
    def convertir(self, fila: dict[str, str]) -> dict: ...

    @abstractmethod
    def guardar(self, filas: list[dict]) -> tuple[int, int]: ...


class ImportadorCasos(Importador):
    tipo = "casos"
    columnas = ("cod_divipola", "enfermedad", "anio", "semana_epi", "casos")

    def __init__(self, db):
        super().__init__(db)
        self.enfermedades = {e.codigo: e.id for e in EnfermedadRepository(db).listar(limit=1000)}

    def convertir(self, f):
        eid = self.enfermedades.get(f["enfermedad"].strip().upper())
        if eid is None:
            raise FilaInvalidaError(f"Enfermedad «{f['enfermedad']}» no existe (usa el código, p. ej. IRA)")
        anio = _entero(f["anio"], "anio", 2000, 2100)
        return {"municipio_id": self.municipio(f["cod_divipola"]), "enfermedad_id": eid, "anio": anio,
                "semana_epi": _entero(f["semana_epi"], "semana_epi", 1, semanas_del_anio(anio)),
                "casos": _entero(f["casos"], "casos", 0), "fuente": "CSV", "es_simulado": False}

    def guardar(self, filas):
        return CasoOficialRepository(self.db).upsert_lote(filas)


class ImportadorClima(Importador):
    tipo = "clima"
    columnas = ("cod_divipola", "fecha", "temp_max_c", "temp_min_c", "temp_media_c", "precipitacion_mm",
                "humedad_relativa_pct")

    def convertir(self, f):
        fila = {"municipio_id": self.municipio(f["cod_divipola"]), "fecha": _fecha(f["fecha"], "fecha"),
                "es_pronostico": False, "es_simulado": False, "fuente": "CSV"}
        for c in self.columnas[2:]:
            fila[c] = _decimal(f.get(c), c)
        h = fila["humedad_relativa_pct"]
        if h is not None and not 0 <= h <= 100:
            raise FilaInvalidaError("La humedad debe estar entre 0 y 100")
        if fila["precipitacion_mm"] is not None and fila["precipitacion_mm"] < 0:
            raise FilaInvalidaError("La precipitación no puede ser negativa")
        return fila

    def guardar(self, filas):
        return RegistroClimaRepository(self.db).upsert(filas, ("municipio_id", "fecha"), [
            RegistroClima.municipio_id.in_({f["municipio_id"] for f in filas}),
            RegistroClima.fecha.in_({f["fecha"] for f in filas})])


class ImportadorEventos(Importador):
    tipo = "eventos"
    columnas = ("tipo", "nivel_actividad", "fecha_inicio", "cod_divipola", "intensidad_ceniza", "so2_ton_dia",
                "descripcion")

    def convertir(self, f):
        tipo = f["tipo"].strip().upper()
        nivel = f["nivel_actividad"].strip().upper()
        if tipo not in {t.value for t in TipoEventoVolcanico}:
            raise FilaInvalidaError(f"Tipo «{f['tipo']}» no válido")
        if nivel not in {n.value for n in NivelVolcanico}:
            raise FilaInvalidaError(f"Nivel «{f['nivel_actividad']}» no válido (VERDE, AMARILLO, NARANJA o ROJO)")
        cod = (f.get("cod_divipola") or "").strip()
        intensidad = _entero(f.get("intensidad_ceniza") or "0", "intensidad_ceniza", 0, 3)
        if tipo == TipoEventoVolcanico.CAIDA_CENIZA and (not cod or intensidad == 0):
            raise FilaInvalidaError("Una caída de ceniza necesita municipio e intensidad entre 1 y 3")
        return {"tipo": tipo, "nivel_actividad": nivel, "fecha_inicio": _fecha(f["fecha_inicio"], "fecha_inicio"),
                "municipio_id": self.municipio(cod) if cod else None, "intensidad_ceniza": intensidad,
                "so2_ton_dia": _decimal(f.get("so2_ton_dia"), "so2_ton_dia"),
                "descripcion": (f.get("descripcion") or "").strip() or None, "es_simulado": False}

    def guardar(self, filas):
        # Clave natural: un evento por tipo, fecha y municipio (o ninguno, para los boletines)
        return EventoVolcanicoRepository(self.db).upsert(
            filas, ("tipo", "fecha_inicio", "municipio_id"),
            [EventoVolcanico.fecha_inicio.in_({f["fecha_inicio"] for f in filas})])


class ImportadorTendencias(Importador):
    tipo = "tendencias"
    columnas = ("termino", "fecha_semana", "indice")

    def convertir(self, f):
        fecha = _fecha(f["fecha_semana"], "fecha_semana")
        anio, semana = semana_de(fecha)
        indice = _decimal(f["indice"], "indice")
        if indice is None or not 0 <= indice <= 100:
            raise FilaInvalidaError("El índice de Google Trends va de 0 a 100")
        termino = f["termino"].strip().lower()
        if len(termino) < 2:
            raise FilaInvalidaError("Término vacío")
        return {"termino": termino, "region": "CO-NAR", "anio": anio, "semana_epi": semana, "fecha_semana": fecha,
                "indice": indice, "fuente": "csv", "es_simulado": False}

    def guardar(self, filas):
        return TendenciaRepository(self.db).upsert(filas, ("termino", "region", "anio", "semana_epi"),
                                                   [TendenciaBusqueda.termino.in_({f["termino"] for f in filas})])


IMPORTADORES: dict[str, type[Importador]] = {
    c.tipo: c for c in (ImportadorCasos, ImportadorClima, ImportadorEventos, ImportadorTendencias)
}


class ImportacionService:
    def __init__(self, db):
        self.db = db

    def importar(self, tipo: str, contenido: bytes) -> ResultadoImportacion:
        clase = IMPORTADORES.get(tipo)
        if clase is None:
            raise ReglaNegocioError(f"Tipo «{tipo}» no soportado. Usa: {', '.join(IMPORTADORES)}")
        if len(contenido) > TAMANO_MAXIMO:
            raise ReglaNegocioError("El archivo supera 5 MB")
        try:
            texto = contenido.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = contenido.decode("latin-1")  # Excel en Windows suele guardar en ANSI
        if not texto.strip():
            raise ReglaNegocioError("El archivo está vacío")
        try:
            dialecto = csv.Sniffer().sniff(texto.splitlines()[0], delimiters=",;")
        except csv.Error:
            dialecto = csv.excel
        lector = csv.DictReader(io.StringIO(texto), dialect=dialecto)
        lector.fieldnames = [(c or "").strip().lower() for c in (lector.fieldnames or [])]
        imp = clase(self.db)
        faltan = [c for c in imp.columnas if c not in lector.fieldnames and c not in ("descripcion", "so2_ton_dia",
                                                                                         "cod_divipola",
                                                                                         "intensidad_ceniza")]
        if faltan:
            raise ReglaNegocioError(f"Faltan columnas: {', '.join(faltan)}",
                                    detalles={"esperadas": list(imp.columnas), "recibidas": lector.fieldnames})
        validas, errores, leidas = [], [], 0
        for n, fila in enumerate(lector, start=2):  # la fila 1 es el encabezado
            leidas += 1
            try:
                validas.append(imp.convertir({k: (v or "") for k, v in fila.items() if k}))
            except FilaInvalidaError as exc:
                if len(errores) < MAX_ERRORES:
                    errores.append(ErrorFila(fila=n, mensaje=str(exc)))
        insertadas, actualizadas = imp.guardar(validas) if validas else (0, 0)
        return ResultadoImportacion(tipo=tipo, filas_leidas=leidas, insertadas=insertadas, actualizadas=actualizadas,
                                    errores=errores)

    # ── Estado de las fuentes (para el panel) ───────────────────────────────
    def estado(self) -> EstadoDatos:
        def contar(modelo, simulado=None, **extra):
            stmt = select(func.count()).select_from(modelo)
            if simulado is not None:
                stmt = stmt.where(modelo.es_simulado.is_(simulado))
            return self.db.scalar(stmt) or 0

        def ultima(modelo) -> str | None:
            fila = self.db.execute(select(modelo.anio, modelo.semana_epi)
                                   .order_by(modelo.anio.desc(), modelo.semana_epi.desc()).limit(1)).first()
            return etiqueta(*fila) if fila else None

        def actualizado(modelo) -> str | None:
            v = self.db.scalar(select(func.max(modelo.actualizado_en)))
            return v.isoformat() if v else None

        ultima_fecha = self.db.scalar(
            select(func.max(RegistroClima.fecha)).where(RegistroClima.es_pronostico.is_(False)))
        fuentes = [
            EstadoFuente(fuente="Casos oficiales (SIVIGILA / CSV)", tabla="casos_oficiales",
                         registros=contar(CasoOficial),
                         simulados=contar(CasoOficial, True), ultima_semana=ultima(CasoOficial),
                         ultima_actualizacion=actualizado(CasoOficial)),
            EstadoFuente(fuente="Clima (Open-Meteo)", tabla="registros_clima", registros=contar(RegistroClima),
                         simulados=contar(RegistroClima, True),
                         ultima_semana=etiqueta(*semana_de(ultima_fecha)) if ultima_fecha else None,
                         ultima_actualizacion=actualizado(RegistroClima)),
            EstadoFuente(fuente="Búsquedas (Google Trends)", tabla="tendencias_busqueda",
                         registros=contar(TendenciaBusqueda), simulados=contar(TendenciaBusqueda, True),
                         ultima_semana=ultima(TendenciaBusqueda), ultima_actualizacion=actualizado(TendenciaBusqueda)),
            EstadoFuente(fuente="Reportes de farmacias", tabla="reportes_farmacia", registros=contar(ReporteFarmacia),
                         simulados=contar(ReporteFarmacia, True), ultima_semana=ultima(ReporteFarmacia),
                         ultima_actualizacion=actualizado(ReporteFarmacia)),
            EstadoFuente(fuente="Eventos volcánicos (SGC)", tabla="eventos_volcanicos",
                         registros=contar(EventoVolcanico), simulados=contar(EventoVolcanico, True),
                         ultima_semana=None, ultima_actualizacion=actualizado(EventoVolcanico)),
            EstadoFuente(fuente="Predicciones del modelo", tabla="predicciones", registros=contar(Prediccion),
                         simulados=0, ultima_semana=ultima(Prediccion),
                         ultima_actualizacion=_iso(self.db.scalar(select(func.max(ModeloEntrenado.fecha_entrenamiento))))),
        ]
        return EstadoDatos(fuentes=fuentes)
