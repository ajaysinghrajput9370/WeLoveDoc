import sqlite3
import os

# Full path ensure kare taaki server/local dono me sahi kaam kare
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "users.db")

def init_db():
    """Create database and users table if not exists."""
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
    """Return a new database connection."""
    return sqlite3.connect(DB_NAME)
