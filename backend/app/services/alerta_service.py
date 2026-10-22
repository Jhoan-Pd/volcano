"""Alertas tempranas.

Regla: se registra una alerta cuando el riesgo de una enfermedad en un municipio llega a
NARANJA o ROJO, ya sea:
    - OBSERVADO: los casos de la última semana con datos superan el percentil 75/90, o
    - PREDICHO:  el modelo espera ese nivel en alguna de las próximas 4 semanas.

Cada evaluación es idempotente: hay como máximo una alerta activa por municipio,
enfermedad, semana y origen (si el nivel sube, se actualiza). Las alertas cuyo motivo ya
no se cumple se cierran solas. Las alertas nuevas se envían por correo (Resend) una sola vez: a
ALERTAS_EMAIL_DESTINO y a los ciudadanos registrados en el municipio afectado.
"""
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.core.config import settings
from app.core.epi import etiqueta
from app.core.errors import NoEncontradoError
from app.models import Alerta, Rol, Usuario
from app.models.enums import NivelRiesgo, OrigenAlerta, RolNombre
from app.notificaciones.correo import NotificadorCorreo, html_alertas, notificador_por_defecto
from app.repositories.repos import EnfermedadRepository, MunicipioRepository
from app.schemas.alerta import AlertaOut, ResultadoEvaluacion
from app.schemas.comun import Pagina
from app.services.dashboard_service import DashboardService
from app.services.prediccion_service import PrediccionService

logger = logging.getLogger("predictor.alertas")

def _percentil_superado(enf, nivel: str) -> int:
    return enf.umbral_rojo_pct if nivel == NivelRiesgo.ROJO else enf.umbral_naranja_pct


def texto_nivel(nivel: str) -> str:
    """«Riesgo alto», «Riesgo muy alto»…"""
    return f"Riesgo {NivelRiesgo(nivel).etiqueta.lower()}"


@dataclass
class _Candidata:
    municipio_id: int
    enfermedad_id: int
    anio: int
    semana_epi: int
    nivel: str
    origen: str
    mensaje: str
    prediccion_id: int | None = None
    extra: dict = field(default_factory=dict)


def alerta_out(a: Alerta) -> AlertaOut:
    return AlertaOut(
        id=a.id, municipio_id=a.municipio_id, municipio=a.municipio.nombre, enfermedad_id=a.enfermedad_id,
        enfermedad=a.enfermedad.nombre, codigo_enfermedad=a.enfermedad.codigo, anio=a.anio, semana_epi=a.semana_epi,
        etiqueta=etiqueta(a.anio, a.semana_epi), nivel_riesgo=a.nivel_riesgo, origen=a.origen, mensaje=a.mensaje,
        activa=a.activa, notificada_email=a.notificada_email, creado_en=a.creado_en, cerrada_en=a.cerrada_en,
    )


class AlertaService:
    def __init__(self, db, notificador: NotificadorCorreo | None = None):
        self.db = db
        self.notificador = notificador or notificador_por_defecto()

    # ── evaluación ───────────────────────────────────────────────────────────
    def _candidatas(self) -> list[_Candidata]:
        pred = PrediccionService(self.db)
        dash = DashboardService(self.db, predicciones=pred)  # comparten la caché de modelos y predicciones
        try:
            anio, semana = dash.semana_referencia()
        except NoEncontradoError:
            return []
        salida = []
        municipios = MunicipioRepository(self.db).activos()
        for enf in EnfermedadRepository(self.db).activas():
            modelo = pred.modelo_activo(enf.id)
            for m in municipios:
                r = dash.riesgo_enfermedad(m, enf, anio, semana)
                if NivelRiesgo(r.nivel).es_alerta:
                    salida.append(_Candidata(
                        m.id, enf.id, anio, semana, r.nivel, OrigenAlerta.OBSERVADO,
                        f"{enf.nombre} en {m.nombre}: {r.casos} casos en la semana {etiqueta(anio, semana)}, "
                        f"por encima del percentil {_percentil_superado(enf, r.nivel)} "
                        f"de los últimos 5 años ({texto_nivel(r.nivel).lower()})."))
                if modelo is None:
                    continue
                preds = [p for p in pred.ultimas_predicciones(modelo.id, m.id) if NivelRiesgo(p.nivel_riesgo).es_alerta]
                if preds:
                    p = max(preds, key=lambda x: (NivelRiesgo(x.nivel_riesgo).rango, x.casos_esperados))
                    salida.append(_Candidata(
                        m.id, enf.id, p.anio, p.semana_epi, p.nivel_riesgo, OrigenAlerta.PREDICHO,
                        f"{enf.nombre} en {m.nombre}: el modelo espera {p.casos_esperados:.0f} casos "
                        f"(entre {p.limite_inferior:.0f} y {p.limite_superior:.0f}) en la semana "
                        f"{etiqueta(p.anio, p.semana_epi)} ({texto_nivel(p.nivel_riesgo).lower()}).",
                        prediccion_id=p.id))
        return salida

    def evaluar(self, enviar_correo: bool = True) -> ResultadoEvaluacion:
        candidatas = self._candidatas()
        ahora = datetime.now(UTC)
        desde = min((c.anio for c in candidatas), default=ahora.year) - 1
        # Todas las alertas recientes (activas o cerradas) por clave; gana la más reciente
        existentes: dict[tuple, Alerta] = {}
        for a in self.db.scalars(select(Alerta).where((Alerta.activa.is_(True)) | (Alerta.anio >= desde))
                                 .order_by(Alerta.id)):
            existentes[(a.municipio_id, a.enfermedad_id, a.anio, a.semana_epi, a.origen)] = a
        activas = {k: a for k, a in existentes.items() if a.activa}
        nuevas: list[Alerta] = []
        actualizadas = 0
        vigentes = set()
        for c in candidatas:
            clave = (c.municipio_id, c.enfermedad_id, c.anio, c.semana_epi, c.origen)
            a = existentes.get(clave)
            sube = a is not None and NivelRiesgo(c.nivel).rango > NivelRiesgo(a.nivel_riesgo).rango
            if a is None:
                a = Alerta(municipio_id=c.municipio_id, enfermedad_id=c.enfermedad_id, prediccion_id=c.prediccion_id,
                           anio=c.anio, semana_epi=c.semana_epi, nivel_riesgo=c.nivel, origen=c.origen,
                           mensaje=c.mensaje, activa=True)
                self.db.add(a)
                nuevas.append(a)
            elif not a.activa:
                # Un administrador la cerró: solo se reabre si el riesgo empeoró
                if not sube:
                    continue
                a.activa, a.cerrada_en, a.notificada_email = True, None, False
                a.nivel_riesgo, a.mensaje, a.prediccion_id = c.nivel, c.mensaje, c.prediccion_id
                actualizadas += 1
            elif a.mensaje != c.mensaje or a.nivel_riesgo != c.nivel:
                a.nivel_riesgo, a.mensaje, a.prediccion_id = c.nivel, c.mensaje, c.prediccion_id
                if sube:
                    a.notificada_email = False  # se vuelve a avisar si empeora
                actualizadas += 1
            vigentes.add(clave)
        cerradas = 0
        for clave, a in activas.items():
            if clave not in vigentes:
                a.activa, a.cerrada_en = False, ahora
                cerradas += 1
        self.db.commit()

        enviadas = self.notificar() if enviar_correo else 0
        logger.info("Alertas: %d nuevas, %d actualizadas, %d cerradas, %d correos", len(nuevas), actualizadas,
                    cerradas, enviadas)
        return ResultadoEvaluacion(nuevas=len(nuevas), actualizadas=actualizadas, cerradas=cerradas,
                                   activas=len(vigentes), correos_enviados=enviadas)

    def _envios(self, pendientes: list[Alerta]) -> list[tuple[list[str], list[Alerta]]]:
        """(destinatarios, alertas) de cada correo. Cada ciudadano recibe un correo propio con las
        alertas de su municipio: así nadie ve las direcciones de los demás."""
        envios = []
        if settings.destinatarios_alertas:
            envios.append((settings.destinatarios_alertas, pendientes))
        if settings.ALERTAS_A_CIUDADANOS:
            por_municipio: dict[int, list[Alerta]] = {}
            for a in pendientes:
                por_municipio.setdefault(a.municipio_id, []).append(a)
            ciudadanos = self.db.scalars(select(Usuario).join(Rol).where(
                Rol.nombre == RolNombre.CIUDADANO.value, Usuario.activo.is_(True),
                Usuario.municipio_id.in_(list(por_municipio))))
            envios.extend(([u.email], por_municipio[u.municipio_id]) for u in ciudadanos)
        return envios

    def notificar(self) -> int:
        pendientes = list(self.db.scalars(select(Alerta).where(Alerta.activa.is_(True),
                                                               Alerta.notificada_email.is_(False))))
        if not pendientes:
            return 0
        notificadas: set[int] = set()
        for destinatarios, alertas in self._envios(pendientes):
            filas = [{"nivel": a.nivel_riesgo, "nivel_texto": texto_nivel(a.nivel_riesgo),
                      "mensaje": a.mensaje} for a in alertas]
            hay_rojo = any(a.nivel_riesgo == "ROJO" for a in alertas)
            asunto = f"{'🔴' if hay_rojo else '🟠'} {len(alertas)} alerta(s) temprana(s) de brotes en Nariño"
            if self.notificador.enviar(destinatarios, asunto, html_alertas(filas, settings.FRONTEND_URL)):
                notificadas.update(a.id for a in alertas)
        for a in pendientes:
            if a.id in notificadas:
                a.notificada_email = True
        self.db.commit()
        return len(notificadas)

    # ── consultas ────────────────────────────────────────────────────────────
    def activas(self) -> list[AlertaOut]:
        alertas = self.db.scalars(select(Alerta).where(Alerta.activa.is_(True)))
        # Primero las más graves; a igual nivel, lo ya observado antes que lo predicho
        def prioridad(a: Alerta) -> tuple[int, bool, int]:
            return (-NivelRiesgo(a.nivel_riesgo).rango, a.origen != OrigenAlerta.OBSERVADO, a.municipio_id)
        return [alerta_out(a) for a in sorted(alertas, key=prioridad)]

    def listar(self, activa: bool | None, offset: int, limit: int) -> Pagina[AlertaOut]:
        stmt = select(Alerta)
        total = select(func.count()).select_from(Alerta)
        if activa is not None:
            stmt, total = stmt.where(Alerta.activa.is_(activa)), total.where(Alerta.activa.is_(activa))
        filas = self.db.scalars(stmt.order_by(Alerta.creado_en.desc(), Alerta.id.desc()).offset(offset).limit(limit))
        return Pagina[AlertaOut](items=[alerta_out(a) for a in filas], total=self.db.scalar(total) or 0,
                                 offset=offset, limit=limit)

    def cerrar(self, alerta_id: int) -> AlertaOut:
        a = self.db.get(Alerta, alerta_id)
        if a is None:
            raise NoEncontradoError(f"Alerta {alerta_id} no existe")
        if a.activa:
            a.activa, a.cerrada_en = False, datetime.now(UTC)
            self.db.commit()
        return alerta_out(a)
