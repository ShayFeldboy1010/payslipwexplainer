import sqlite3, os, json, time, uuid
# Simple SQLite storage for payslip text
DB_PATH = os.getenv("DB_PATH", "payslips.db")

def _conn():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    return con

def init_db():
    con = _conn()
    con.execute("""
    CREATE TABLE IF NOT EXISTS payslips (
      id TEXT PRIMARY KEY,
      text TEXT NOT NULL,
      meta TEXT,
      created_at REAL
    )
    """)
    con.commit(); con.close()

def save_payslip(text: str, meta: dict) -> str:
    pid = str(uuid.uuid4())
    con = _conn()
    con.execute("INSERT INTO payslips (id, text, meta, created_at) VALUES (?, ?, ?, ?)",
                (pid, text, json.dumps(meta or {}), time.time()))
    con.commit(); con.close()
    return pid

def get_payslip(pid: str) -> str | None:
    con = _conn()
    cur = con.execute("SELECT text FROM payslips WHERE id = ?", (pid,))
    row = cur.fetchone()
    con.close()
    return row[0] if row else None

def latest_payslip_id() -> str | None:
    con = _conn()
    cur = con.execute("SELECT id FROM payslips ORDER BY created_at DESC LIMIT 1")
    row = cur.fetchone()
    con.close()
    return row[0] if row else None

def list_payslips(limit:int=20):
    con = _conn()
    cur = con.execute("SELECT id, created_at FROM payslips ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = [{"id": r[0], "created_at": r[1]} for r in cur.fetchall()]
    con.close()
    return rows
