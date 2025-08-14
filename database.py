import sqlite3

DB_NAME = "users.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            subscription_expiry INTEGER,
            tasks_done INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_db_connection():
    return sqlite3.connect(DB_NAME)
