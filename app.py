# ... sab imports same

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "very_secure_random_string")
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs("static", exist_ok=True)

# Razorpay init same
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID") 
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# DB init
DB_NAME = "users.db"
def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            tasks_done INTEGER DEFAULT 0,
            subscription_expiry INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ... clean_old_uploads, save_uploaded_file same

# -------------------------
# Signup & Login
# -------------------------
@app.route("/signup", methods=["GET","POST"])
def signup():
    if request.method=="POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        name = request.form.get("name","").strip()
        if not email or not password:
            flash("Email and Password required","danger")
            return render_template("signup.html")
        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO users (email,password,name) VALUES (?,?,?)",
                         (email, generate_password_hash(password), name))
            conn.commit()
            flash("Signup successful! Please login.","success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered!","danger")
        finally:
            conn.close()
    return render_template("signup.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id,password,name FROM users WHERE email=?",(email,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"]=user["id"]
            session["email"]=email
            session["user_name"]=user["name"]
            flash("Login successful!","success")
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials!","danger")
    return render_template("login.html")

# Logout same
# Plans & Payment same
# Index same
# Highlight route minor fix above
# Download routes safer with filename join
# Static pages same
# Sitemap same
# Run app same
