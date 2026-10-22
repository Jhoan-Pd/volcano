"""Entrena modelos, genera las predicciones de las próximas 4 semanas y las expone al dashboard.

Cada entrenamiento crea una fila en `modelos_entrenados` (fecha, algoritmo, MAE/RMSE de la
línea base y del modelo, importancias). Solo el último modelo de cada enfermedad queda
activo y conserva su artefacto serializado; los anteriores guardan sus métricas para el
historial pero se les borra el binario (la BD gratuita tiene 0,5 GB).
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy import delete, select, update

from app.core.epi import desplazar, etiqueta, inicio_semana
from app.core.errors import NoEncontradoError
from app.core.texto import numero_es
from app.ml.dataset import FEATURES, HORIZONTES, ConstructorDataset, ultima_fila_por_municipio
from app.ml.entrenador import DatosInsuficientesError, Entrenador
from app.ml.explicador import explicar
from app.models import Enfermedad, ModeloEntrenado, Municipio, Prediccion
from app.models.enums import NivelRiesgo
from app.repositories.repos import EnfermedadRepository
from app.schemas.dashboard import Umbrales
from app.schemas.modelo import (
    ExplicacionPrediccion, FactorExplicacion, ModeloOut, ModeloResumen, PrediccionEnfermedad,
    PuntoBacktest, PuntoPrediccion, ResumenPrediccion,
)
from app.services import riesgo_service as rs

logger = logging.getLogger("predictor.modelo")


def modelo_out(m: ModeloEntrenado, codigo: str) -> ModeloOut:
    mejora = None
    if m.mae_base and m.mae_modelo is not None:
        mejora = round((1 - m.mae_modelo / m.mae_base) * 100, 1)
    return ModeloOut(
        id=m.id, enfermedad_id=m.enfermedad_id, enfermedad=codigo, algoritmo=m.algoritmo, version=m.version,
        fecha_entrenamiento=m.fecha_entrenamiento, mae_base=m.mae_base, rmse_base=m.rmse_base, mae_modelo=m.mae_modelo,
        rmse_modelo=m.rmse_modelo, mejora_mae_pct=mejora, n_muestras=m.n_muestras, activo=m.activo,
        importancias=m.importancias, metricas=(m.parametros or {}).get("metricas"),
    )


class PrediccionService:
    """Una instancia vive lo que dura una petición: guarda en memoria el modelo activo de cada
    enfermedad y sus predicciones agrupadas por municipio, así el dashboard, las alertas y los
    reportes (que preguntan por 6 municipios × 4 enfermedades) no repiten la misma consulta."""

    def __init__(self, db, entrenador: Entrenador | None = None):
        self.db = db
        self.entrenador = entrenador or Entrenador()
        self.enfermedades = EnfermedadRepository(db)
        self._modelos: dict[int, ModeloEntrenado | None] = {}
        self._vigentes: dict[int, dict[int, list[Prediccion]]] = {}  # modelo → municipio → predicciones

    def _invalidar_cache(self) -> None:
        self._modelos.clear()
        self._vigentes.clear()

    # ── entrenamiento ─────────────────────────────────────────────────────────
    def entrenar(self, enfermedad_id: int | None = None) -> tuple[list[ModeloEntrenado], list[str]]:
        enfermedades = self.enfermedades.activas()
        if enfermedad_id is not None:
            enfermedades = [e for e in enfermedades if e.id == enfermedad_id]
            if not enfermedades:
                raise NoEncontradoError(f"Enfermedad {enfermedad_id} no existe o está inactiva")
        modelos, errores = [], []
        for enf in enfermedades:
            try:
                modelos.append(self.entrenar_enfermedad(enf))
            except DatosInsuficientesError as exc:
                errores.append(f"{enf.codigo}: {exc}")
        return modelos, errores

    def entrenar_enfermedad(self, enf: Enfermedad) -> ModeloEntrenado:
        df = ConstructorDataset(self.db).construir(enf)
        r = self.entrenador.entrenar(df)
        ahora = datetime.now(timezone.utc)
        # Solo el modelo vigente conserva el binario
        self.db.execute(update(ModeloEntrenado).where(ModeloEntrenado.enfermedad_id == enf.id)
                        .values(activo=False, artefacto=None))
        m = ModeloEntrenado(
            enfermedad_id=enf.id, algoritmo=r.algoritmo, version=ahora.strftime("%Y%m%d-%H%M%S"),
            fecha_entrenamiento=ahora, mae_base=r.mae_base, rmse_base=r.rmse_base, mae_modelo=r.mae_modelo,
            rmse_modelo=r.rmse_modelo, n_muestras=r.n_muestras, importancias=r.importancias,
            parametros={"clave": r.clave, "metricas": r.metricas, "cuantiles": r.cuantiles, "backtest": r.backtest,
                        "hiperparametros": r.parametros},
            artefacto=r.artefacto, activo=True,
        )
        self.db.add(m)
        self.db.commit()
        self._invalidar_cache()
        logger.info("Modelo %s: %s MAE %.3f (base %.3f)", enf.codigo, r.algoritmo, r.mae_modelo, r.mae_base)
        self.predecir_enfermedad(enf, m, df)
        return m

    # ── predicción ────────────────────────────────────────────────────────────
    def modelo_activo(self, enfermedad_id: int) -> ModeloEntrenado | None:
        if enfermedad_id not in self._modelos:
            self._modelos[enfermedad_id] = self.db.scalars(select(ModeloEntrenado).where(
                ModeloEntrenado.enfermedad_id == enfermedad_id, ModeloEntrenado.activo.is_(True))
                .order_by(ModeloEntrenado.id.desc()).limit(1)).first()
        return self._modelos[enfermedad_id]

    def predecir(self) -> int:
        total = 0
        for enf in self.enfermedades.activas():
            m = self.modelo_activo(enf.id)
            if m is not None and m.artefacto:
                total += self.predecir_enfermedad(enf, m)
        return total

    def predecir_enfermedad(self, enf: Enfermedad, modelo: ModeloEntrenado, df: pd.DataFrame | None = None) -> int:
        if df is None:
            df = ConstructorDataset(self.db).construir(enf)
        if df.empty:
            return 0
        art = Entrenador.deserializar(modelo.artefacto)
        medianas, cuantiles = art["medianas"], art["cuantiles"]
        terminos, categorias = enf.lista_terminos, enf.lista_categorias_farmacia
        nuevas = 0
        for _, fila in ultima_fila_por_municipio(df).iterrows():
            mid = int(fila["municipio_id"])
            serie = {(int(a), int(s)): c for a, s, c in
                     df.loc[df["municipio_id"] == mid, ["anio", "semana_epi", "casos"]].itertuples(index=False)}
            X = pd.DataFrame([fila[FEATURES].astype(float)], columns=FEATURES)
            # "Valor típico" del propio municipio (Pasto a 2 527 m no se compara con Consacá a 1 730 m)
            tipicos = df.loc[df["municipio_id"] == mid, FEATURES].median()
            med_m = {f: (medianas.get(f) if pd.isna(v) else float(v)) for f, v in tipicos.items()}
            for h in HORIZONTES:
                est = art["modelos"][h]
                p_log = float(est.predecir_log(X)[0])
                q10, q90 = cuantiles[str(h)]
                esperado = max(float(np.expm1(p_log)), 0.0)
                a, s = desplazar(int(fila["anio"]), int(fila["semana_epi"]), h)
                u = rs.calcular_umbrales([serie[p] for p in rs.semanas_referencia(a, s) if p in serie],
                                         enf.umbral_amarillo_pct, enf.umbral_naranja_pct, enf.umbral_rojo_pct)
                self.db.execute(delete(Prediccion).where(
                    Prediccion.modelo_id == modelo.id, Prediccion.municipio_id == mid, Prediccion.anio == a,
                    Prediccion.semana_epi == s, Prediccion.horizonte == h))
                exp = explicar(est, X, fila, med_m, terminos, categorias)
                exp["umbrales"] = {"amarillo": u.amarillo, "naranja": u.naranja, "rojo": u.rojo} if u else None
                self.db.add(Prediccion(
                    modelo_id=modelo.id, municipio_id=mid, enfermedad_id=enf.id, anio=a, semana_epi=s, horizonte=h,
                    casos_esperados=round(esperado, 2),
                    limite_inferior=round(max(float(np.expm1(p_log + q10)), 0.0), 2),
                    limite_superior=round(max(float(np.expm1(p_log + q90)), 0.0), 2),
                    nivel_riesgo=rs.clasificar(esperado, u).value, explicacion=exp,
                ))
                nuevas += 1
        self.db.commit()
        self._invalidar_cache()
        return nuevas

    # ── consultas ─────────────────────────────────────────────────────────────
    def ultimas_predicciones(self, modelo_id: int, municipio_id: int) -> list[Prediccion]:
        """Predicciones de la corrida más reciente (horizontes 1-4) de un modelo para un municipio.

        La primera llamada para un modelo carga TODAS sus predicciones en una sola consulta y las
        agrupa por municipio; las siguientes son una búsqueda en un diccionario (O(1))."""
        if modelo_id not in self._vigentes:
            por_municipio: dict[int, list[Prediccion]] = defaultdict(list)
            for p in self.db.scalars(select(Prediccion).where(Prediccion.modelo_id == modelo_id)):
                por_municipio[p.municipio_id].append(p)
            self._vigentes[modelo_id] = {mid: self._corrida_reciente(ps) for mid, ps in por_municipio.items()}
        return self._vigentes[modelo_id].get(municipio_id, [])

    @staticmethod
    def _corrida_reciente(predicciones: list[Prediccion]) -> list[Prediccion]:
        """De varias corridas semanales, solo la última (misma semana de origen), ordenada por horizonte."""
        def origen(p: Prediccion) -> tuple[int, int]:
            return desplazar(p.anio, p.semana_epi, -p.horizonte)
        ultima = max(map(origen, predicciones))
        return sorted((p for p in predicciones if origen(p) == ultima), key=lambda p: p.horizonte)

    def _enfermedad(self, enfermedad_id: int) -> Enfermedad:
        enf = self.enfermedades.obtener(enfermedad_id)
        if enf is None:
            raise NoEncontradoError(f"Enfermedad {enfermedad_id} no existe")
        return enf

    def prediccion(self, municipio_id: int, enfermedad_id: int) -> PrediccionEnfermedad:
        enf = self._enfermedad(enfermedad_id)
        m = self.modelo_activo(enf.id)
        if m is None:
            return PrediccionEnfermedad(municipio_id=municipio_id, enfermedad_id=enf.id, enfermedad=enf.nombre,
                                        semana_base=None, modelo=None, nivel_max=None, puntos=[], backtest=[])
        preds = self.ultimas_predicciones(m.id, municipio_id)
        puntos = []
        for p in preds:
            u = (p.explicacion or {}).get("umbrales")
            puntos.append(PuntoPrediccion(
                anio=p.anio, semana_epi=p.semana_epi, etiqueta=etiqueta(p.anio, p.semana_epi),
                fecha_inicio=inicio_semana(p.anio, p.semana_epi), horizonte=p.horizonte,
                casos_esperados=p.casos_esperados, limite_inferior=p.limite_inferior,
                limite_superior=p.limite_superior, nivel=p.nivel_riesgo, umbrales=Umbrales(**u) if u else None))
        backtest = [PuntoBacktest(anio=b["anio"], semana_epi=b["semana_epi"], etiqueta=etiqueta(b["anio"], b["semana_epi"]),
                                  real=b["real"], predicho=b["predicho"])
                    for b in (m.parametros or {}).get("backtest", []) if b["municipio_id"] == municipio_id]
        base = desplazar(preds[0].anio, preds[0].semana_epi, -1) if preds else None
        return PrediccionEnfermedad(
            municipio_id=municipio_id, enfermedad_id=enf.id, enfermedad=enf.nombre,
            semana_base=etiqueta(*base) if base else None,
            modelo=ModeloResumen(id=m.id, algoritmo=m.algoritmo, fecha_entrenamiento=m.fecha_entrenamiento,
                                 mae_base=m.mae_base, mae_modelo=m.mae_modelo, rmse_base=m.rmse_base,
                                 rmse_modelo=m.rmse_modelo),
            nivel_max=NivelRiesgo.peor(p.nivel for p in puntos).value if puntos else None, puntos=puntos, backtest=backtest)

    def resumen(self, municipio_id: int, enfermedad_id: int) -> ResumenPrediccion | None:
        m = self.modelo_activo(enfermedad_id)
        if m is None:
            return None
        preds = self.ultimas_predicciones(m.id, municipio_id)
        if not preds:
            return None
        pico = max(preds, key=lambda p: (NivelRiesgo(p.nivel_riesgo).rango, p.casos_esperados))
        h1 = preds[0]
        return ResumenPrediccion(nivel_max=pico.nivel_riesgo, semana_pico=etiqueta(pico.anio, pico.semana_epi),
                                 casos_esperados_h1=h1.casos_esperados, limite_inferior_h1=h1.limite_inferior,
                                 limite_superior_h1=h1.limite_superior, algoritmo=m.algoritmo)

    def explicacion(self, municipio_id: int, enfermedad_id: int, horizonte: int | None = None) -> ExplicacionPrediccion:
        enf = self._enfermedad(enfermedad_id)
        muni = self.db.get(Municipio, municipio_id)
        if muni is None:
            raise NoEncontradoError(f"Municipio {municipio_id} no existe")
        m = self.modelo_activo(enf.id)
        preds = self.ultimas_predicciones(m.id, municipio_id) if m else []
        if not preds:
            raise NoEncontradoError("Aún no hay predicciones. Un administrador debe entrenar el modelo.")
        if horizonte is None:  # por defecto se explica la semana de mayor riesgo
            p = max(preds, key=lambda x: (NivelRiesgo(x.nivel_riesgo).rango, x.casos_esperados))
        else:
            p = next((x for x in preds if x.horizonte == horizonte), preds[0])
        exp = p.explicacion or {}
        factores = [FactorExplicacion(**f) for f in exp.get("factores", [])]
        # Solo se mencionan los factores que mueven la predicción de forma apreciable
        umbral = max(0.1, 0.05 * p.casos_esperados)
        suben = [f for f in factores if f.direccion == "sube" and f.contribucion >= umbral]
        if suben:
            resumen = (f"Para la semana {etiqueta(p.anio, p.semana_epi)} se esperan {numero_es(p.casos_esperados)} casos. "
                       f"Lo que más empuja la predicción hacia arriba: {', '.join(f.grupo.lower() for f in suben[:3])}.")
        else:
            resumen = (f"Para la semana {etiqueta(p.anio, p.semana_epi)} se esperan {numero_es(p.casos_esperados)} casos; "
                       "ninguna señal está por encima de su valor típico.")
        return ExplicacionPrediccion(
            municipio_id=muni.id, municipio=muni.nombre, enfermedad_id=enf.id, enfermedad=enf.nombre,
            etiqueta=etiqueta(p.anio, p.semana_epi), horizonte=p.horizonte, nivel=p.nivel_riesgo,
            casos_esperados=p.casos_esperados, metodo=exp.get("metodo", ""), resumen=resumen, factores=factores,
            importancia_global=m.importancias if m else None)

    def historial(self, enfermedad_id: int | None = None, limite: int = 50) -> list[ModeloOut]:
        codigos = {e.id: e.codigo for e in self.db.scalars(select(Enfermedad))}
        stmt = select(ModeloEntrenado).order_by(ModeloEntrenado.fecha_entrenamiento.desc(), ModeloEntrenado.id.desc())
        if enfermedad_id is not None:
            stmt = stmt.where(ModeloEntrenado.enfermedad_id == enfermedad_id)
        return [modelo_out(m, codigos.get(m.enfermedad_id, "?")) for m in self.db.scalars(stmt.limit(limite))]
