"""Weekly pharmacy reports: create, history, edit and delete.

Business rules:
- A PHARMACY user only reports for the pharmacy assigned to them; the ADMIN for any pharmacy.
- Only finished epidemiological weeks can be reported (not the current or future ones).
- A pharmacy may create or fix the reports of the last EDIT_WINDOW_WEEKS weeks; older ones
  can only be changed by the ADMIN (so the model's history is not altered without control).
- A week is reported once (POST); PUT fixes it.
"""
from datetime import date, timedelta

from sqlalchemy import delete, select

from volcano.models import Pharmacy, PharmacyReport, User
from volcano.models.enums import ProductCategory, RoleName
from volcano.schemas.pharmacy import (
    MyPharmacy,
    ReportableWeek,
    ReportItem,
    ReportItemOut,
    WeeklyReportIn,
    WeeklyReportOut,
)
from volcano.shared.epi import EpiWeek, label, last_complete_week, shift, week_start
from volcano.shared.errors import BusinessRuleError, ConflictError, NotFoundError, PermissionDeniedError

EDIT_WINDOW_WEEKS = 8
CATEGORY_ORDER = list(ProductCategory.__members__)


class PharmacyReportService:
    def __init__(self, db, actor: User):
        self.db = db
        self.actor = actor
        self.is_admin = actor.role_name == RoleName.ADMIN

    # ── the user's pharmacy ──────────────────────────────────────────────────
    def pharmacy(self, pharmacy_id: int | None = None) -> Pharmacy:
        if self.is_admin:
            if pharmacy_id is None:
                raise BusinessRuleError("Como ADMIN debes indicar pharmacy_id")
            p = self.db.get(Pharmacy, pharmacy_id)
            if p is None:
                raise NotFoundError(f"Farmacia {pharmacy_id} no existe")
            return p
        p = self.db.scalar(select(Pharmacy).where(Pharmacy.user_id == self.actor.id))
        if p is None:
            raise NotFoundError("Tu usuario no está asignado a ninguna farmacia. Pide al administrador que te asigne.")
        if pharmacy_id is not None and pharmacy_id != p.id:
            raise PermissionDeniedError("Solo puedes reportar por tu propia farmacia")
        return p

    @staticmethod
    def reportable_weeks(today: date | None = None) -> list[EpiWeek]:
        latest = last_complete_week(today)
        return [shift(*latest, -k) for k in range(EDIT_WINDOW_WEEKS)]

    def _check_week(self, year: int, week: int) -> None:
        if (year, week) > last_complete_week():
            raise BusinessRuleError("Solo se pueden reportar semanas epidemiológicas ya terminadas")
        if not self.is_admin and (year, week) not in self.reportable_weeks():
            raise BusinessRuleError(
                f"Solo puedes registrar o corregir las últimas {EDIT_WINDOW_WEEKS} semanas. "
                "Para semanas anteriores contacta al administrador.")

    # ── reads ────────────────────────────────────────────────────────────────
    def _week_rows(self, pharmacy_id: int, year: int, week: int) -> list[PharmacyReport]:
        return list(self.db.scalars(select(PharmacyReport).where(
            PharmacyReport.pharmacy_id == pharmacy_id, PharmacyReport.year == year,
            PharmacyReport.epi_week == week).order_by(PharmacyReport.category)))

    def _to_out(self, p: Pharmacy, year: int, week: int, rows: list[PharmacyReport]) -> WeeklyReportOut:
        start = week_start(year, week)
        rows = sorted(rows, key=lambda r: CATEGORY_ORDER.index(r.category) if r.category in CATEGORY_ORDER else 99)
        author_id = next((r.reported_by_id for r in rows if r.reported_by_id), None)
        author = self.db.get(User, author_id) if author_id else None
        return WeeklyReportOut(
            pharmacy_id=p.id, pharmacy=p.name, year=year, epi_week=week, label=label(year, week),
            start_date=start, end_date=start + timedelta(days=6),
            items=[ReportItemOut(category=r.category, units=r.units) for r in rows],
            total_units=sum(r.units for r in rows), is_simulated=any(r.is_simulated for r in rows),
            updated_at=max((r.updated_at for r in rows), default=None),
            reported_by=author.name if author else None,
            editable=self.is_admin or (year, week) in self.reportable_weeks(),
        )

    def my_pharmacy(self, pharmacy_id: int | None = None) -> MyPharmacy:
        p = self.pharmacy(pharmacy_id)
        reported = set(self.db.execute(
            select(PharmacyReport.year, PharmacyReport.epi_week).where(PharmacyReport.pharmacy_id == p.id)
            .distinct()).all())
        weeks = []
        for y, w in self.reportable_weeks():
            start = week_start(y, w)
            weeks.append(ReportableWeek(year=y, epi_week=w, label=label(y, w), start_date=start,
                                        end_date=start + timedelta(days=6), reported=(y, w) in reported))
        return MyPharmacy(id=p.id, name=p.name, tax_id=p.tax_id, address=p.address, municipality_id=p.municipality_id,
                          municipality=p.municipality.name if p.municipality else "", active=p.active,
                          reportable_weeks=weeks, categories=CATEGORY_ORDER)

    def history(self, pharmacy_id: int | None = None, weeks: int = 26) -> list[WeeklyReportOut]:
        p = self.pharmacy(pharmacy_id)
        since = shift(*last_complete_week(), -(weeks - 1))
        by_week: dict[EpiWeek, list[PharmacyReport]] = {}
        for r in self.db.scalars(select(PharmacyReport).where(PharmacyReport.pharmacy_id == p.id)):
            if (r.year, r.epi_week) >= since:
                by_week.setdefault((r.year, r.epi_week), []).append(r)
        return [self._to_out(p, y, w, by_week[(y, w)]) for y, w in sorted(by_week, reverse=True)]

    def get(self, year: int, week: int, pharmacy_id: int | None = None) -> WeeklyReportOut:
        p = self.pharmacy(pharmacy_id)
        rows = self._week_rows(p.id, year, week)
        if not rows:
            raise NotFoundError(f"No hay reporte de la semana {label(year, week)}")
        return self._to_out(p, year, week, rows)

    # ── writes ───────────────────────────────────────────────────────────────
    def _save_items(self, p: Pharmacy, year: int, week: int, items: list[ReportItem]) -> None:
        self.db.execute(delete(PharmacyReport).where(
            PharmacyReport.pharmacy_id == p.id, PharmacyReport.year == year, PharmacyReport.epi_week == week))
        self.db.add_all([PharmacyReport(pharmacy_id=p.id, year=year, epi_week=week, category=i.category.value,
                                        units=i.units, reported_by_id=self.actor.id, is_simulated=False)
                         for i in items])
        self.db.commit()

    def create(self, data: WeeklyReportIn) -> WeeklyReportOut:
        p = self.pharmacy(data.pharmacy_id)
        if not p.active:
            raise BusinessRuleError("La farmacia está inactiva y no puede reportar")
        self._check_week(data.year, data.epi_week)
        if self._week_rows(p.id, data.year, data.epi_week):
            raise ConflictError(f"Ya existe el reporte de la semana {label(data.year, data.epi_week)}. "
                                "Usa la opción Editar para corregirlo.")
        self._save_items(p, data.year, data.epi_week, data.items)
        return self.get(data.year, data.epi_week, p.id if self.is_admin else None)

    def update(self, year: int, week: int, items: list[ReportItem], pharmacy_id: int | None = None) -> WeeklyReportOut:
        p = self.pharmacy(pharmacy_id)
        self._check_week(year, week)
        if not self._week_rows(p.id, year, week):
            raise NotFoundError(f"No hay reporte de la semana {label(year, week)} para editar")
        self._save_items(p, year, week, items)
        return self.get(year, week, p.id if self.is_admin else None)

    def save_week(self, year: int, week: int, items: list[ReportItem], pharmacy_id: int | None = None) -> bool:
        """Create or replace one week's report (bulk upload of a history).

        Same rules as create/update: own and active pharmacy, finished week and, for a PHARMACY
        user, inside the edit window. Returns True when the week did not exist."""
        p = self.pharmacy(pharmacy_id)
        if not p.active:
            raise BusinessRuleError("La farmacia está inactiva y no puede reportar")
        self._check_week(year, week)
        created = not self._week_rows(p.id, year, week)
        self._save_items(p, year, week, items)
        return created

    def delete(self, year: int, week: int, pharmacy_id: int | None = None) -> None:
        p = self.pharmacy(pharmacy_id)
        self._check_week(year, week)
        if not self._week_rows(p.id, year, week):
            raise NotFoundError(f"No hay reporte de la semana {label(year, week)}")
        self.db.execute(delete(PharmacyReport).where(
            PharmacyReport.pharmacy_id == p.id, PharmacyReport.year == year, PharmacyReport.epi_week == week))
        self.db.commit()
