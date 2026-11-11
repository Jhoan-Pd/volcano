"""Early alerts.

Rule: an alert is recorded when the risk of a disease in a municipality reaches ORANGE or RED,
either because:
    - OBSERVED:  last week's cases are above percentile 75/90, or
    - PREDICTED: the model expects that level in one of the next 4 weeks.

Each evaluation is idempotent: there is at most one active alert per municipality, disease,
week and origin (when the level rises it is updated). Alerts whose reason no longer holds are
closed automatically. New alerts are e-mailed once (Resend): to ALERT_EMAIL_RECIPIENTS and to the
citizens registered in the affected municipality. Messages are Spanish because users read them.
"""
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, or_, select

from volcano.models import Alert, Disease, Municipality, Role, User
from volcano.models.enums import AlertOrigin, RiskLevel, RoleName
from volcano.notifications.email import EmailNotifier, alerts_html, default_notifier
from volcano.repositories.domain import DiseaseRepository, MunicipalityRepository
from volcano.schemas.alert import AlertFilters, AlertOut, EvaluationResult
from volcano.schemas.common import Page
from volcano.services.dashboard import DashboardService
from volcano.services.predictions import PredictionQueryService
from volcano.shared.config import settings
from volcano.shared.epi import label
from volcano.shared.errors import NotFoundError

logger = logging.getLogger("volcano.alerts")


def _exceeded_percentile(disease, level: str) -> int:
    return disease.red_threshold_pct if level == RiskLevel.RED else disease.orange_threshold_pct


def level_text_es(level: str) -> str:
    """«Riesgo alto», «Riesgo muy alto»…"""
    return f"Riesgo {RiskLevel(level).label_es.lower()}"


@dataclass
class _Candidate:
    municipality_id: int
    disease_id: int
    year: int
    epi_week: int
    level: str
    origin: str
    message: str
    prediction_id: int | None = None
    extra: dict = field(default_factory=dict)


def alert_out(a: Alert) -> AlertOut:
    return AlertOut(
        id=a.id, municipality_id=a.municipality_id, municipality=a.municipality.name, disease_id=a.disease_id,
        disease=a.disease.name, disease_code=a.disease.code, year=a.year, epi_week=a.epi_week,
        label=label(a.year, a.epi_week), risk_level=a.risk_level, origin=a.origin, message=a.message,
        active=a.active, email_notified=a.email_notified, created_at=a.created_at, closed_at=a.closed_at,
    )


class AlertService:
    def __init__(self, db, notifier: EmailNotifier | None = None):
        self.db = db
        self.notifier = notifier or default_notifier()

    # ── evaluation ───────────────────────────────────────────────────────────
    def _candidates(self) -> list[_Candidate]:
        predictions = PredictionQueryService(self.db)
        dashboard = DashboardService(self.db, predictions=predictions)  # they share the per-request cache
        try:
            year, week = dashboard.reference_week()
        except NotFoundError:
            return []
        out = []
        municipalities = MunicipalityRepository(self.db).active()
        for disease in DiseaseRepository(self.db).active():
            model = predictions.active_model(disease.id)
            for m in municipalities:
                r = dashboard.disease_risk(m, disease, year, week)
                if RiskLevel(r.level).is_alert:
                    out.append(_Candidate(
                        m.id, disease.id, year, week, r.level, AlertOrigin.OBSERVED,
                        f"{disease.name} en {m.name}: {r.cases} casos en la semana {label(year, week)}, "
                        f"por encima del percentil {_exceeded_percentile(disease, r.level)} "
                        f"de los últimos 5 años ({level_text_es(r.level).lower()})."))
                if model is None:
                    continue
                preds = [p for p in predictions.latest_predictions(model.id, m.id)
                         if RiskLevel(p.risk_level).is_alert]
                if preds:
                    p = max(preds, key=lambda x: (RiskLevel(x.risk_level).rank, x.expected_cases))
                    out.append(_Candidate(
                        m.id, disease.id, p.year, p.epi_week, p.risk_level, AlertOrigin.PREDICTED,
                        f"{disease.name} en {m.name}: el modelo espera {p.expected_cases:.0f} casos "
                        f"(entre {p.lower_bound:.0f} y {p.upper_bound:.0f}) en la semana "
                        f"{label(p.year, p.epi_week)} ({level_text_es(p.risk_level).lower()}).",
                        prediction_id=p.id))
        return out

    def evaluate(self, send_email: bool = True) -> EvaluationResult:
        candidates = self._candidates()
        now = datetime.now(UTC)
        since = min((c.year for c in candidates), default=now.year) - 1
        # Every recent alert (active or closed) by key; the newest wins
        existing: dict[tuple, Alert] = {}
        for a in self.db.scalars(select(Alert).where((Alert.active.is_(True)) | (Alert.year >= since))
                                 .order_by(Alert.id)):
            existing[(a.municipality_id, a.disease_id, a.year, a.epi_week, a.origin)] = a
        active = {k: a for k, a in existing.items() if a.active}
        created: list[Alert] = []
        updated = 0
        current = set()
        for c in candidates:
            key = (c.municipality_id, c.disease_id, c.year, c.epi_week, c.origin)
            a = existing.get(key)
            worse = a is not None and RiskLevel(c.level).rank > RiskLevel(a.risk_level).rank
            if a is None:
                a = Alert(municipality_id=c.municipality_id, disease_id=c.disease_id, prediction_id=c.prediction_id,
                          year=c.year, epi_week=c.epi_week, risk_level=c.level, origin=c.origin,
                          message=c.message, active=True)
                self.db.add(a)
                created.append(a)
            elif not a.active:
                # An administrator closed it: it only reopens when the risk got worse
                if not worse:
                    continue
                a.active, a.closed_at, a.email_notified = True, None, False
                a.risk_level, a.message, a.prediction_id = c.level, c.message, c.prediction_id
                updated += 1
            elif a.message != c.message or a.risk_level != c.level:
                a.risk_level, a.message, a.prediction_id = c.level, c.message, c.prediction_id
                if worse:
                    a.email_notified = False  # notify again when it gets worse
                updated += 1
            current.add(key)
        closed = 0
        for key, a in active.items():
            if key not in current:
                a.active, a.closed_at = False, now
                closed += 1
        self.db.commit()

        sent = self.notify() if send_email else 0
        logger.info("Alerts: %d new, %d updated, %d closed, %d e-mails", len(created), updated, closed, sent)
        return EvaluationResult(new=len(created), updated=updated, closed=closed, active=len(current),
                                emails_sent=sent)

    def _deliveries(self, pending: list[Alert]) -> list[tuple[list[str], list[Alert]]]:
        """(recipients, alerts) of each e-mail. Every citizen gets their own e-mail with the alerts of
        their municipality, so nobody sees anyone else's address."""
        deliveries = []
        if settings.alert_recipients:
            deliveries.append((settings.alert_recipients, pending))
        if settings.ALERTS_TO_CITIZENS:
            by_municipality: dict[int, list[Alert]] = {}
            for a in pending:
                by_municipality.setdefault(a.municipality_id, []).append(a)
            citizens = self.db.scalars(select(User).join(Role).where(
                Role.name == RoleName.CITIZEN.value, User.active.is_(True),
                User.municipality_id.in_(list(by_municipality))))
            deliveries.extend(([u.email], by_municipality[u.municipality_id]) for u in citizens)
        return deliveries

    def notify(self) -> int:
        pending = list(self.db.scalars(select(Alert).where(Alert.active.is_(True), Alert.email_notified.is_(False))))
        if not pending:
            return 0
        notified: set[int] = set()
        for recipients, alerts in self._deliveries(pending):
            rows = [{"level": a.risk_level, "level_text": level_text_es(a.risk_level), "message": a.message}
                    for a in alerts]
            any_red = any(a.risk_level == RiskLevel.RED for a in alerts)
            subject = f"{'🔴' if any_red else '🟠'} {len(alerts)} alerta(s) temprana(s) de brotes en Nariño"
            if self.notifier.send(recipients, subject, alerts_html(rows, settings.FRONTEND_URL)):
                notified.update(a.id for a in alerts)
        for a in pending:
            if a.id in notified:
                a.email_notified = True
        self.db.commit()
        return len(notified)

    # ── queries ──────────────────────────────────────────────────────────────
    def active(self) -> list[AlertOut]:
        alerts = self.db.scalars(select(Alert).where(Alert.active.is_(True)))

        # Most severe first; at the same level, what is already observed before what is predicted
        def priority(a: Alert) -> tuple[int, bool, int]:
            return (-RiskLevel(a.risk_level).rank, a.origin != AlertOrigin.OBSERVED, a.municipality_id)
        return [alert_out(a) for a in sorted(alerts, key=priority)]

    def list_page(self, active: bool | None, offset: int, limit: int) -> Page[AlertOut]:
        stmt = select(Alert)
        total = select(func.count()).select_from(Alert)
        if active is not None:
            stmt, total = stmt.where(Alert.active.is_(active)), total.where(Alert.active.is_(active))
        rows = self.db.scalars(stmt.order_by(Alert.created_at.desc(), Alert.id.desc()).offset(offset).limit(limit))
        return Page[AlertOut](items=[alert_out(a) for a in rows], total=self.db.scalar(total) or 0,
                              offset=offset, limit=limit)

    def search(self, filters: AlertFilters, offset: int = 0, limit: int = 20) -> Page[AlertOut]:
        """Public history search: free text (message, municipality or disease) and filters.
        Most severe and most recent first."""
        conditions = []
        if filters.q:
            pattern = f"%{filters.q.strip()}%"
            conditions.append(or_(Alert.message.ilike(pattern), Municipality.name.ilike(pattern),
                                  Disease.name.ilike(pattern), Disease.code.ilike(pattern)))
        if filters.municipality_id is not None:
            conditions.append(Alert.municipality_id == filters.municipality_id)
        if filters.disease_id is not None:
            conditions.append(Alert.disease_id == filters.disease_id)
        if filters.level:
            conditions.append(Alert.risk_level == filters.level.value)
        if filters.origin:
            conditions.append(Alert.origin == filters.origin.value)
        if filters.active is not None:
            conditions.append(Alert.active.is_(filters.active))
        base = select(Alert).join(Municipality, Alert.municipality_id == Municipality.id) \
            .join(Disease, Alert.disease_id == Disease.id).where(*conditions)
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self.db.scalars(base.order_by(Alert.year.desc(), Alert.epi_week.desc(), Alert.id.desc())
                               .offset(offset).limit(limit))
        return Page[AlertOut](items=[alert_out(a) for a in rows], total=total, offset=offset, limit=limit)

    def close(self, alert_id: int) -> AlertOut:
        a = self.db.get(Alert, alert_id)
        if a is None:
            raise NotFoundError(f"La alerta {alert_id} no existe")
        if a.active:
            a.active, a.closed_at = False, datetime.now(UTC)
            self.db.commit()
        return alert_out(a)
