"""Construcción del dataset semanal (municipio × semana epidemiológica) para el modelo.

Cada fila representa "lo que se sabe al cerrar la semana t" en un municipio. Todas las
variables usan información de la semana t o anteriores; los objetivos son los casos de
t+1 ... t+4. Así no hay fuga de datos (el error del XGBoost del sistema anterior).

Variables por grupo (los grupos se usan para explicar las predicciones):
    Casos recientes   rezagos 0-3 de log(1+casos), promedios móviles de 4 y 8 semanas, tasa x 100 mil
    Estacionalidad    casos de las mismas semanas del año anterior, seno/coseno de la semana
    Clima             temperatura, lluvia y humedad con rezagos (dengue: 4-6 semanas)
    Búsquedas         índice de Google Trends de los términos de la enfermedad y su variación
    Farmacias         índice de ventas de las categorías asociadas
    Volcán            SO₂ del boletín y caída de ceniza en el municipio (rezagos 0-3)
    Municipio         población y altitud
"""
import math
from collections import defaultdict

import numpy as np
import pandas as pd
from sqlalchemy import select

from app.core.epi import desplazar, iterar_semanas, semana_de
from app.fuentes.farmacia import FarmaciaFuente
from app.models import CasoOficial, Enfermedad, EventoVolcanico, RegistroClima
from app.repositories.repos import MunicipioRepository
from app.services.tendencia_service import TendenciaService

HORIZONTES = (1, 2, 3, 4)

GRUPOS: dict[str, list[str]] = {
    "Casos recientes": ["y_l0", "y_l1", "y_l2", "y_l3", "y_ma4", "y_ma8", "tasa_l0"],
    "Estacionalidad": ["y_anio_ant", "sem_sin", "sem_cos"],
    "Clima": ["temp_l0", "temp_l2", "temp_l4_6", "lluvia_l0", "lluvia_l1", "lluvia_l2_6", "hum_l0", "hum_l1"],
    "Búsquedas en internet": ["busq_l0", "busq_l1", "busq_var"],
    "Ventas en farmacias": ["farm_l0", "farm_l1"],
    "Actividad volcánica": ["so2_l0", "ceniza_l0_1", "ceniza_l2_3"],
    "Municipio": ["log_poblacion", "altitud_km"],
}
FEATURES: list[str] = [f for fs in GRUPOS.values() for f in fs]
OBJETIVOS = [f"y_h{h}" for h in HORIZONTES]


def grupo_de(feature: str) -> str:
    return next(g for g, fs in GRUPOS.items() if feature in fs)


class ConstructorDataset:
    def __init__(self, db):
        self.db = db

    # ── series crudas ─────────────────────────────────────────────────────────
    def _casos(self, enfermedad_id: int) -> pd.DataFrame:
        filas = self.db.execute(select(CasoOficial.municipio_id, CasoOficial.anio, CasoOficial.semana_epi,
                                       CasoOficial.casos).where(CasoOficial.enfermedad_id == enfermedad_id)).all()
        return pd.DataFrame(filas, columns=["municipio_id", "anio", "semana_epi", "casos"])

    def _clima(self) -> dict[tuple[int, int, int], dict[str, float]]:
        filas = self.db.execute(select(RegistroClima.municipio_id, RegistroClima.fecha, RegistroClima.temp_media_c,
                                       RegistroClima.precipitacion_mm, RegistroClima.humedad_relativa_pct)
                                .where(RegistroClima.es_pronostico.is_(False))).all()
        acum: dict[tuple[int, int, int], list] = defaultdict(list)
        for mid, fecha, t, p, h in filas:
            acum[(mid, *semana_de(fecha))].append((t, p, h))

        def prom(vs):
            vs = [v for v in vs if v is not None]
            return float(np.mean(vs)) if vs else np.nan

        return {k: {"t": prom([x[0] for x in v]), "p": float(np.nansum([x[1] for x in v if x[1] is not None]))
                    if any(x[1] is not None for x in v) else np.nan, "h": prom([x[2] for x in v])}
                for k, v in acum.items()}

    def _volcan(self) -> tuple[dict[tuple[int, int], float], dict[tuple[int, int, int], int]]:
        so2: dict[tuple[int, int], list[float]] = defaultdict(list)
        ceniza: dict[tuple[int, int, int], int] = {}
        for e in self.db.scalars(select(EventoVolcanico)):
            k = semana_de(e.fecha_inicio)
            if e.so2_ton_dia is not None:
                so2[k].append(e.so2_ton_dia)
            if e.tipo == "CAIDA_CENIZA" and e.municipio_id:
                kk = (e.municipio_id, *k)
                ceniza[kk] = max(ceniza.get(kk, 0), e.intensidad_ceniza)
        return {k: float(np.mean(v)) for k, v in so2.items()}, ceniza

    def _farmacia(self, enf: Enfermedad) -> dict[tuple[int, int, int], float]:
        cats = enf.lista_categorias_farmacia
        if not cats:
            return {}
        acum: dict[tuple[int, int, int], list[float]] = defaultdict(list)
        for f in FarmaciaFuente(self.db).obtener(categorias=cats):
            if f["indice"] is not None:
                acum[(f["municipio_id"], f["anio"], f["semana_epi"])].append(f["indice"])
        return {k: float(np.mean(v)) for k, v in acum.items()}

    # ── dataset ───────────────────────────────────────────────────────────────
    def construir(self, enf: Enfermedad) -> pd.DataFrame:
        casos = self._casos(enf.id)
        if casos.empty:
            return pd.DataFrame(columns=["municipio_id", "anio", "semana_epi", "casos", *FEATURES, *OBJETIVOS])
        inicio = tuple(casos.sort_values(["anio", "semana_epi"]).iloc[0][["anio", "semana_epi"]].astype(int))
        fin = tuple(casos.sort_values(["anio", "semana_epi"]).iloc[-1][["anio", "semana_epi"]].astype(int))
        semanas = list(iterar_semanas(inicio, fin))
        indice_semana = {k: i for i, k in enumerate(semanas)}

        clima = self._clima()
        so2, ceniza = self._volcan()
        busq = TendenciaService(self.db).indice_por_semana(enf)
        farm = self._farmacia(enf)
        municipios = {m.id: m for m in MunicipioRepository(self.db).activos()}

        bloques = []
        for mid, grupo in casos.groupby("municipio_id"):
            m = municipios.get(int(mid))
            if m is None:
                continue
            serie = dict(zip(zip(grupo["anio"], grupo["semana_epi"]), grupo["casos"]))
            y = np.array([serie.get(k, 0) for k in semanas], dtype=float)
            df = pd.DataFrame({"municipio_id": int(mid), "anio": [a for a, _ in semanas],
                               "semana_epi": [s for _, s in semanas], "t_idx": range(len(semanas)), "casos": y})
            ly = np.log1p(pd.Series(y))
            for k in range(4):
                df[f"y_l{k}"] = ly.shift(k)
            df["y_ma4"] = np.log1p(pd.Series(y).rolling(4).mean())
            df["y_ma8"] = np.log1p(pd.Series(y).rolling(8).mean())
            df["tasa_l0"] = y / m.poblacion * 100_000
            # Mismas semanas del año anterior que las semanas objetivo (t+1..t+4 → t-51..t-48)
            df["y_anio_ant"] = np.log1p(pd.Series(y).shift(48).rolling(4).mean())
            df["sem_sin"] = [math.sin(2 * math.pi * s / 52.18) for _, s in semanas]
            df["sem_cos"] = [math.cos(2 * math.pi * s / 52.18) for _, s in semanas]

            def col(fuente: dict, clave, campo=None, lag=0):
                vals = []
                for a, s in semanas:
                    kk = desplazar(a, s, -lag)
                    v = fuente.get(clave(kk))
                    vals.append(np.nan if v is None else (v.get(campo, np.nan) if campo else v))
                return pd.Series(vals, dtype=float)

            cm = lambda kk: (int(mid), *kk)  # noqa: E731 - clave de clima/farmacia/ceniza por municipio
            temp = col(clima, cm, "t")
            lluvia = col(clima, cm, "p")
            hum = col(clima, cm, "h")
            df["temp_l0"], df["temp_l2"] = temp, temp.shift(2)
            df["temp_l4_6"] = temp.shift(4).rolling(3, min_periods=1).mean()
            df["lluvia_l0"], df["lluvia_l1"] = lluvia, lluvia.shift(1)
            df["lluvia_l2_6"] = lluvia.shift(2).rolling(5, min_periods=2).mean()
            df["hum_l0"], df["hum_l1"] = hum, hum.shift(1)

            b = col(busq, lambda kk: kk)
            df["busq_l0"], df["busq_l1"] = b, b.shift(1)
            df["busq_var"] = b / b.shift(1).rolling(8, min_periods=4).mean()

            f = col(farm, cm)
            df["farm_l0"], df["farm_l1"] = f, f.shift(1)

            df["so2_l0"] = col(so2, lambda kk: kk).ffill(limit=4)
            cz = col(ceniza, cm).fillna(0)
            df["ceniza_l0_1"] = cz.rolling(2, min_periods=1).max()
            df["ceniza_l2_3"] = cz.shift(2).rolling(2, min_periods=1).max()

            df["log_poblacion"] = math.log(m.poblacion)
            df["altitud_km"] = (m.altitud_m or 0) / 1000
            for h in HORIZONTES:
                df[f"y_h{h}"] = pd.Series(y).shift(-h)
            bloques.append(df)

        datos = pd.concat(bloques, ignore_index=True) if bloques else pd.DataFrame()
        datos.attrs["semanas"] = semanas
        datos.attrs["indice_semana"] = indice_semana
        return datos


def filas_entrenables(df: pd.DataFrame, h: int) -> pd.DataFrame:
    """Filas con rezagos completos y objetivo conocido para el horizonte h."""
    return df[df["y_ma8"].notna() & df[f"y_h{h}"].notna()]


def ultima_fila_por_municipio(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values("t_idx").groupby("municipio_id").tail(1)
