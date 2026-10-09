"""Reportes descargables: CSV (datos crudos) y PDF (resumen del municipio).

- CSV con BOM UTF-8 para que Excel muestre bien las tildes.
- PDF con ReportLab (puro Python, sin navegador): semáforo actual y predicho, gráfica de
  las últimas 26 semanas con la predicción de 4, alertas activas, estado del volcán y
  métricas del modelo.
"""
import csv
import io
from datetime import date, datetime, timezone

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, Line, String
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select

from app.core.epi import etiqueta, inicio_semana
from app.core.errors import NoEncontradoError
from app.models import Alerta, CasoOficial, Enfermedad, Municipio
from app.repositories.repos import EnfermedadRepository
from app.services.alerta_service import AlertaService
from app.services.dashboard_service import DashboardService
from app.services.prediccion_service import PrediccionService

TEXTO_NIVEL = {"VERDE": "Bajo", "AMARILLO": "Moderado", "NARANJA": "Alto", "ROJO": "Muy alto"}
# Tinta legible sobre blanco para cada nivel (los colores de relleno no tienen contraste suficiente como texto)
COLOR_NIVEL = {"VERDE": "#0a6b0a", "AMARILLO": "#8a5a00", "NARANJA": "#9e3f17", "ROJO": "#a52222"}
TINTA = colors.HexColor("#171614")
GRIS = colors.HexColor("#7d7b75")
LINEA = colors.HexColor("#e3e1da")


def _csv(encabezados: list[str], filas) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(encabezados)
    w.writerows(filas)
    return ("﻿" + buf.getvalue()).encode("utf-8")


def _num(v: float | None, dec: int = 1) -> str:
    if v is None:
        return "—"
    texto = f"{v:,.{dec}f}"  # 1,234.5 → 1.234,5
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


class ReporteService:
    def __init__(self, db):
        self.db = db

    # ── CSV ──────────────────────────────────────────────────────────────────
    def casos_csv(self, municipio_id: int | None = None, enfermedad_id: int | None = None,
                  desde_anio: int | None = None) -> bytes:
        stmt = (select(Municipio.codigo_divipola, Municipio.nombre, Enfermedad.codigo, CasoOficial.anio,
                       CasoOficial.semana_epi, CasoOficial.casos, CasoOficial.fuente, CasoOficial.es_simulado)
                .join(Municipio, Municipio.id == CasoOficial.municipio_id)
                .join(Enfermedad, Enfermedad.id == CasoOficial.enfermedad_id)
                .order_by(Municipio.nombre, Enfermedad.codigo, CasoOficial.anio, CasoOficial.semana_epi))
        if municipio_id:
            stmt = stmt.where(CasoOficial.municipio_id == municipio_id)
        if enfermedad_id:
            stmt = stmt.where(CasoOficial.enfermedad_id == enfermedad_id)
        if desde_anio:
            stmt = stmt.where(CasoOficial.anio >= desde_anio)
        filas = ((d, n, e, a, s, inicio_semana(a, s).isoformat(), c, f, "si" if sim else "no")
                 for d, n, e, a, s, c, f, sim in self.db.execute(stmt))
        return _csv(["cod_divipola", "municipio", "enfermedad", "anio", "semana_epi", "fecha_inicio_semana", "casos",
                     "fuente", "simulado"], filas)

    def predicciones_csv(self, municipio_id: int | None = None) -> bytes:
        pred = PrediccionService(self.db)
        municipios = list(self.db.scalars(select(Municipio).where(Municipio.activo.is_(True)).order_by(Municipio.nombre)))
        if municipio_id:
            municipios = [m for m in municipios if m.id == municipio_id]
        filas = []
        for enf in EnfermedadRepository(self.db).activas():
            modelo = pred.modelo_activo(enf.id)
            if modelo is None:
                continue
            for m in municipios:
                for p in pred._ultimas(modelo.id, m.id):
                    filas.append((m.codigo_divipola, m.nombre, enf.codigo, p.anio, p.semana_epi,
                                  inicio_semana(p.anio, p.semana_epi).isoformat(), p.horizonte, p.casos_esperados,
                                  p.limite_inferior, p.limite_superior, p.nivel_riesgo, modelo.algoritmo,
                                  modelo.fecha_entrenamiento.date().isoformat()))
        return _csv(["cod_divipola", "municipio", "enfermedad", "anio", "semana_epi", "fecha_inicio_semana",
                     "horizonte_semanas", "casos_esperados", "limite_inferior_80", "limite_superior_80", "nivel_riesgo",
                     "modelo", "fecha_entrenamiento"], filas)

    def alertas_csv(self, solo_activas: bool = False) -> bytes:
        stmt = select(Alerta).order_by(Alerta.creado_en.desc())
        if solo_activas:
            stmt = stmt.where(Alerta.activa.is_(True))
        filas = ((a.id, a.municipio.nombre, a.enfermedad.codigo, a.anio, a.semana_epi, a.nivel_riesgo, a.origen,
                  "si" if a.activa else "no", a.creado_en.date().isoformat(),
                  a.cerrada_en.date().isoformat() if a.cerrada_en else "", a.mensaje)
                 for a in self.db.scalars(stmt))
        return _csv(["id", "municipio", "enfermedad", "anio", "semana_epi", "nivel", "origen", "activa", "creada",
                     "cerrada", "mensaje"], filas)

    # ── PDF ──────────────────────────────────────────────────────────────────
    def resumen_pdf(self, municipio_id: int) -> bytes:
        m = self.db.get(Municipio, municipio_id)
        if m is None:
            raise NoEncontradoError(f"Municipio {municipio_id} no existe")
        dash = DashboardService(self.db)
        pred = PrediccionService(self.db)
        resumen = dash.resumen(m.id)

        estilos = getSampleStyleSheet()
        h1 = ParagraphStyle("h1", parent=estilos["Title"], fontSize=18, leading=22, alignment=0, textColor=TINTA,
                            spaceAfter=2)
        h2 = ParagraphStyle("h2", parent=estilos["Heading2"], fontSize=12.5, textColor=TINTA, spaceBefore=12,
                            spaceAfter=6)
        normal = ParagraphStyle("n", parent=estilos["BodyText"], fontSize=9, leading=12, textColor=TINTA)
        pequeno = ParagraphStyle("p", parent=normal, fontSize=7.5, leading=10, textColor=GRIS)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm,
                                bottomMargin=1.6 * cm, title=f"Reporte de riesgo · {m.nombre}",
                                author="Predictor de Brotes Nariño")
        ahora = datetime.now(timezone.utc).astimezone()
        historia = [
            Paragraph(f"Reporte de riesgo de brotes · {m.nombre}", h1),
            Paragraph(f"Semana epidemiológica {resumen.semana_referencia.replace('-S', ' · S')} · "
                      f"{m.poblacion:,} habitantes · generado el {ahora:%d/%m/%Y %H:%M}".replace(",", "."), pequeno),
        ]
        if resumen.hay_datos_simulados:
            historia.append(Paragraph("Incluye datos simulados para demostración (marcados en la base de datos).", pequeno))

        # 1. Semáforo actual y predicho
        historia.append(Paragraph("Semáforo de riesgo", h2))
        filas = [["Enfermedad", "Casos", "Nivel actual", "Próx. semana (int. 80 %)", "Máx. 4 semanas"]]
        estilos_tabla = []
        for i, r in enumerate(resumen.riesgos, start=1):
            p = r.prediccion
            filas.append([Paragraph(r.nombre, normal), str(r.casos), TEXTO_NIVEL[r.nivel],
                          f"{_num(p.casos_esperados_h1)} ({_num(p.limite_inferior_h1, 0)}–{_num(p.limite_superior_h1, 0)})"
                          if p else "Sin modelo",
                          TEXTO_NIVEL.get(p.nivel_max, "—") if p else "—"])
            estilos_tabla.append(("TEXTCOLOR", (2, i), (2, i), colors.HexColor(COLOR_NIVEL[r.nivel])))
            if p:
                estilos_tabla.append(("TEXTCOLOR", (4, i), (4, i), colors.HexColor(COLOR_NIVEL[p.nivel_max])))
        historia.append(self._tabla(filas, [5.6 * cm, 1.5 * cm, 2.4 * cm, 4.4 * cm, 3.0 * cm], estilos_tabla))
        historia.append(Spacer(1, 4))
        historia.append(Paragraph("Niveles por canal endémico: Bajo ≤ P50 · Moderado ≤ P75 · Alto ≤ P90 · Muy alto > P90 "
                                  "de las mismas semanas de los 5 años anteriores.", pequeno))

        # 2. Gráficas por enfermedad
        historia.append(Paragraph("Últimas 26 semanas y predicción", h2))
        graficas = [self._grafica(dash, pred, m, r.enfermedad_id, r.nombre, r.color) for r in resumen.riesgos]
        pares = [graficas[i:i + 2] + [""] * (2 - len(graficas[i:i + 2])) for i in range(0, len(graficas), 2)]
        t = Table(pares, colWidths=[8.7 * cm, 8.7 * cm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        historia.append(t)
        historia.append(Paragraph("Línea continua: casos observados · puntos: casos esperados · franja: intervalo del 80 %.",
                                  pequeno))

        # 3. Alertas
        alertas = [a for a in AlertaService(self.db).activas() if a.municipio_id == m.id]
        bloque = [Paragraph("Alertas activas", h2)]
        if alertas:
            bloque.append(self._tabla([["Nivel", "Origen", "Detalle"]] + [
                [TEXTO_NIVEL[a.nivel_riesgo], a.origen.capitalize(), Paragraph(a.mensaje, normal)] for a in alertas],
                [2.2 * cm, 2.4 * cm, 12.3 * cm]))
        else:
            bloque.append(Paragraph("No hay alertas activas para este municipio.", normal))
        historia.append(KeepTogether(bloque))

        # 4. Volcán
        v = resumen.volcan
        historia.append(Paragraph("Volcán Galeras", h2))
        texto = f"<b>Nivel de actividad:</b> {v.nivel_actividad.capitalize()}"
        if v.fecha:
            texto += f" (boletín SGC del {v.fecha:%d/%m/%Y})"
        if v.so2_ton_dia:
            texto += f" · SO₂ {_num(v.so2_ton_dia, 0)} t/día"
        historia.append(Paragraph(texto, normal))
        if v.ceniza_reciente:
            cenizas = "; ".join(f"{c.municipio} ({c.fecha:%d/%m/%Y})" for c in v.ceniza_reciente)
            historia.append(Paragraph(f"<b>Caída de ceniza en los últimos 12 meses:</b> {cenizas}", normal))

        # 5. Modelos
        filas = [["Enfermedad", "Algoritmo", "MAE base", "MAE modelo", "RMSE base", "RMSE modelo", "Entrenado"]]
        for r in resumen.riesgos:
            mod = pred.modelo_activo(r.enfermedad_id)
            if mod:
                filas.append([r.codigo, mod.algoritmo, _num(mod.mae_base, 2), _num(mod.mae_modelo, 2),
                              _num(mod.rmse_base, 2), _num(mod.rmse_modelo, 2), f"{mod.fecha_entrenamiento:%d/%m/%Y}"])
        historia.append(KeepTogether([
            Paragraph("Modelos predictivos", h2),
            self._tabla(filas, [2.6 * cm, 3.2 * cm, 2.0 * cm, 2.2 * cm, 2.1 * cm, 2.4 * cm, 2.4 * cm]),
            Paragraph("Base = promedio móvil de 4 semanas. MAE/RMSE en casos por semana y municipio, "
                      "validación con las últimas 52 semanas.", pequeno),
        ]))
        historia.append(Spacer(1, 10))
        historia.append(Paragraph("Proyecto académico · Programación Orientada a la Web. Las predicciones son orientativas "
                                  "y no reemplazan la vigilancia oficial del INS ni de la Secretaría de Salud.", pequeno))

        doc.build(historia, onFirstPage=self._pie, onLaterPages=self._pie)
        return buf.getvalue()

    @staticmethod
    def _tabla(filas, anchos, extra=None) -> Table:
        t = Table(filas, colWidths=anchos, repeatRows=1)
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
            ("TEXTCOLOR", (0, 0), (-1, 0), GRIS),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINEA),
            ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINEA),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            *(extra or []),
        ]))
        return t

    @staticmethod
    def _pie(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GRIS)
        canvas.drawString(1.8 * cm, 1 * cm, "Predictor de Brotes · Pasto y zona del Volcán Galeras")
        canvas.drawRightString(A4[0] - 1.8 * cm, 1 * cm, f"Página {doc.page}")
        canvas.restoreState()

    @staticmethod
    def _grafica(dash: DashboardService, pred: PrediccionService, m: Municipio, enfermedad_id: int, nombre: str,
                 color: str) -> Drawing:
        serie = dash.serie(m.id, enfermedad_id, semanas=26).puntos
        futuro = pred.prediccion(m.id, enfermedad_id).puntos
        obs = [(i, p.casos or 0) for i, p in enumerate(serie)]
        esp = [(len(serie) - 1, obs[-1][1])] + [(len(serie) + i, f.casos_esperados) for i, f in enumerate(futuro)] \
            if futuro and obs else []
        sup = [(len(serie) + i, f.limite_superior) for i, f in enumerate(futuro)]
        inf = [(len(serie) + i, f.limite_inferior) for i, f in enumerate(futuro)]
        tope = max([1.0] + [y for _, y in obs] + [y for _, y in sup]) * 1.1

        d = Drawing(8.5 * cm, 4.6 * cm)
        d.add(String(0, 4.6 * cm - 9, nombre, fontName="Helvetica-Bold", fontSize=8, fillColor=TINTA))
        lp = LinePlot()
        lp.x, lp.y, lp.width, lp.height = 26, 14, 8.5 * cm - 34, 4.6 * cm - 34
        datos = [obs]
        if esp:
            datos += [esp, sup, inf]
        lp.data = datos
        c = colors.HexColor(color)
        lp.lines[0].strokeColor, lp.lines[0].strokeWidth = c, 1.4
        if esp:
            lp.lines[1].strokeColor, lp.lines[1].strokeWidth, lp.lines[1].strokeDashArray = c, 1.2, [3, 2]
            lp.lines[1].symbol = makeMarker("FilledCircle", size=2.5, fillColor=c, strokeColor=c)
            for k in (2, 3):
                lp.lines[k].strokeColor, lp.lines[k].strokeWidth = colors.Color(c.red, c.green, c.blue, alpha=0.45), 0.6
        lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = 0, len(serie) + max(len(futuro), 1) - 1
        lp.xValueAxis.visibleLabels = False
        lp.xValueAxis.strokeColor = LINEA
        lp.yValueAxis.valueMin, lp.yValueAxis.valueMax = 0, tope
        lp.yValueAxis.labels.fontSize, lp.yValueAxis.labels.fillColor = 6.5, GRIS
        lp.yValueAxis.strokeColor = LINEA
        lp.yValueAxis.labelTextFormat = (lambda v: f"{v:.0f}") if tope >= 6 else (lambda v: f"{v:.1f}".replace(".", ","))
        lp.yValueAxis.labels.fontName = "Helvetica"
        d.add(lp)
        if futuro:
            x = lp.x + lp.width * (len(serie) - 1) / max(lp.xValueAxis.valueMax, 1)
            d.add(Line(x, lp.y, x, lp.y + lp.height, strokeColor=GRIS, strokeWidth=0.4, strokeDashArray=[1, 2]))
        primera = serie[0].etiqueta.replace("-S", " S") if serie else ""
        ultima = etiqueta(futuro[-1].anio, futuro[-1].semana_epi).replace("-S", " S") if futuro else \
            (serie[-1].etiqueta.replace("-S", " S") if serie else "")
        d.add(String(lp.x, 2, primera, fontName="Helvetica", fontSize=6.5, fillColor=GRIS))
        d.add(String(lp.x + lp.width, 2, ultima, fontName="Helvetica", fontSize=6.5, fillColor=GRIS, textAnchor="end"))
        return d


def nombre_archivo(base: str, ext: str, sufijo: str | None = None) -> str:
    limpio = "".join(ch if ch.isalnum() else "-" for ch in (sufijo or "").lower()).strip("-")
    return f"{base}{'-' + limpio if limpio else ''}-{date.today():%Y%m%d}.{ext}"
