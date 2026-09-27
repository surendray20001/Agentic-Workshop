"""Load Case Expenses' seed CSVs into cases/expense/app.db.

Idempotent: drops and recreates each table, so running this twice yields an
identical database. Isolated from the root app.db used by Saturday's triage
agent.
"""

import csv
import sqlite3
from pathlib import Path

CASE_DIR = Path(__file__).resolve().parent
SEED_DIR = CASE_DIR / "seed"
DB_PATH = CASE_DIR / "app.db"

TABLES = {
    "claims": {
        "file": "claims.csv",
        "columns": ["claim_id", "employee_id", "submitted_at", "purpose"],
    },
    "employees": {
        "file": "employees.csv",
        "columns": ["employee_id", "name", "level", "city", "department"],
    },
    "limits": {
        "file": "limits.csv",
        "columns": ["level", "city", "category", "limit_cad"],
    },
    "line_items": {
        "file": "line_items.csv",
        "columns": [
            "line_id",
            "claim_id",
            "date",
            "city",
            "category",
            "merchant",
            "amount",
            "has_receipt",
            "description",
        ],
    },
}


def _load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_seed() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        for table, spec in TABLES.items():
            columns = spec["columns"]
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            column_defs = ", ".join(f'"{c}" TEXT' for c in columns)
            conn.execute(f"CREATE TABLE {table} ({column_defs})")

            rows = _load_csv(SEED_DIR / spec["file"])
            placeholders = ", ".join("?" for _ in columns)
            conn.executemany(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                [tuple(row[c] for c in columns) for row in rows],
            )
        conn.commit()


if __name__ == "__main__":
    load_seed()
    print(f"Loaded seed data into {DB_PATH}")
