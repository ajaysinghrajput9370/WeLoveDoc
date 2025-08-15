import hashlib
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db, month_key

# ---------- Users ----------

def create_user(email: str, password: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email, generate_password_hash(password), datetime.utcnow().isoformat()),
        )
        conn.commit()


def get_user_by_email(email: str):
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM users WHERE email=?", (email,))
        return cur.fetchone()


def verify_user(email: str, password: str):
    user = get_user_by_email(email)
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None

# ---------- Subscription ----------

def set_subscription(user_id: int, plan: str, days: int):
    expiry = (datetime.utcnow() + timedelta(days=days)).isoformat()
    with get_db() as conn:
        # upsert
        cur = conn.execute("SELECT id FROM subscriptions WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if row:
            conn.execute("UPDATE subscriptions SET plan=?, expiry=? WHERE user_id=?", (plan, expiry, user_id))
        else:
            conn.execute("INSERT INTO subscriptions (user_id, plan, expiry) VALUES (?, ?, ?)", (user_id, plan, expiry))
        conn.commit()


def get_subscription(user_id: int):
    with get_db() as conn:
        cur = conn.execute("SELECT * FROM subscriptions WHERE user_id=?", (user_id,))
        return cur.fetchone()


def is_subscribed(user_id: int) -> tuple[bool, str|None]:
    sub = get_subscription(user_id)
    if not sub:
        return False, None
    try:
        expiry = datetime.fromisoformat(sub["expiry"])
    except Exception:
        return False, None
    return expiry > datetime.utcnow(), expiry.strftime("%d %b %Y")

# ---------- Task usage (2 free tasks/month for guests & non-subscribed) ----------

def session_key_from(flask_session) -> str:
    # robust session key usable for guests
    raw = str(flask_session.get("session_id"))
    if not raw or raw == "None":
        raw = os.urandom(16).hex()
        flask_session["session_id"] = raw
    return hashlib.sha256(raw.encode()).hexdigest()


def get_task_count(user_id: int|None, session_key: str, mkey: str) -> int:
    with get_db() as conn:
        if user_id:
            cur = conn.execute("SELECT count FROM tasks WHERE user_id=? AND month_key=?", (user_id, mkey))
        else:
            cur = conn.execute("SELECT count FROM tasks WHERE session_key=? AND month_key=?", (session_key, mkey))
        row = cur.fetchone()
        return int(row["count"]) if row else 0


def inc_task_count(user_id: int|None, session_key: str, mkey: str, ip: str):
    with get_db() as conn:
        if user_id:
            cur = conn.execute("SELECT id, count FROM tasks WHERE user_id=? AND month_key=?", (user_id, mkey))
        else:
            cur = conn.execute("SELECT id, count FROM tasks WHERE session_key=? AND month_key=?", (session_key, mkey))
        row = cur.fetchone()
        if row:
            conn.execute("UPDATE tasks SET count=? WHERE id=?", (int(row["count"]) + 1, row["id"]))
        else:
            conn.execute(
                "INSERT INTO tasks (user_id, session_key, month_key, count, ip) VALUES (?, ?, ?, ?, ?)",
                (user_id, session_key, mkey, 1, ip),
            )
        conn.commit()
