import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = "welovedoc.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DB_PATH):
        conn = get_db_connection()
        cursor = conn.cursor()
        # Users table
        cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            subscription TEXT,
            devices INTEGER DEFAULT 1,
            tasks_done INTEGER DEFAULT 0
        )
        """)
        # Referrals table
        cursor.execute("""
        CREATE TABLE referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referee_email TEXT,
            bonus_days INTEGER,
            FOREIGN KEY(referrer_id) REFERENCES users(id)
        )
        """)
        # Payments table
        cursor.execute("""
        CREATE TABLE payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            razorpay_order_id TEXT,
            razorpay_payment_id TEXT,
            amount INTEGER,
            status TEXT,
            created_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)
        conn.commit()
        conn.close()

# User functions
def add_user(name, email, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    hashed = generate_password_hash(password)
    cursor.execute("INSERT INTO users (name,email,password) VALUES (?,?,?)",
                   (name,email,hashed))
    conn.commit()
    conn.close()

def validate_user(email, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    if user and check_password_hash(user["password"], password):
        return user
    return None

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return user
