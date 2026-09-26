import sqlite3

from load_seed import load_seed


def test_load_seed_creates_expected_tables(tmp_path):
    db_path = tmp_path / "app.db"

    load_seed(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tickets = conn.execute("SELECT * FROM tickets WHERE ticket_id = 'T-1042'").fetchone()
        customers = conn.execute("SELECT * FROM customers WHERE customer_id = 'C-05'").fetchone()

    assert set(tickets.keys()) == {"ticket_id", "customer_id", "created_at", "text"}
    assert tickets["customer_id"] == "C-77"

    assert set(customers.keys()) == {"customer_id", "name", "plan", "open_tickets"}
    assert customers["name"] == "Hooli"
    assert customers["open_tickets"] == 4


def test_load_seed_is_idempotent(tmp_path):
    db_path = tmp_path / "app.db"

    load_seed(db_path)
    load_seed(db_path)

    with sqlite3.connect(db_path) as conn:
        ticket_count = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        customer_count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

    assert ticket_count == 24
    assert customer_count == 20
