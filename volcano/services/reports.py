"""Downloadable reports: CSV (raw data) and PDF (municipality summary).

- CSV with a UTF-8 BOM so Excel shows accents correctly. Column names are English (they are a
  data contract, like the CSV upload templates).
- PDF with ReportLab (pure Python, no browser), written in Spanish for its readers: current and
  predicted traffic light, the last 26 weeks with the 4-week prediction, active alerts, volcano
  status and model metrics.
"""
import csv
import io
from datetime import UTC, datetime

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, Line, String
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select

from volcano.models import Alert, Disease, Municipality, OfficialCase
from volcano.models.enums import AlertOrigin, RiskLevel
from volcano.repositories.domain import DiseaseRepository
from volcano.services.alerts import AlertService
from volcano.services.dashboard import DashboardService
from volcano.services.predictions import PredictionQueryService
from volcano.shared.epi import label, week_start
from volcano.shared.errors import NotFoundError
from volcano.shared.text import format_number_es

# Ink readable on white for each level (the fill colours are not contrasted enough as text)
LEVEL_INK = {"GREEN": "#0a6b0a", "YELLOW": "#8a5a00", "ORANGE": "#9e3f17", "RED": "#a52222"}
ORIGIN_ES = {AlertOrigin.OBSERVED: "Observado", AlertOrigin.PREDICTED: "Predicho"}
VOLCANO_LEVEL_ES = {"GREEN": "Verde", "YELLOW": "Amarillo", "ORANGE": "Naranja", "RED": "Rojo", "NO_DATA": "Sin dato"}
INK = colors.HexColor("#171614")
GREY = colors.HexColor("#7d7b75")
RULE = colors.HexColor("#e3e1da")


def _csv(headers: list[str], rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    w.writerows(rows)
    return ("﻿" + buf.getvalue()).encode("utf-8")


def _num(v: float | None, decimals: int = 1) -> str:
    return format_number_es(v, decimals, thousands=True)


def _yes_no(v: bool) -> str:
    return "yes" if v else "no"


class _Styles:
    """PDF paragraph styles (built once per report)."""

    def __init__(self) -> None:
        base = getSampleStyleSheet()
        self.h1 = ParagraphStyle("h1", parent=base["Title"], fontSize=18, leading=22, alignment=0, textColor=INK,
                                 spaceAfter=2)
        self.h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=12.5, textColor=INK, spaceBefore=12,
                                 spaceAfter=6)
        self.normal = ParagraphStyle("n", parent=base["BodyText"], fontSize=9, leading=12, textColor=INK)
        self.small = ParagraphStyle("s", parent=self.normal, fontSize=7.5, leading=10, textColor=GREY)


class ReportService:
    def __init__(self, db):
        self.db = db

    # ── CSV ──────────────────────────────────────────────────────────────────
    def cases_csv(self, municipality_id: int | None = None, disease_id: int | None = None,
                  since_year: int | None = None) -> bytes:
        stmt = (select(Municipality.divipola_code, Municipality.name, Disease.code, OfficialCase.year,
                       OfficialCase.epi_week, OfficialCase.cases, OfficialCase.source, OfficialCase.is_simulated)
                .join(Municipality, Municipality.id == OfficialCase.municipality_id)
                .join(Disease, Disease.id == OfficialCase.disease_id)
                .order_by(Municipality.name, Disease.code, OfficialCase.year, OfficialCase.epi_week))
        if municipality_id:
            stmt = stmt.where(OfficialCase.municipality_id == municipality_id)
        if disease_id:
            stmt = stmt.where(OfficialCase.disease_id == disease_id)
        if since_year:
            stmt = stmt.where(OfficialCase.year >= since_year)
        rows = ((d, n, code, y, w, week_start(y, w).isoformat(), c, s, _yes_no(sim))
                for d, n, code, y, w, c, s, sim in self.db.execute(stmt))
        return _csv(["divipola_code", "municipality", "disease", "year", "epi_week", "week_start", "cases",
                     "source", "is_simulated"], rows)

    def predictions_csv(self, municipality_id: int | None = None) -> bytes:
        predictions = PredictionQueryService(self.db)
        municipalities = list(self.db.scalars(
            select(Municipality).where(Municipality.active.is_(True)).order_by(Municipality.name)))
        if municipality_id:
            municipalities = [m for m in municipalities if m.id == municipality_id]
        rows = []
        for disease in DiseaseRepository(self.db).active():
            model = predictions.active_model(disease.id)
            if model is None:
                continue
            rows.extend((m.divipola_code, m.name, disease.code, p.year, p.epi_week,
                         week_start(p.year, p.epi_week).isoformat(), p.horizon, p.expected_cases,
                         p.lower_bound, p.upper_bound, p.risk_level, model.algorithm,
                         model.trained_at.date().isoformat())
                        for m in municipalities for p in predictions.latest_predictions(model.id, m.id))
        return _csv(["divipola_code", "municipality", "disease", "year", "epi_week", "week_start", "horizon_weeks",
                     "expected_cases", "lower_bound_80", "upper_bound_80", "risk_level", "model", "trained_at"], rows)

    def alerts_csv(self, active_only: bool = False) -> bytes:
        stmt = select(Alert).order_by(Alert.created_at.desc())
        if active_only:
            stmt = stmt.where(Alert.active.is_(True))
        rows = ((a.id, a.municipality.name, a.disease.code, a.year, a.epi_week, a.risk_level, a.origin,
                 _yes_no(a.active), a.created_at.date().isoformat(),
                 a.closed_at.date().isoformat() if a.closed_at else "", a.message)
                for a in self.db.scalars(stmt))
        return _csv(["id", "municipality", "disease", "year", "epi_week", "risk_level", "origin", "active",
                     "created_at", "closed_at", "message"], rows)

    # ── PDF ──────────────────────────────────────────────────────────────────
    def summary_pdf(self, municipality_id: int) -> bytes:
        m = self.db.get(Municipality, municipality_id)
        if m is None:
            raise NotFoundError(f"Municipio {municipality_id} no existe")
        predictions = PredictionQueryService(self.db)
        dashboard = DashboardService(self.db, predictions=predictions)
        summary = dashboard.summary(m.id)
        alerts = [a for a in AlertService(self.db).active() if a.municipality_id == m.id]
        s = _Styles()
        # Builder pattern: every section is built by its own method; here they are only ordered
        story = [
            *self._header_section(m, summary, s),
            *self._traffic_light_section(summary, s),
            *self._charts_section(dashboard, predictions, m, summary, s),
            KeepTogether(self._alerts_section(alerts, s)),
            *self._volcano_section(summary.volcano, s),
            KeepTogether(self._models_section(predictions, summary, s)),
            Spacer(1, 10),
            Paragraph("Proyecto académico · Programación Orientada a la Web. Las predicciones son orientativas y no "
                      "reemplazan la vigilancia oficial del INS ni de la Secretaría de Salud.", s.small),
        ]
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm,
                                bottomMargin=1.6 * cm, title=f"Reporte de riesgo · {m.name}",
                                author="Predictor de Brotes Nariño")
        doc.build(story, onFirstPage=self._footer, onLaterPages=self._footer)
        return buf.getvalue()

    @staticmethod
    def _header_section(m: Municipality, summary, s: _Styles) -> list:
        now = datetime.now(UTC).astimezone()
        parts = [
            Paragraph(f"Reporte de riesgo de brotes · {m.name}", s.h1),
            Paragraph(f"Semana epidemiológica {summary.reference_week.replace('-S', ' · S')} · "
                      f"{format_number_es(m.population, 0, thousands=True)} habitantes · "
                      f"generado el {now:%d/%m/%Y %H:%M}", s.small),
        ]
        if summary.has_simulated_data:
            parts.append(Paragraph("Incluye datos simulados para demostración (marcados en la base de datos).",
                                   s.small))
        return parts

    def _traffic_light_section(self, summary, s: _Styles) -> list:
        rows = [["Enfermedad", "Casos", "Nivel actual", "Próx. semana (int. 80 %)", "Máx. 4 semanas"]]
        inks = []
        for i, r in enumerate(summary.risks, start=1):
            p = r.prediction
            next_week = (f"{_num(p.expected_cases_h1)} "
                         f"({_num(p.lower_bound_h1, 0)}–{_num(p.upper_bound_h1, 0)})") if p else "Sin modelo"
            rows.append([Paragraph(r.name, s.normal), str(r.cases), RiskLevel(r.level).label_es, next_week,
                         RiskLevel(p.max_level).label_es if p else "—"])
            inks.append(("TEXTCOLOR", (2, i), (2, i), colors.HexColor(LEVEL_INK[r.level])))
            if p:
                inks.append(("TEXTCOLOR", (4, i), (4, i), colors.HexColor(LEVEL_INK[p.max_level])))
        return [
            Paragraph("Semáforo de riesgo", s.h2),
            self._table(rows, [5.6 * cm, 1.5 * cm, 2.4 * cm, 4.4 * cm, 3.0 * cm], inks),
            Spacer(1, 4),
            Paragraph("Niveles por canal endémico: Bajo ≤ P50 · Moderado ≤ P75 · Alto ≤ P90 · Muy alto > P90 "
                      "de las mismas semanas de los 5 años anteriores.", s.small),
        ]

    def _charts_section(self, dashboard: DashboardService, predictions: PredictionQueryService, m: Municipality,
                        summary, s: _Styles) -> list:
        charts = [self._chart(dashboard, predictions, m, r.disease_id, r.name, r.color) for r in summary.risks]
        pairs = [charts[i:i + 2] + [""] * (2 - len(charts[i:i + 2])) for i in range(0, len(charts), 2)]
        t = Table(pairs, colWidths=[8.7 * cm, 8.7 * cm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        return [
            Paragraph("Últimas 26 semanas y predicción", s.h2),
            t,
            Paragraph("Línea continua: casos observados · puntos: casos esperados · franja: intervalo del 80 %.",
                      s.small),
        ]

    def _alerts_section(self, alerts, s: _Styles) -> list:
        if not alerts:
            return [Paragraph("Alertas activas", s.h2),
                    Paragraph("No hay alertas activas para este municipio.", s.normal)]
        rows = [["Nivel", "Origen", "Detalle"]] + [
            [RiskLevel(a.risk_level).label_es, ORIGIN_ES.get(AlertOrigin(a.origin), a.origin),
             Paragraph(a.message, s.normal)]
            for a in alerts]
        return [Paragraph("Alertas activas", s.h2), self._table(rows, [2.2 * cm, 2.4 * cm, 12.3 * cm])]

    @staticmethod
    def _volcano_section(v, s: _Styles) -> list:
        text = f"<b>Nivel de actividad:</b> {VOLCANO_LEVEL_ES.get(v.activity_level, v.activity_level)}"
        if v.date:
            text += f" (boletín SGC del {v.date:%d/%m/%Y})"
        if v.so2_tons_per_day:
            text += f" · SO₂ {_num(v.so2_tons_per_day, 0)} t/día"
        parts = [Paragraph("Volcán Galeras", s.h2), Paragraph(text, s.normal)]
        if v.recent_ash_falls:
            ash = "; ".join(f"{c.municipality} ({c.date:%d/%m/%Y})" for c in v.recent_ash_falls)
            parts.append(Paragraph(f"<b>Caída de ceniza en los últimos 12 meses:</b> {ash}", s.normal))
        return parts

    def _models_section(self, predictions: PredictionQueryService, summary, s: _Styles) -> list:
        rows = [["Enfermedad", "Algoritmo", "MAE base", "MAE modelo", "RMSE base", "RMSE modelo", "Entrenado"]]
        for r in summary.risks:
            model = predictions.active_model(r.disease_id)
            if model:
                rows.append([r.code, model.algorithm, _num(model.baseline_mae, 2), _num(model.model_mae, 2),
                             _num(model.baseline_rmse, 2), _num(model.model_rmse, 2), f"{model.trained_at:%d/%m/%Y}"])
        return [
            Paragraph("Modelos predictivos", s.h2),
            self._table(rows, [2.6 * cm, 3.2 * cm, 2.0 * cm, 2.2 * cm, 2.1 * cm, 2.4 * cm, 2.4 * cm]),
            Paragraph("Base = promedio móvil de 4 semanas. MAE/RMSE en casos por semana y municipio, "
                      "validación con las últimas 52 semanas.", s.small),
        ]

    @staticmethod
    def _table(rows, widths, extra=None) -> Table:
        t = Table(rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
            ("TEXTCOLOR", (0, 0), (-1, 0), GREY),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, RULE),
            ("LINEBELOW", (0, 1), (-1, -1), 0.3, RULE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            *(extra or []),
        ]))
        return t

    @staticmethod
    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GREY)
        canvas.drawString(1.8 * cm, 1 * cm, "Predictor de Brotes · Pasto y zona del Volcán Galeras")
        canvas.drawRightString(A4[0] - 1.8 * cm, 1 * cm, f"Página {doc.page}")
        canvas.restoreState()

    @staticmethod
    def _chart(dashboard: DashboardService, predictions: PredictionQueryService, m: Municipality, disease_id: int,
               name: str, color: str) -> Drawing:
        series = dashboard.series(m.id, disease_id, weeks=26).points
        future = predictions.prediction(m.id, disease_id).points
        observed = [(i, p.cases or 0) for i, p in enumerate(series)]
        expected = []
        if future and observed:
            expected = [(len(series) - 1, observed[-1][1]),
                        *((len(series) + i, f.expected_cases) for i, f in enumerate(future))]
        upper = [(len(series) + i, f.upper_bound) for i, f in enumerate(future)]
        lower = [(len(series) + i, f.lower_bound) for i, f in enumerate(future)]
        top = max([1.0] + [y for _, y in observed] + [y for _, y in upper]) * 1.1

        d = Drawing(8.5 * cm, 4.6 * cm)
        d.add(String(0, 4.6 * cm - 9, name, fontName="Helvetica-Bold", fontSize=8, fillColor=INK))
        lp = LinePlot()
        lp.x, lp.y, lp.width, lp.height = 26, 14, 8.5 * cm - 34, 4.6 * cm - 34
        data = [observed]
        if expected:
            data += [expected, upper, lower]
        lp.data = data
        c = colors.HexColor(color)
        lp.lines[0].strokeColor, lp.lines[0].strokeWidth = c, 1.4
        if expected:
            lp.lines[1].strokeColor, lp.lines[1].strokeWidth, lp.lines[1].strokeDashArray = c, 1.2, [3, 2]
            lp.lines[1].symbol = makeMarker("FilledCircle", size=2.5, fillColor=c, strokeColor=c)
            for k in (2, 3):
                lp.lines[k].strokeColor, lp.lines[k].strokeWidth = colors.Color(c.red, c.green, c.blue, alpha=0.45), 0.6
        lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = 0, len(series) + max(len(future), 1) - 1
        lp.xValueAxis.visibleLabels = False
        lp.xValueAxis.strokeColor = RULE
        lp.yValueAxis.valueMin, lp.yValueAxis.valueMax = 0, top
        lp.yValueAxis.labels.fontSize, lp.yValueAxis.labels.fillColor = 6.5, GREY
        lp.yValueAxis.strokeColor = RULE
        lp.yValueAxis.labelTextFormat = (lambda v: f"{v:.0f}") if top >= 6 else (lambda v: format_number_es(v, 1))
        lp.yValueAxis.labels.fontName = "Helvetica"
        d.add(lp)
        if future:
            x = lp.x + lp.width * (len(series) - 1) / max(lp.xValueAxis.valueMax, 1)
            d.add(Line(x, lp.y, x, lp.y + lp.height, strokeColor=GREY, strokeWidth=0.4, strokeDashArray=[1, 2]))
        first = series[0].label.replace("-S", " S") if series else ""
        last = label(future[-1].year, future[-1].epi_week).replace("-S", " S") if future else \
            (series[-1].label.replace("-S", " S") if series else "")
        d.add(String(lp.x, 2, first, fontName="Helvetica", fontSize=6.5, fillColor=GREY))
        d.add(String(lp.x + lp.width, 2, last, fontName="Helvetica", fontSize=6.5, fillColor=GREY, textAnchor="end"))
        return d

