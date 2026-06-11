import sqlite3
import os
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(__file__), "cflo.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS borrowers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            loan_account TEXT NOT NULL,
            outstanding_balance REAL NOT NULL,
            emi_amount REAL NOT NULL,
            emi_due_date TEXT NOT NULL,
            dpd INTEGER DEFAULT 0,
            risk_segment TEXT DEFAULT 'S4',
            last_payment_date TEXT,
            last_payment_amount REAL
        );

        CREATE TABLE IF NOT EXISTS ptp_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id TEXT NOT NULL,
            promised_amount REAL NOT NULL,
            promised_date TEXT NOT NULL,
            captured_at TEXT NOT NULL,
            channel TEXT DEFAULT 'voice',
            status TEXT DEFAULT 'pending'
        );

        CREATE TABLE IF NOT EXISTS call_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            borrower_id TEXT,
            call_sid TEXT,
            direction TEXT,
            intent TEXT,
            transcript TEXT,
            outcome TEXT,
            started_at TEXT,
            ended_at TEXT
        );
    """)

    cursor.execute("SELECT COUNT(*) FROM borrowers")
    if cursor.fetchone()[0] == 0:
        borrowers = [
            ("B001", "Ravi Sharma", "+918800662025", "asmitaasmani@gmail.com", "LOAN-4821", 84000, 8400, "2026-06-05", 12, "S2", "2026-04-20", 4000),
            ("B002", "Priya Mehta",   "+14155550002", "priya@email.com",  "LOAN-7103", 45000, 5200, "2026-06-08",  3, "S4", "2026-05-28", 5200),
            ("B003", "Amit Kumar",    "+14155550003", "amit@email.com",   "LOAN-2299", 12000, 3000, "2026-06-03",  0, "S5", "2026-06-01", 3000),
            ("B004", "Sunita Nair",   "+14155550004", "sunita@email.com", "LOAN-8844", 95000, 9500, "2026-05-25", 45, "S1", "2026-03-10", 2000),
            ("B005", "Deepak Verma",  "+14155550005", "deepak@email.com", "LOAN-3312", 30000, 4500, "2026-06-10",  0, "S5", "2026-06-02", 4500),
        ]
        cursor.executemany("""
            INSERT INTO borrowers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, borrowers)

    conn.commit()
    conn.close()
    print("Database initialised with mock borrower data")

def get_borrower_by_phone(phone: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM borrowers WHERE phone = ?", (phone,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_borrower_by_id(borrower_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM borrowers WHERE id = ?", (borrower_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def log_ptp(borrower_id: str, amount: float, promised_date: str, channel: str = "voice"):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ptp_log (borrower_id, promised_amount, promised_date, captured_at, channel)
        VALUES (?, ?, ?, ?, ?)
    """, (borrower_id, amount, promised_date, datetime.now().isoformat(), channel))
    conn.commit()
    conn.close()

def log_call(borrower_id: str, call_sid: str, direction: str,
             intent: str, transcript: str, outcome: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO call_log (borrower_id, call_sid, direction, intent, transcript, outcome, started_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (borrower_id, call_sid, direction, intent, transcript, outcome, datetime.now().isoformat()))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()