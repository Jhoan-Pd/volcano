"""Google Trends symptom-search adapters.

`pytrends` is not an official API: Google rate-limits it (HTTP 429) and changes the format
without notice. That is why there are three levels, from freshest to safest:

1. `TrendsSource` queries Google Trends through pytrends.
2. When it fails it falls back to `CsvTrendsSource`: CSV files downloaded by hand from
   trends.google.com ("multiTimeline.csv") or in our own long format.
3. The service (`SearchTrendService`) stores everything in `search_trends`, which works as a
   cache: if the source is down, the model keeps using what was stored.

Google normalizes every query to 0-100 within the requested period, so one term is requested
per call and each series keeps its own scale. Periods longer than 5 years (where Google switches
to monthly data) are requested as overlapping weekly windows stitched together by rescaling with
the mean of the overlap.
"""
import csv
import io
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from volcano.shared.config import settings
from volcano.shared.epi import week_of, week_start
from volcano.sources.base import DataSource, DataSourceError, logger

REPO_ROOT = Path(__file__).resolve().parents[2]
WINDOW_DAYS = 1800  # < 5 years: Google returns weekly data
OVERLAP_DAYS = 364

# Long-format headers: the English names, plus the Spanish ones older exports still use
LONG_FORMAT_COLUMNS = {
    "term": ("term", "termino"),
    "week_start": ("week_start", "fecha_semana"),
    "interest": ("interest", "indice"),
    "region": ("region",),
    "is_simulated": ("is_simulated", "es_simulado"),
}
# First column of a trends.google.com export depending on language and granularity
DATE_HEADERS = ("semana", "week", "día", "dia", "day", "mes", "month")


def _row(term: str, region: str, day: date, interest: float, source: str, simulated: bool = False) -> dict[str, Any]:
    year, week = week_of(day)
    return {
        "term": term, "region": region, "year": year, "epi_week": week,
        "week_start": week_start(year, week), "interest": round(float(interest), 2),
        "source": source, "is_simulated": simulated,
    }


def _number(text: str) -> float | None:
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("<"):  # Google writes "<1" when interest is very low
        return 0.5
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def _date(text: str) -> date | None:
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _pick(record: dict[str, str], field: str) -> str:
    return next((record[k] for k in LONG_FORMAT_COLUMNS[field] if record.get(k)), "")


class CsvTrendsSource(DataSource):
    """Reads Google Trends CSV files. Two formats are accepted:

    - Official trends.google.com export (multiTimeline.csv):
          Categoría: Todas las categorías
          <blank line>
          Semana,fiebre: (Nariño),dengue: (Nariño)
          2021-10-03,54,12
    - Our long format: term,week_start,interest[,region][,is_simulated]
    """

    name = "csv"

    def __init__(self, directory: str | Path | None = None):
        d = Path(directory or settings.TRENDS_CSV_DIR)
        self.directory = d if d.is_absolute() else REPO_ROOT / d

    # ── parsing ──────────────────────────────────────────────────────────────
    @classmethod
    def parse(cls, content: str, region: str = "CO-NAR") -> list[dict[str, Any]]:
        lines = content.lstrip("﻿").splitlines()
        rows: list[dict[str, Any]] = []
        term_headers = LONG_FORMAT_COLUMNS["term"]
        long_header = next((i for i, line in enumerate(lines) if line.lower().split(",")[0] in term_headers), None)
        if long_header is not None:
            for r in csv.DictReader(io.StringIO("\n".join(lines[long_header:]))):
                day, value, term = _date(_pick(r, "week_start")), _number(_pick(r, "interest")), _pick(r, "term")
                if day is None or value is None or not term:
                    continue
                simulated = _pick(r, "is_simulated").strip().lower() in ("1", "true", "yes", "si", "sí")
                rows.append(_row(term.strip().lower(), (_pick(r, "region") or region).strip(), day, value,
                                 "simulated" if simulated else cls.name, simulated))
            return rows

        # Google format: find the header row ("Semana", "Week", "Día"…)
        start = next((i for i, line in enumerate(lines) if line.split(",")[0].strip().lower() in DATE_HEADERS), None)
        if start is None:
            raise DataSourceError("Trends CSV without a recognizable header")
        reader = csv.reader(io.StringIO("\n".join(lines[start:])))
        header = next(reader)
        terms = [c.split(":")[0].strip().lower() for c in header[1:]]
        for r in reader:
            if not r:
                continue
            day = _date(r[0])
            if day is None:
                continue
            for term, text in zip(terms, r[1:], strict=False):  # incomplete rows: ignore what is missing
                value = _number(text)
                if value is not None:
                    rows.append(_row(term, region, day, value, cls.name))
        return rows

    # ── Strategy ─────────────────────────────────────────────────────────────
    def fetch(self, *, terms: list[str], region: str = "CO-NAR", since: date | None = None,
              until: date | None = None, **_: Any) -> list[dict[str, Any]]:
        if not self.directory.is_dir():
            raise DataSourceError(f"Fallback directory {self.directory} does not exist")
        wanted = {t.lower() for t in terms}
        by_key: dict[tuple, dict] = {}
        for path in sorted(self.directory.glob("*.csv")):
            try:
                rows = self.parse(path.read_text(encoding="utf-8"), region)
            except (DataSourceError, UnicodeDecodeError) as exc:
                logger.warning("Trends CSV %s skipped: %s", path.name, exc)
                continue
            for r in rows:
                if r["term"] not in wanted or r["region"] != region:
                    continue
                if (since and r["week_start"] < since) or (until and r["week_start"] > until):
                    continue
                by_key[(r["term"], r["year"], r["epi_week"])] = r  # the last file wins
        if not by_key:
            raise DataSourceError("The fallback CSV files have no data for those terms")
        return sorted(by_key.values(), key=lambda r: (r["term"], r["week_start"]))

    def check(self) -> None:
        if not any(self.directory.glob("*.csv")):
            raise DataSourceError("No fallback CSV files")


def _pytrends_client():  # pragma: no cover - depends on Google's network
    from pytrends.request import TrendReq  # noqa: PLC0415 - deferred import: pytrends is optional and slow

    return TrendReq(hl="es-CO", tz=300, timeout=(10, 25), retries=1, backoff_factor=0.5)


class TrendsSource(DataSource):
    """Google Trends through pytrends with an automatic CSV fallback (chain of responsibility)."""

    name = "pytrends"

    def __init__(self, fallback: DataSource | None = None, client_factory: Callable[[], Any] | None = None,
                 pause: float | None = None, enabled: bool | None = None):
        self.fallback = fallback if fallback is not None else CsvTrendsSource()
        self._factory = client_factory or _pytrends_client
        self.pause = settings.TRENDS_PAUSE_SECONDS if pause is None else pause
        self.enabled = settings.TRENDS_ENABLED if enabled is None else enabled
        self.last_source: str | None = None

    @staticmethod
    def windows(since: date, until: date) -> list[tuple[date, date]]:
        """Windows shorter than 5 years, newest first, overlapping by one year."""
        out, end = [], until
        while True:
            start = max(since, end - timedelta(days=WINDOW_DAYS))
            out.append((start, end))
            if start <= since:
                return out
            end = start + timedelta(days=OVERLAP_DAYS)

    @staticmethod
    def stitch(series: list[dict[date, float]]) -> dict[date, float]:
        """Join windows (the first is the newest) rescaling each one with the overlap."""
        joined = dict(series[0])
        for older in series[1:]:
            common = [d for d in older if d in joined]
            older_sum = sum(older[d] for d in common)
            factor = (sum(joined[d] for d in common) / older_sum) if common and older_sum else 1.0
            for d, v in older.items():
                joined.setdefault(d, v * factor)
        peak = max(joined.values(), default=0) or 1.0
        return {d: v * 100 / peak for d, v in joined.items()}

    def _query(self, term: str, region: str, since: date, until: date) -> dict[date, float]:
        client = self._factory()
        series = []
        for start, end in self.windows(since, until):
            client.build_payload([term], geo=region, timeframe=f"{start.isoformat()} {end.isoformat()}")
            df = client.interest_over_time()
            if df is None or df.empty or term not in df.columns:
                raise DataSourceError(f"Google Trends returned no data for '{term}'")
            if "isPartial" in df.columns:
                df = df[~df["isPartial"].astype(bool)]
            series.append({ts.date(): float(v) for ts, v in df[term].items()})
            time.sleep(self.pause)  # avoids being blocked for too many requests (HTTP 429)
        return self.stitch(series)

    def fetch(self, *, terms: list[str], region: str | None = None, since: date,
              until: date | None = None, **_: Any) -> list[dict[str, Any]]:
        region = region or settings.TRENDS_REGION
        until = until or date.today()
        if self.enabled:
            try:
                rows = []
                for t in terms:
                    series = self._query(t.lower(), region, since, until)
                    rows += [_row(t.lower(), region, d, v, self.name) for d, v in sorted(series.items())]
                self.last_source = self.name
                logger.info("Google Trends: %d rows (%s)", len(rows), ", ".join(terms))
                return rows
            except Exception as exc:
                logger.warning("pytrends failed (%s): using the CSV fallback", exc)
        rows = self.fallback.fetch(terms=terms, region=region, since=since, until=until)
        self.last_source = self.fallback.name
        return rows

    def check(self) -> None:  # pragma: no cover - network
        self._query("fiebre", settings.TRENDS_REGION, date.today() - timedelta(days=90), date.today())
