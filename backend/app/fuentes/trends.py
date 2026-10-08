"""Adaptadores de búsquedas de síntomas en Google Trends.

`pytrends` no es una API oficial: Google limita las consultas (HTTP 429) y cambia el
formato sin aviso. Por eso hay tres niveles, del más fresco al más seguro:

1. `TrendsFuente` consulta Google Trends con pytrends.
2. Si falla, usa su respaldo `CsvTrendsFuente`: archivos CSV descargados a mano desde
   trends.google.com (formato "multiTimeline.csv") o en formato largo propio.
3. El servicio (`TendenciaService`) guarda todo en la tabla `tendencias_busqueda`, que
   funciona como caché: si la fuente no responde, el modelo sigue usando lo guardado.

Google normaliza cada consulta a 0-100 dentro del periodo pedido. Se consulta un término
por petición, para que cada serie tenga su propia escala. Para periodos de más de 5 años
(donde Google pasa a datos mensuales) se piden ventanas semanales solapadas y se empalman
reescalando con la media del solape.
"""
import csv
import io
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.epi import inicio_semana, semana_de
from app.fuentes.base import FuenteDatos, FuenteDatosError, logger

RAIZ_BACKEND = Path(__file__).resolve().parents[2]
VENTANA_DIAS = 1800  # < 5 años: Google entrega datos semanales
SOLAPE_DIAS = 364


def _fila(termino: str, region: str, fecha: date, indice: float, fuente: str, simulado: bool = False) -> dict[str, Any]:
    anio, semana = semana_de(fecha)
    return {
        "termino": termino, "region": region, "anio": anio, "semana_epi": semana,
        "fecha_semana": inicio_semana(anio, semana), "indice": round(float(indice), 2),
        "fuente": fuente, "es_simulado": simulado,
    }


def _valor(texto: str) -> float | None:
    texto = (texto or "").strip()
    if not texto:
        return None
    if texto.startswith("<"):  # Google escribe "<1" cuando el interés es muy bajo
        return 0.5
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def _fecha(texto: str) -> date | None:
    texto = texto.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            continue
    return None


class CsvTrendsFuente(FuenteDatos):
    """Lee CSV de Google Trends. Acepta dos formatos:

    - Exportación oficial de trends.google.com (multiTimeline.csv):
          Categoría: Todas las categorías
          <línea vacía>
          Semana,fiebre: (Nariño),dengue: (Nariño)
          2021-10-03,54,12
    - Formato largo propio: termino,fecha_semana,indice[,region][,es_simulado]
    """

    nombre = "csv"

    def __init__(self, directorio: str | Path | None = None):
        d = Path(directorio or settings.TRENDS_CSV_DIR)
        self.directorio = d if d.is_absolute() else RAIZ_BACKEND / d

    # ── parseo ────────────────────────────────────────────────────────────────
    @classmethod
    def parsear(cls, contenido: str, region: str = "CO-NAR") -> list[dict[str, Any]]:
        lineas = contenido.lstrip("﻿").splitlines()
        filas: list[dict[str, Any]] = []
        encabezado_largo = next((i for i, l in enumerate(lineas) if l.lower().startswith("termino,")), None)
        if encabezado_largo is not None:
            lector = csv.DictReader(io.StringIO("\n".join(lineas[encabezado_largo:])))
            for r in lector:
                f, v = _fecha(r.get("fecha_semana", "")), _valor(r.get("indice", ""))
                if f is None or v is None or not r.get("termino"):
                    continue
                simulado = str(r.get("es_simulado", "")).strip().lower() in ("1", "true", "si", "sí")
                filas.append(_fila(r["termino"].strip().lower(), (r.get("region") or region).strip(), f, v,
                                   "simulado" if simulado else cls.nombre, simulado))
            return filas

        # Formato de Google: buscar la fila de encabezados ("Semana", "Week", "Día"...)
        inicio = next((i for i, l in enumerate(lineas)
                       if l.split(",")[0].strip().lower() in ("semana", "week", "día", "dia", "day", "mes", "month")), None)
        if inicio is None:
            raise FuenteDatosError("CSV de Trends sin encabezado reconocible")
        lector = csv.reader(io.StringIO("\n".join(lineas[inicio:])))
        cabecera = next(lector)
        terminos = [c.split(":")[0].strip().lower() for c in cabecera[1:]]
        for r in lector:
            if not r:
                continue
            f = _fecha(r[0])
            if f is None:
                continue
            for termino, texto in zip(terminos, r[1:]):
                v = _valor(texto)
                if v is not None:
                    filas.append(_fila(termino, region, f, v, cls.nombre))
        return filas

    # ── Strategy ──────────────────────────────────────────────────────────────
    def obtener(self, *, terminos: list[str], region: str = "CO-NAR", desde: date | None = None,
                hasta: date | None = None, **_: Any) -> list[dict[str, Any]]:
        if not self.directorio.is_dir():
            raise FuenteDatosError(f"No existe el directorio de respaldo {self.directorio}")
        buscados = {t.lower() for t in terminos}
        por_clave: dict[tuple, dict] = {}
        for archivo in sorted(self.directorio.glob("*.csv")):
            try:
                filas = self.parsear(archivo.read_text(encoding="utf-8"), region)
            except (FuenteDatosError, UnicodeDecodeError) as exc:
                logger.warning("CSV de Trends %s ignorado: %s", archivo.name, exc)
                continue
            for f in filas:
                if f["termino"] not in buscados or f["region"] != region:
                    continue
                if (desde and f["fecha_semana"] < desde) or (hasta and f["fecha_semana"] > hasta):
                    continue
                por_clave[(f["termino"], f["anio"], f["semana_epi"])] = f  # el último archivo prevalece
        if not por_clave:
            raise FuenteDatosError("Los CSV de respaldo no tienen datos para esos términos")
        return sorted(por_clave.values(), key=lambda f: (f["termino"], f["fecha_semana"]))

    def verificar(self) -> None:
        if not any(self.directorio.glob("*.csv")):
            raise FuenteDatosError("No hay CSV de respaldo")


def _cliente_pytrends():  # pragma: no cover - depende de la red de Google
    from pytrends.request import TrendReq  # import diferido: pytrends es opcional

    return TrendReq(hl="es-CO", tz=300, timeout=(10, 25), retries=1, backoff_factor=0.5)


class TrendsFuente(FuenteDatos):
    """Google Trends vía pytrends con respaldo automático en CSV (cadena de responsabilidad)."""

    nombre = "pytrends"

    def __init__(self, respaldo: FuenteDatos | None = None, cliente_factory: Callable[[], Any] | None = None,
                 pausa: float | None = None, habilitado: bool | None = None):
        self.respaldo = respaldo if respaldo is not None else CsvTrendsFuente()
        self._factory = cliente_factory or _cliente_pytrends
        self.pausa = settings.TRENDS_PAUSA_SEGUNDOS if pausa is None else pausa
        self.habilitado = settings.TRENDS_HABILITADO if habilitado is None else habilitado
        self.ultima_fuente: str | None = None

    @staticmethod
    def ventanas(desde: date, hasta: date) -> list[tuple[date, date]]:
        """Ventanas de < 5 años, de la más reciente a la más antigua, con un año de solape."""
        salida, fin = [], hasta
        while True:
            ini = max(desde, fin - timedelta(days=VENTANA_DIAS))
            salida.append((ini, fin))
            if ini <= desde:
                return salida
            fin = ini + timedelta(days=SOLAPE_DIAS)

    @staticmethod
    def empalmar(series: list[dict[date, float]]) -> dict[date, float]:
        """Une ventanas (la primera es la más reciente) reescalando cada una con el solape."""
        unida = dict(series[0])
        for anterior in series[1:]:
            comunes = [d for d in anterior if d in unida]
            suma_ant = sum(anterior[d] for d in comunes)
            factor = (sum(unida[d] for d in comunes) / suma_ant) if comunes and suma_ant else 1.0
            for d, v in anterior.items():
                unida.setdefault(d, v * factor)
        tope = max(unida.values(), default=0) or 1.0
        return {d: v * 100 / tope for d, v in unida.items()}

    def _consultar(self, termino: str, region: str, desde: date, hasta: date) -> dict[date, float]:
        cliente = self._factory()
        series = []
        for ini, fin in self.ventanas(desde, hasta):
            cliente.build_payload([termino], geo=region, timeframe=f"{ini.isoformat()} {fin.isoformat()}")
            df = cliente.interest_over_time()
            if df is None or df.empty or termino not in df.columns:
                raise FuenteDatosError(f"Google Trends no devolvió datos para '{termino}'")
            if "isPartial" in df.columns:
                df = df[~df["isPartial"].astype(bool)]
            series.append({ts.date(): float(v) for ts, v in df[termino].items()})
            time.sleep(self.pausa)  # evita el bloqueo por exceso de consultas (HTTP 429)
        return self.empalmar(series)

    def obtener(self, *, terminos: list[str], region: str | None = None, desde: date,
                hasta: date | None = None, **_: Any) -> list[dict[str, Any]]:
        region = region or settings.TRENDS_REGION
        hasta = hasta or date.today()
        if self.habilitado:
            try:
                filas = []
                for t in terminos:
                    serie = self._consultar(t.lower(), region, desde, hasta)
                    filas += [_fila(t.lower(), region, d, v, self.nombre) for d, v in sorted(serie.items())]
                self.ultima_fuente = self.nombre
                logger.info("Google Trends: %d filas (%s)", len(filas), ", ".join(terminos))
                return filas
            except Exception as exc:  # noqa: BLE001 - pytrends lanza errores de muchos tipos
                logger.warning("pytrends falló (%s): se usa el CSV de respaldo", exc)
        filas = self.respaldo.obtener(terminos=terminos, region=region, desde=desde, hasta=hasta)
        self.ultima_fuente = self.respaldo.nombre
        return filas

    def verificar(self) -> None:  # pragma: no cover - red
        self._consultar("fiebre", settings.TRENDS_REGION, date.today() - timedelta(days=90), date.today())
