from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, abort
import os
import uuid
import re
import hmac
import pymysql
from werkzeug.security import generate_password_hash, check_password_hash
from pymysql.cursors import DictCursor
from datetime import datetime
from ai.service_finder import find_service
from ai.time_prediction import predict_days

app = Flask(__name__)
app.secret_key = os.getenv("CIVIC_FLOW_SECRET_KEY", "change-this-demo-key")

# Uploaded documents are stored here (outside static/, so they are never public).
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_FILE_BYTES = 5 * 1024 * 1024           # 5 MB per document
app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024
ALLOWED_TYPES = {".pdf": b"%PDF", ".jpg": b"\xff\xd8", ".jpeg": b"\xff\xd8", ".png": b"\x89PNG"}


def check_upload(f):
    """Return (ext, error). Checks file type, real file signature and size."""
    ext = os.path.splitext(f.filename or "")[1].lower()
    if ext not in ALLOWED_TYPES:
        return None, "only PDF, JPG or PNG files are allowed"
    head = f.stream.read(8)
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    if not head.startswith(ALLOWED_TYPES[ext]):
        return None, "the file content does not match its type"
    if size == 0 or size > MAX_FILE_BYTES:
        return None, "file must be between 1 byte and 5 MB"
    return ext, None

# Set these values to match the MySQL connection on your computer.
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "civic_flow"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
    "autocommit": False,
}

class DatabaseConnection:
    """Small adapter so the app's parameterized queries work with MySQL."""
    def __init__(self):
        self.connection = pymysql.connect(**DB_CONFIG)

    def execute(self, query, params=None):
        cursor = self.connection.cursor()
        cursor.execute(query.replace("?", "%s"), params or ())
        return cursor

    def executemany(self, query, params):
        cursor = self.connection.cursor()
        cursor.executemany(query.replace("?", "%s"), params)
        return cursor

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()


def db():
    """Open a connection to the separate MySQL database."""
    return DatabaseConnection()


# Real checklist data for every built-in service. Each document is (name, required).
SERVICE_GUIDE = {
    "NID Application (New NID)": {
        "docs": [
            ("Birth registration certificate (online copy with 17-digit number)", 1),
            ("SSC / equivalent certificate or marksheet (if you have one)", 0),
            ("Father's and mother's NID card copies", 1),
            ("Citizenship certificate from Union Parishad chairman or ward/city councillor", 1),
            ("Proof of present and permanent address (utility bill, holding tax receipt or rent agreement)", 1),
            ("Spouse's NID card copy (only if married)", 0),
        ],
        "steps": [
            "Check eligibility: you must be a Bangladeshi citizen aged 16 or above (confirm the current age rule with the Election Commission).",
            "Collect the documents listed above (originals and photocopies).",
            "Get your citizenship certificate from your Union Parishad chairman or ward/city councillor.",
            "Fill in the registration form online at the NID Wing website (nidw.gov.bd) or get it from your Upazila/Thana Election Office.",
            "Visit your Upazila/Thana Election Office with the documents for biometric enrolment (fingerprints, photo, signature).",
            "Keep the enrolment slip. After verification your smart NID card can be downloaded or collected.",
        ],
    },
    "NID Information Correction": {
        "docs": [
            ("Existing NID card copy", 1),
            ("Document that proves the correct information (SSC certificate, passport or birth certificate)", 1),
            ("Parents' NID card copies", 0),
            ("Correction application form / online application summary", 1),
            ("Fee payment receipt (official fee)", 1),
        ],
        "steps": [
            "Find exactly which information on your NID is wrong (name, date of birth, parents' names, address).",
            "Collect an official document that proves the correct information.",
            "Apply for correction through the NID Wing online service (nidw.gov.bd) and upload your documents.",
            "Pay the official correction fee and keep the receipt.",
            "Visit your Upazila/Thana Election Office if you are called for verification.",
            "Wait for the update and download your corrected NID.",
        ],
    },
    "Birth Certificate Correction": {
        "docs": [
            ("Existing birth registration certificate", 1),
            ("Parents' NID card copies", 1),
            ("Document showing the correct information (SSC certificate, school record or vaccination card)", 1),
            ("Correction application printed from the birth registration website (bdris.gov.bd)", 1),
            ("Affidavit or notice, only if the Registrar asks for it", 0),
        ],
        "steps": [
            "Note exactly what is wrong on the birth certificate.",
            "Apply for correction online on the birth registration website (bdris.gov.bd).",
            "Print the application and attach the documents listed above.",
            "Submit it to the Registrar's office (Union Parishad, Pourashava or City Corporation) that issued the certificate.",
            "Pay the official fee if required and keep the receipt.",
            "Collect the corrected certificate once it is approved.",
        ],
    },
    "Passport Application": {
        "docs": [
            ("NID card copy (or birth registration certificate if you have no NID)", 1),
            ("Online application form and summary printout", 1),
            ("Passport fee payment receipt (bank or approved payment channel)", 1),
            ("Previous passport (only for renewal or reissue)", 0),
            ("No-objection certificate from employer (only for government employees)", 0),
        ],
        "steps": [
            "Fill in the online application at epassport.gov.bd and choose the passport type and delivery speed.",
            "Print the application summary.",
            "Pay the passport fee through the allowed payment channel and keep the receipt.",
            "Visit your chosen passport office on your appointment date with original documents for biometric enrolment.",
            "Complete police verification if it is required.",
            "Collect your passport when it is ready.",
        ],
    },
    "Trade License": {
        "docs": [
            ("NID card copy of the owner", 1),
            ("Passport-size photograph of the owner", 1),
            ("Proof of business premises (rent agreement, ownership deed or holding tax receipt)", 1),
            ("Business name, type and address details (application form from the local authority)", 1),
            ("TIN certificate (if you have one)", 0),
            ("Previous trade license (only for renewal)", 0),
        ],
        "steps": [
            "Decide your business name, type and address.",
            "Get the application form from your City Corporation, Pourashava or Union Parishad (some offer it online).",
            "Fill in the form and attach the documents listed above.",
            "Pay the license fee and any related tax, and keep the receipt.",
            "Allow an inspection if the authority asks for one.",
            "Collect your trade license.",
        ],
    },
}
FOOTNOTE = "Official rules can change. Always confirm the final requirements with the responsible office or its official website."


def column_exists(c, table, column):
    row = c.execute(
        "SELECT COUNT(*) AS n FROM information_schema.columns "
        "WHERE table_schema=DATABASE() AND table_name=? AND column_name=?", (table, column)).fetchone()
    return row["n"] > 0


def sync_service_guide(c):
    """Replace the old generic checklist with the detailed documents and steps (safe to run every start)."""
    for name, guide in SERVICE_GUIDE.items():
        s = c.execute("SELECT id FROM services WHERE name=?", (name,)).fetchone()
        if not s:
            continue
        sid = s["id"]
        first_doc = guide["docs"][0][0]
        if c.execute("SELECT COUNT(*) AS n FROM requirements WHERE service_id=? AND document_name=?", (sid, first_doc)).fetchone()["n"] == 0:
            c.execute("DELETE FROM requirements WHERE service_id=?", (sid,))
            for doc, required in guide["docs"]:
                c.execute("INSERT INTO requirements(service_id,document_name,required) VALUES(?,?,?)", (sid, doc, required))
        first_step = guide["steps"][0]
        if c.execute("SELECT COUNT(*) AS n FROM service_steps WHERE service_id=? AND step_text=?", (sid, first_step)).fetchone()["n"] == 0:
            c.execute("DELETE FROM service_steps WHERE service_id=?", (sid,))
            for number, text in enumerate(guide["steps"], start=1):
                c.execute("INSERT INTO service_steps(service_id,step_no,step_text) VALUES(?,?,?)", (sid, number, text))


def init_db():
    """Create project tables and insert demo data when tables are empty."""
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(120) NOT NULL,
        email VARCHAR(190) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL,
        role VARCHAR(30) NOT NULL DEFAULT 'user'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    c.execute("""CREATE TABLE IF NOT EXISTS services (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        description TEXT,
        department VARCHAR(150),
        fee VARCHAR(100),
        processing_time INT DEFAULT 7
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    c.execute("""CREATE TABLE IF NOT EXISTS requirements (
        id INT AUTO_INCREMENT PRIMARY KEY,
        service_id INT NOT NULL,
        document_name VARCHAR(255) NOT NULL,
        required TINYINT(1) NOT NULL DEFAULT 1,
        FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    c.execute("""CREATE TABLE IF NOT EXISTS service_steps (
        id INT AUTO_INCREMENT PRIMARY KEY,
        service_id INT NOT NULL,
        step_no INT NOT NULL,
        step_text TEXT NOT NULL,
        FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    c.execute("""CREATE TABLE IF NOT EXISTS applications (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        service_id INT NOT NULL,
        reference VARCHAR(40) NOT NULL UNIQUE,
        status VARCHAR(40) NOT NULL,
        created_at VARCHAR(30),
        estimated_days INT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (service_id) REFERENCES services(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    c.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        message TEXT NOT NULL,
        created_at VARCHAR(30),
        is_read TINYINT(1) NOT NULL DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    if c.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"] == 0:
        admin_email = os.getenv("CIVIC_FLOW_ADMIN_EMAIL", "admin@civicflow.com")
        admin_password = os.getenv("CIVIC_FLOW_ADMIN_PASSWORD", "admin123")
        c.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                  ("Admin", admin_email, generate_password_hash(admin_password), "admin"))
    if c.execute("SELECT COUNT(*) AS total FROM services").fetchone()["total"] == 0:
        data = [
            ("NID Application (New NID)", "Prepare a new NID application checklist and track your CIVIC-FLOW request.", "Bangladesh Election Commission", "Check official source", 15),
            ("NID Information Correction", "Guidance for eligible NID information correction.", "Bangladesh Election Commission", "Official fee varies", 7),
            ("Birth Certificate Correction", "Guidance for eligible birth registration correction.", "Birth Registration Authority", "Official fee varies", 10),
            ("Passport Application", "Guidance for passport application.", "Passport Office", "Official fee varies", 15),
            ("Trade License", "Guidance for trade license application.", "Local Government", "Official fee varies", 7),
        ]
        c.executemany("INSERT INTO services(name,description,department,fee,processing_time) VALUES(?,?,?,?,?)", data)
        req = {
            1: ["Birth registration certificate or other officially accepted proof", "Required supporting documents listed by the Election Commission"],
            2: ["Existing National ID Card", "Supporting evidence for the requested correction"],
            3: ["Birth registration record", "Supporting document (if applicable)"],
            4: ["National ID Card (if required)", "Photograph and other documents required by the Passport Office"],
            5: ["National ID Card", "Business-related documents (if applicable)"],
        }
        for sid, docs in req.items():
            for document in docs:
                c.execute("INSERT INTO requirements(service_id,document_name) VALUES(?,?)", (sid, document))
    # Upgrade existing databases too: add the new NID application guide if it is not present.
    existing_nid = c.execute("SELECT id FROM services WHERE name=?", ("NID Application (New NID)",)).fetchone()
    if not existing_nid:
        c.execute("INSERT INTO services(name,description,department,fee,processing_time) VALUES(?,?,?,?,?)",
                  ("NID Application (New NID)", "Prepare a new NID application checklist and track your CIVIC-FLOW request.", "Bangladesh Election Commission", "Check official source", 15))
        nid_service = c.execute("SELECT id FROM services WHERE name=?", ("NID Application (New NID)",)).fetchone()
        for document in ["Birth registration certificate or other officially accepted proof", "Required supporting documents listed by the Election Commission"]:
            c.execute("INSERT INTO requirements(service_id,document_name) VALUES(?,?)", (nid_service["id"], document))
    c.execute("""CREATE TABLE IF NOT EXISTS application_documents (
        id INT AUTO_INCREMENT PRIMARY KEY,
        application_id INT NOT NULL,
        requirement_id INT,
        document_name VARCHAR(255) NOT NULL,
        original_name VARCHAR(255) NOT NULL,
        stored_name VARCHAR(100) NOT NULL,
        uploaded_at VARCHAR(30),
        FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    # Upgrade older databases: store the applicant's details with each application.
    for column, ddl in [("applicant_name", "VARCHAR(150)"), ("phone", "VARCHAR(30)"), ("dob", "VARCHAR(20)"),
                        ("address", "TEXT"), ("documents_ready", "TEXT")]:
        if not column_exists(c, "applications", column):
            c.execute("ALTER TABLE applications ADD COLUMN " + column + " " + ddl)
    sync_service_guide(c)
    c.commit()
    c.close()

@app.route("/")
def index(): return render_template("index.html")

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        try:
            c=db();c.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",(request.form["name"],request.form["email"],generate_password_hash(request.form["password"])));c.commit();c.close()
            flash("Registration successful.");return redirect(url_for("login"))
        except pymysql.err.IntegrityError: flash("Email already registered.")
    return render_template("register.html")

def password_ok(stored, given):
    """Check a password against a stored hash. Old plain-text rows are still accepted once, then upgraded."""
    if stored.startswith(("scrypt:", "pbkdf2:")):
        return check_password_hash(stored, given), False
    return hmac.compare_digest(stored.encode(), given.encode()), True

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        c=db();u=c.execute("SELECT * FROM users WHERE email=?",(request.form["email"],)).fetchone()
        if u:
            ok,legacy=password_ok(u["password"],request.form["password"])
            if ok and legacy:
                c.execute("UPDATE users SET password=? WHERE id=?",(generate_password_hash(request.form["password"]),u["id"]));c.commit()
            if not ok:u=None
        c.close()
        if u:
            session.update(user_id=u["id"],name=u["name"],role=u["role"])
            return redirect(url_for("admin" if u["role"]=="admin" else "dashboard"))
        flash("Invalid email or password.")
    return render_template("login.html")

@app.route("/logout")
def logout(): session.clear();return redirect("/")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:return redirect("/login")
    c=db()
    apps=c.execute("SELECT a.*,s.name service_name FROM applications a JOIN services s ON s.id=a.service_id WHERE a.user_id=? ORDER BY a.id DESC",(session["user_id"],)).fetchall()
    notes=c.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 5",(session["user_id"],)).fetchall()
    c.close();return render_template("dashboard.html",apps=apps,notes=notes)

@app.route("/services")
def services():
    c=db();rows=c.execute("SELECT * FROM services").fetchall();c.close();return render_template("services.html",services=rows)

@app.route("/service/<int:sid>")
def service_details(sid):
    c=db();s=c.execute("SELECT * FROM services WHERE id=?",(sid,)).fetchone();r=c.execute("SELECT * FROM requirements WHERE service_id=? ORDER BY required DESC,id",(sid,)).fetchall();st=c.execute("SELECT * FROM service_steps WHERE service_id=? ORDER BY step_no",(sid,)).fetchall();c.close()
    if not s:return "Service not found",404
    return render_template("service_details.html",service=s,requirements=r,steps=st,footnote=FOOTNOTE)

# The finder currently uses hand-written keyword rules (see ai/service_finder.py).
@app.route("/finder",methods=["GET","POST"])
def finder():
    result=None;rows=[]
    if request.method=="POST":
        c=db();rows=c.execute("SELECT id,name FROM services").fetchall();c.close()
        result=find_service(request.form["problem"],rows)
    return render_template("finder.html",result=result,services=rows)

# This creates an internal CIVIC-FLOW record; it does not submit to a government portal.
@app.errorhandler(413)
def too_large(e):
    flash("Your files are too large. Each document must be 5 MB or smaller.")
    return redirect(request.url)

@app.route("/apply/<int:sid>",methods=["GET","POST"])
def apply(sid):
    if "user_id" not in session:return redirect("/login")
    c=db();s=c.execute("SELECT * FROM services WHERE id=?",(sid,)).fetchone()
    reqs=c.execute("SELECT * FROM requirements WHERE service_id=? ORDER BY required DESC,id",(sid,)).fetchall();c.close()
    if not s:return "Service not found",404
    form={};errors=[]
    if request.method=="POST":
        form=request.form
        name=form.get("full_name","").strip();phone=form.get("phone","").strip();dob=form.get("dob","").strip();address=form.get("address","").strip()
        if len(name)<3:errors.append("Please enter your full name.")
        if not re.fullmatch(r"[0-9+\-\s]{7,20}",phone):errors.append("Please enter a valid phone number.")
        try:
            born=datetime.strptime(dob,"%Y-%m-%d")
            if born>datetime.now() or born.year<1900:errors.append("Please enter a valid date of birth.")
        except ValueError:errors.append("Please enter your date of birth.")
        if len(address)<5:errors.append("Please enter your address.")
        uploads=[]  # (requirement, file, ext)
        for r in reqs:
            f=request.files.get(f"doc_{r['id']}")
            has=bool(f and f.filename)
            if not has:
                if r["required"]:errors.append(f"Please upload: {r['document_name']}")
                continue
            ext,err=check_upload(f)
            if err:errors.append(f"{r['document_name']}: {err}.")
            else:uploads.append((r,f,ext))
        if not form.get("declare"):errors.append("Please tick the confirmation box to continue.")
        if not errors:
            ready=", ".join(r["document_name"] for r,_,_ in uploads)
            ref="CF-"+uuid.uuid4().hex[:8].upper();days=predict_days(s["processing_time"]);now=datetime.now().strftime("%Y-%m-%d %H:%M")
            c=db();cur=c.execute("INSERT INTO applications(user_id,service_id,reference,status,created_at,estimated_days,applicant_name,phone,dob,address,documents_ready) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(session["user_id"],sid,ref,"Submitted",now,days,name,phone,dob,address,ready))
            app_id=cur.lastrowid
            for r,f,ext in uploads:
                stored=uuid.uuid4().hex+ext
                f.save(os.path.join(UPLOAD_DIR,stored))
                c.execute("INSERT INTO application_documents(application_id,requirement_id,document_name,original_name,stored_name,uploaded_at) VALUES(?,?,?,?,?,?)",(app_id,r["id"],r["document_name"],os.path.basename(f.filename)[:250],stored,now))
            c.execute("INSERT INTO notifications(user_id,message,created_at) VALUES(?,?,?)",(session["user_id"],f"Application {ref} submitted with {len(uploads)} document(s).",now));c.commit();c.close()
            return redirect(url_for("tracking",reference=ref))
    return render_template("application.html",service=s,requirements=reqs,form=form,errors=errors)

# Only the owner of an application or an admin can open its uploaded documents.
@app.route("/files/<int:doc_id>")
def download_document(doc_id):
    if "user_id" not in session:return redirect("/login")
    c=db();d=c.execute("SELECT d.*,a.user_id FROM application_documents d JOIN applications a ON a.id=d.application_id WHERE d.id=?",(doc_id,)).fetchone();c.close()
    if not d:abort(404)
    if session.get("role")!="admin" and d["user_id"]!=session["user_id"]:abort(403)
    return send_from_directory(UPLOAD_DIR,d["stored_name"],download_name=d["original_name"])

@app.route("/admin/application/<int:aid>")
def admin_application(aid):
    if session.get("role")!="admin":return redirect("/login")
    c=db()
    a=c.execute("SELECT a.*,u.name user_name,u.email user_email,s.name service_name FROM applications a JOIN users u ON u.id=a.user_id JOIN services s ON s.id=a.service_id WHERE a.id=?",(aid,)).fetchone()
    docs=c.execute("SELECT * FROM application_documents WHERE application_id=? ORDER BY id",(aid,)).fetchall();c.close()
    if not a:return "Application not found",404
    return render_template("admin_application.html",a=a,docs=docs)

@app.route("/tracking/<reference>")
def tracking(reference):
    c=db();a=c.execute("SELECT a.*,s.name service_name FROM applications a JOIN services s ON s.id=a.service_id WHERE a.reference=?",(reference,)).fetchone();c.close()
    if not a:return "Application not found",404
    return render_template("tracking.html",app=a)

@app.route("/correction")
def correction(): return render_template("correction.html")

@app.route("/admin",methods=["GET","POST"])
def admin():
    if session.get("role")!="admin":return redirect("/login")
    c=db()
    if request.method=="POST":
        if request.form["action"]=="add":
            c.execute("INSERT INTO services(name,description,department,fee,processing_time) VALUES(?,?,?,?,?)",(request.form["name"],request.form["description"],request.form["department"],request.form["fee"],int(request.form["days"])))
        else:
            aid=request.form["app_id"];status=request.form["status"];c.execute("UPDATE applications SET status=? WHERE id=?",(status,aid))
            a=c.execute("SELECT user_id,reference FROM applications WHERE id=?",(aid,)).fetchone()
            c.execute("INSERT INTO notifications(user_id,message,created_at) VALUES(?,?,?)",(a["user_id"],f"Application {a['reference']} status: {status}",datetime.now().strftime("%Y-%m-%d %H:%M")))
        c.commit()
    services=c.execute("SELECT * FROM services").fetchall()
    apps=c.execute("SELECT a.*,u.name user_name,s.name service_name FROM applications a JOIN users u ON u.id=a.user_id JOIN services s ON s.id=a.service_id ORDER BY a.id DESC").fetchall()
    c.close();return render_template("admin.html",services=services,apps=apps)

# For local development only. Use a production server and secure configuration before deployment.
if __name__=="__main__":
    init_db();app.run(debug=True)
