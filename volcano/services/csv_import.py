"""Bulk data upload from CSV files (admin panel).

Each file kind has its own importer (Strategy): it checks the columns, converts each row and stores
it with insert-or-update, so uploading the same file twice never duplicates data. Rows with errors
do not stop the upload: they are reported with their line number so the administrator can fix them.

Formats (headers required on the first line; separator , or ;):
    cases      divipola_code, disease, year, epi_week, cases
    weather    divipola_code, date, temp_max_c, temp_min_c, temp_mean_c, precipitation_mm, relative_humidity_pct
    events     event_type, activity_level, start_date, divipola_code, ash_intensity, so2_tons_per_day, description
    trends     term, week_start, interest

Files that still use the Spanish headers and values of the original templates (cod_divipola, anio,
CAIDA_CENIZA, AMARILLO…) are accepted too; they are translated on the way in.
"""
import csv
import io
from abc import ABC, abstractmethod
from datetime import date

from sqlalchemy import func, select

from volcano.models import (
    OfficialCase,
    PharmacyReport,
    Prediction,
    SearchTrend,
    TrainedModel,
    VolcanicEvent,
    WeatherRecord,
)
from volcano.models.enums import VolcanicEventType, VolcanoLevel, parse_enum
from volcano.repositories.domain import (
    DiseaseRepository,
    MunicipalityRepository,
    OfficialCaseRepository,
    SearchTrendRepository,
    VolcanicEventRepository,
    WeatherRecordRepository,
)
from volcano.schemas.data_sources import DataStatus, ImportResult, RowError, SourceStatus
from volcano.shared.epi import label, week_of, weeks_in_year
from volcano.shared.errors import BusinessRuleError

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_REPORTED_ERRORS = 50
LEGACY_KINDS = {"casos": "cases", "clima": "weather", "eventos": "events", "tendencias": "trends"}
LEGACY_HEADERS = {
    "cod_divipola": "divipola_code", "enfermedad": "disease", "anio": "year", "semana_epi": "epi_week",
    "casos": "cases", "fecha": "date", "temp_media_c": "temp_mean_c", "precipitacion_mm": "precipitation_mm",
    "humedad_relativa_pct": "relative_humidity_pct", "tipo": "event_type", "nivel_actividad": "activity_level",
    "fecha_inicio": "start_date", "intensidad_ceniza": "ash_intensity", "so2_ton_dia": "so2_tons_per_day",
    "descripcion": "description", "termino": "term", "fecha_semana": "week_start", "indice": "interest",
}


class InvalidRowError(ValueError):
    pass


def _iso(moment) -> str | None:
    return moment.isoformat() if moment else None


def _integer(value: str, field: str, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        n = int(float(value.strip()))
    except (ValueError, AttributeError):
        raise InvalidRowError(f"«{field}» debe ser un número entero (llegó «{value}»)") from None
    if (minimum is not None and n < minimum) or (maximum is not None and n > maximum):
        raise InvalidRowError(f"«{field}» fuera de rango ({n})")
    return n


def _decimal(value: str | None, field: str) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        return float(value.strip().replace(",", "."))
    except ValueError:
        raise InvalidRowError(f"«{field}» debe ser numérico (llegó «{value}»)") from None


def _date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        raise InvalidRowError(f"«{field}» debe tener formato AAAA-MM-DD (llegó «{value}»)") from None


class Importer(ABC):
    kind: str
    columns: tuple[str, ...]
    optional: tuple[str, ...] = ()

    def __init__(self, db):
        self.db = db
        self.municipalities = {m.divipola_code: m.id for m in MunicipalityRepository(db).list_page(limit=1000)}

    def municipality(self, code: str) -> int:
        mid = self.municipalities.get((code or "").strip().zfill(5))
        if mid is None:
            raise InvalidRowError(f"El municipio con DIVIPOLA «{code}» no está registrado")
        return mid

    @abstractmethod
    def convert(self, row: dict[str, str]) -> dict: ...

    @abstractmethod
    def save(self, rows: list[dict]) -> tuple[int, int]: ...


class CasesImporter(Importer):
    kind = "cases"
    columns = ("divipola_code", "disease", "year", "epi_week", "cases")

    def __init__(self, db):
        super().__init__(db)
        self.diseases = {d.code: d.id for d in DiseaseRepository(db).list_page(limit=1000)}

    def convert(self, r):
        disease_id = self.diseases.get(r["disease"].strip().upper())
        if disease_id is None:
            raise InvalidRowError(f"La enfermedad «{r['disease']}» no existe (usa el código, p. ej. IRA)")
        year = _integer(r["year"], "year", 2000, 2100)
        return {"municipality_id": self.municipality(r["divipola_code"]), "disease_id": disease_id, "year": year,
                "epi_week": _integer(r["epi_week"], "epi_week", 1, weeks_in_year(year)),
                "cases": _integer(r["cases"], "cases", 0), "source": "CSV", "is_simulated": False}

    def save(self, rows):
        return OfficialCaseRepository(self.db).upsert_weeks(rows)


class WeatherImporter(Importer):
    kind = "weather"
    columns = ("divipola_code", "date", "temp_max_c", "temp_min_c", "temp_mean_c", "precipitation_mm",
               "relative_humidity_pct")

    def convert(self, r):
        row = {"municipality_id": self.municipality(r["divipola_code"]), "date": _date(r["date"], "date"),
               "is_forecast": False, "is_simulated": False, "source": "CSV"}
        for c in self.columns[2:]:
            row[c] = _decimal(r.get(c), c)
        h = row["relative_humidity_pct"]
        if h is not None and not 0 <= h <= 100:
            raise InvalidRowError("La humedad debe estar entre 0 y 100")
        if row["precipitation_mm"] is not None and row["precipitation_mm"] < 0:
            raise InvalidRowError("La precipitación no puede ser negativa")
        return row

    def save(self, rows):
        return WeatherRecordRepository(self.db).upsert(rows, ("municipality_id", "date"), [
            WeatherRecord.municipality_id.in_({r["municipality_id"] for r in rows}),
            WeatherRecord.date.in_({r["date"] for r in rows})])


class EventsImporter(Importer):
    kind = "events"
    columns = ("event_type", "activity_level", "start_date", "divipola_code", "ash_intensity", "so2_tons_per_day",
               "description")
    optional = ("divipola_code", "ash_intensity", "so2_tons_per_day", "description")

    def convert(self, r):
        try:
            event_type = parse_enum(VolcanicEventType, r["event_type"])
        except ValueError:
            raise InvalidRowError(f"Tipo «{r['event_type']}» no válido") from None
        try:
            level = parse_enum(VolcanoLevel, r["activity_level"])
        except ValueError:
            raise InvalidRowError(f"Nivel «{r['activity_level']}» no válido (GREEN, YELLOW, ORANGE o RED)") from None
        code = (r.get("divipola_code") or "").strip()
        intensity = _integer(r.get("ash_intensity") or "0", "ash_intensity", 0, 3)
        if event_type == VolcanicEventType.ASH_FALL and (not code or intensity == 0):
            raise InvalidRowError("Una caída de ceniza necesita municipio e intensidad entre 1 y 3")
        return {"event_type": event_type.value, "activity_level": level.value,
                "start_date": _date(r["start_date"], "start_date"),
                "municipality_id": self.municipality(code) if code else None, "ash_intensity": intensity,
                "so2_tons_per_day": _decimal(r.get("so2_tons_per_day"), "so2_tons_per_day"),
                "description": (r.get("description") or "").strip() or None, "is_simulated": False}

    def save(self, rows):
        # Natural key: one event per type, date and municipality (or none, for bulletins)
        return VolcanicEventRepository(self.db).upsert(
            rows, ("event_type", "start_date", "municipality_id"),
            [VolcanicEvent.start_date.in_({r["start_date"] for r in rows})])


class TrendsImporter(Importer):
    kind = "trends"
    columns = ("term", "week_start", "interest")

    def convert(self, r):
        day = _date(r["week_start"], "week_start")
        year, week = week_of(day)
        interest = _decimal(r["interest"], "interest")
        if interest is None or not 0 <= interest <= 100:
            raise InvalidRowError("El índice de Google Trends va de 0 a 100")
        term = r["term"].strip().lower()
        if len(term) < 2:
            raise InvalidRowError("Término vacío")
        return {"term": term, "region": "CO-NAR", "year": year, "epi_week": week, "week_start": day,
                "interest": interest, "source": "csv", "is_simulated": False}

    def save(self, rows):
        return SearchTrendRepository(self.db).upsert(rows, ("term", "region", "year", "epi_week"),
                                                     [SearchTrend.term.in_({r["term"] for r in rows})])


IMPORTERS: dict[str, type[Importer]] = {
    c.kind: c for c in (CasesImporter, WeatherImporter, EventsImporter, TrendsImporter)
}


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("latin-1")  # Excel on Windows usually saves as ANSI


class CsvImportService:
    def __init__(self, db):
        self.db = db

    def import_file(self, kind: str, content: bytes) -> ImportResult:
        kind = LEGACY_KINDS.get(kind, kind)
        importer_cls = IMPORTERS.get(kind)
        if importer_cls is None:
            raise BusinessRuleError(f"Tipo «{kind}» no soportado. Usa: {', '.join(IMPORTERS)}")
        if len(content) > MAX_FILE_BYTES:
            raise BusinessRuleError("El archivo supera 5 MB")
        text = _decode(content)
        if not text.strip():
            raise BusinessRuleError("El archivo está vacío")
        try:
            dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",;")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        headers = [(c or "").strip().lower() for c in (reader.fieldnames or [])]
        reader.fieldnames = [LEGACY_HEADERS.get(h, h) for h in headers]
        importer = importer_cls(self.db)
        missing = [c for c in importer.columns if c not in reader.fieldnames and c not in importer.optional]
        if missing:
            raise BusinessRuleError(f"Faltan columnas: {', '.join(missing)}",
                                    details={"expected": list(importer.columns), "received": headers})
        valid, errors, read = [], [], 0
        for n, row in enumerate(reader, start=2):  # line 1 is the header
            read += 1
            try:
                valid.append(importer.convert({k: (v or "") for k, v in row.items() if k}))
            except InvalidRowError as exc:
                if len(errors) < MAX_REPORTED_ERRORS:
                    errors.append(RowError(row=n, message=str(exc)))
        inserted, updated = importer.save(valid) if valid else (0, 0)
        return ImportResult(kind=kind, rows_read=read, inserted=inserted, updated=updated, errors=errors)

    # ── source status (admin panel) ──────────────────────────────────────────
    def status(self) -> DataStatus:
        def count(model, simulated=None):
            stmt = select(func.count()).select_from(model)
            if simulated is not None:
                stmt = stmt.where(model.is_simulated.is_(simulated))
            return self.db.scalar(stmt) or 0

        def latest(model) -> str | None:
            row = self.db.execute(select(model.year, model.epi_week)
                                  .order_by(model.year.desc(), model.epi_week.desc()).limit(1)).first()
            return label(*row) if row else None

        def updated(model) -> str | None:
            v = self.db.scalar(select(func.max(model.updated_at)))
            return v.isoformat() if v else None

        last_weather = self.db.scalar(select(func.max(WeatherRecord.date)).where(WeatherRecord.is_forecast.is_(False)))
        # `source` is the Spanish name shown in the admin panel
        sources = [
            SourceStatus(source="Casos oficiales (SIVIGILA / CSV)", table="official_cases", rows=count(OfficialCase),
                         simulated=count(OfficialCase, True), latest_week=latest(OfficialCase),
                         last_updated=updated(OfficialCase)),
            SourceStatus(source="Clima (Open-Meteo)", table="weather_records", rows=count(WeatherRecord),
                         simulated=count(WeatherRecord, True),
                         latest_week=label(*week_of(last_weather)) if last_weather else None,
                         last_updated=updated(WeatherRecord)),
            SourceStatus(source="Búsquedas (Google Trends)", table="search_trends", rows=count(SearchTrend),
                         simulated=count(SearchTrend, True), latest_week=latest(SearchTrend),
                         last_updated=updated(SearchTrend)),
            SourceStatus(source="Reportes de farmacias", table="pharmacy_reports", rows=count(PharmacyReport),
                         simulated=count(PharmacyReport, True), latest_week=latest(PharmacyReport),
                         last_updated=updated(PharmacyReport)),
            SourceStatus(source="Eventos volcánicos (SGC)", table="volcanic_events", rows=count(VolcanicEvent),
                         simulated=count(VolcanicEvent, True), latest_week=None, last_updated=updated(VolcanicEvent)),
            SourceStatus(source="Predicciones del modelo", table="predictions", rows=count(Prediction), simulated=0,
                         latest_week=latest(Prediction),
                         last_updated=_iso(self.db.scalar(select(func.max(TrainedModel.trained_at))))),
        ]
        return DataStatus(sources=sources)
