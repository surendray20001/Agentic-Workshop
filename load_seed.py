"""Loads seed/tickets.csv and seed/customers.csv into app.db."""

import contextlib
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "app.db"
TICKETS_CSV = ROOT / "seed" / "tickets.csv"
CUSTOMERS_CSV = ROOT / "seed" / "customers.csv"


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_seed(db_path: Path = DB_PATH) -> None:
    """Load seed/tickets.csv and seed/customers.csv into db_path, replacing any existing tables."""
    tickets = _read_csv(TICKETS_CSV)
    customers = _read_csv(CUSTOMERS_CSV)

    # Table and column names must match mcp/triage_server.py's queries exactly —
    # that server is read-only and cannot be adjusted to follow a rename here.
    with contextlib.closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute("DROP TABLE IF EXISTS tickets")
        conn.execute("DROP TABLE IF EXISTS customers")
        conn.execute(
            """
            CREATE TABLE tickets (
                ticket_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                text TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE customers (
                customer_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                plan TEXT NOT NULL,
                open_tickets INTEGER NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO tickets (ticket_id, customer_id, created_at, text) VALUES (?, ?, ?, ?)",
            [(t["ticket_id"], t["customer_id"], t["created_at"], t["text"]) for t in tickets],
        )
        conn.executemany(
            "INSERT INTO customers (customer_id, name, plan, open_tickets) VALUES (?, ?, ?, ?)",
            [(c["customer_id"], c["name"], c["plan"], int(c["open_tickets"])) for c in customers],
        )


if __name__ == "__main__":
    load_seed()
    with contextlib.closing(sqlite3.connect(DB_PATH)) as conn:
        ticket_count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        customer_count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    print(f"Loaded {DB_PATH}: {ticket_count} tickets, {customer_count} customers")
