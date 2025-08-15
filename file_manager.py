from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from database import get_db_connection, month_key_now
from config import Config

REFERRAL_BONUS = {
    "monthly": 5,
    "6month": 10,
    "12month": 30
}

def create_user(name, email, password):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO users(name, email, password_hash, created_at) VALUES(?,?,?,?)",
                (name, email, generate_password_hash(password), datetime.utcnow().isoformat()))
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid

def get_user_by_email(email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    conn.close()
    return row

def verify_password(row, password):
    return check_password_hash(row["password_hash"], password)

def record_task(user_id=None, session_id=None):
    conn = get_db_connection()
    cur = conn.cursor()
    mk = month_key_now()
    if user_id:
        cur.execute("SELECT * FROM tasks WHERE user_id=? AND month_key=?", (user_id, mk))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE tasks SET count=count+1 WHERE id=?", (row["id"],))
        else:
            cur.execute("INSERT INTO tasks(user_id, session_id, month_key, count) VALUES(?,?,?,?)",
                        (user_id, None, mk, 1))
    else:
        cur.execute("SELECT * FROM tasks WHERE session_id=? AND month_key=?", (session_id, mk))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE tasks SET count=count+1 WHERE id=?", (row["id"],))
        else:
            cur.execute("INSERT INTO tasks(user_id, session_id, month_key, count) VALUES(?,?,?,?)",
                        (None, session_id, mk, 1))
    conn.commit()
    conn.close()

def get_task_count(user_id=None, session_id=None):
    conn = get_db_connection()
    cur = conn.cursor()
    mk = month_key_now()
    if user_id:
        cur.execute("SELECT count FROM tasks WHERE user_id=? AND month_key=?", (user_id, mk))
    else:
        cur.execute("SELECT count FROM tasks WHERE session_id=? AND month_key=?", (session_id, mk))
    row = cur.fetchone()
    conn.close()
    return row["count"] if row else 0

def active_subscription(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    today = datetime.utcnow().date().isoformat()
    cur.execute("SELECT * FROM subscriptions WHERE user_id=? AND end_date>=? ORDER BY end_date DESC LIMIT 1",
                (user_id, today))
    row = cur.fetchone()
    conn.close()
    return row

def start_subscription(user_id, plan):
    devices_allowed = {
        "monthly": Config.DEVICES_MONTHLY,
        "6month": Config.DEVICES_6MONTH,
        "12month": Config.DEVICES_12MONTH
    }.get(plan, 1)

    duration_days = {
        "monthly": 30,
        "6month": 180,
        "12month": 365
    }[plan]
    start = datetime.utcnow().date()
    end = start + timedelta(days=duration_days)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""INSERT INTO subscriptions(user_id, plan, start_date, end_date, devices_allowed)
                   VALUES(?,?,?,?,?)""",
                (user_id, plan, start.isoformat(), end.isoformat(), devices_allowed))
    conn.commit()
    conn.close()

def add_device_if_allowed(user_id, fingerprint):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM devices WHERE user_id=?", (user_id,))
    used = cur.fetchone()["c"]
    sub = active_subscription(user_id)
    allowed = sub["devices_allowed"] if sub else 0
    if used >= allowed:
        conn.close()
        return False
    try:
        cur.execute("INSERT INTO devices(user_id, device_fingerprint, created_at) VALUES(?,?,?)",
                    (user_id, fingerprint, datetime.utcnow().isoformat()))
        conn.commit()
        ok = True
    except Exception:
        ok = True  # already exists is okay
    conn.close()
    return ok

def credit_referral(referrer_id, plan):
    bonus = REFERRAL_BONUS.get(plan, 0)
    if not bonus:
        return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""INSERT INTO referrals(referrer_id, referee_email, plan, bonus_days, created_at)
                   VALUES(?,?,?,?,?)""", (referrer_id, None, plan, bonus, datetime.utcnow().isoformat()))
    sub = active_subscription(referrer_id)
    if sub:
        from datetime import datetime, timedelta
        end = datetime.fromisoformat(sub["end_date"]) + timedelta(days=bonus)
        cur.execute("UPDATE subscriptions SET end_date=? WHERE id=?", (end.date().isoformat(), sub["id"]))
    conn.commit()
    conn.close()
