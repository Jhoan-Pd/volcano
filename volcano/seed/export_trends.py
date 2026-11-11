"""Export the searches stored in the database to the Google Trends fallback CSV.

Usage:  python -m volcano.seed.export_trends [--output data/trends/trends_fallback_narino.csv]

Regenerates the fallback `CsvTrendsSource` reads when pytrends fails.
"""
import argparse
import csv
from pathlib import Path

from sqlalchemy import select

from volcano.db.session import SessionLocal
from volcano.models import SearchTrend
from volcano.sources.trends import REPO_ROOT

OUTPUT = REPO_ROOT / "data" / "trends" / "trends_fallback_narino.csv"


def export(output: Path = OUTPUT) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db, open(output, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["term", "week_start", "interest", "region", "is_simulated"])
        n = 0
        for t in db.scalars(select(SearchTrend).order_by(SearchTrend.term, SearchTrend.week_start)):
            w.writerow([t.term, t.week_start.isoformat(), t.interest, t.region, int(t.is_simulated)])
            n += 1
    return n


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(f"{export(args.output)} rows → {args.output}")
