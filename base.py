"""Shared test setup. Tests run on an in-memory SQLite database, so they need no MySQL/XAMPP.

The app talks to MySQL in production; here db() is swapped for a SQLite adapter with the same
execute()/commit()/close() interface. Schema and seed data mirror init_db() in app.py.
"""
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pymysql  # noqa: F401
except ImportError:  # lets the suite run where the MySQL driver is not installed
    _err = types.SimpleNamespace(IntegrityError=sqlite3.IntegrityError)
    sys.modules["pymysql"] = types.SimpleNamespace(connect=None, err=_err, cursors=types.SimpleNamespace(DictCursor=None))
    sys.modules["pymysql.cursors"] = sys.modules["pymysql"].cursors
import pymysql  # noqa: E402

import app as appmod  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user');
CREATE TABLE services (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT, department TEXT, fee TEXT, processing_time INTEGER DEFAULT 7);
CREATE TABLE requirements (id INTEGER PRIMARY KEY AUTOINCREMENT, service_id INTEGER NOT NULL, document_name TEXT NOT NULL, required INTEGER NOT NULL DEFAULT 1);
CREATE TABLE service_steps (id INTEGER PRIMARY KEY AUTOINCREMENT, service_id INTEGER NOT NULL, step_no INTEGER NOT NULL, step_text TEXT NOT NULL);
CREATE TABLE applications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, service_id INTEGER NOT NULL, reference TEXT NOT NULL UNIQUE, status TEXT NOT NULL, created_at TEXT, estimated_days INTEGER, applicant_name TEXT, phone TEXT, dob TEXT, address TEXT, documents_ready TEXT);
CREATE TABLE notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, message TEXT NOT NULL, created_at TEXT, is_read INTEGER NOT NULL DEFAULT 0);
CREATE TABLE application_documents (id INTEGER PRIMARY KEY AUTOINCREMENT, application_id INTEGER NOT NULL, requirement_id INTEGER, document_name TEXT NOT NULL, original_name TEXT NOT NULL, stored_name TEXT NOT NULL, uploaded_at TEXT);
"""
SERVICES = [
    ("NID Application (New NID)", "New NID guide", "Bangladesh Election Commission", "Check official source", 15),
    ("NID Information Correction", "NID correction guide", "Bangladesh Election Commission", "Official fee varies", 7),
    ("Birth Certificate Correction", "Birth certificate guide", "Birth Registration Authority", "Official fee varies", 10),
    ("Passport Application", "Passport guide", "Passport Office", "Official fee varies", 15),
    ("Trade License", "Trade license guide", "Local Government", "Official fee varies", 7),
]


class SqliteAdapter:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, query, params=None):
        try:
            return self.conn.execute(query, params or ())
        except sqlite3.IntegrityError as e:
            raise pymysql.err.IntegrityError(str(e))

    def executemany(self, query, params):
        return self.conn.executemany(query, params)

    def commit(self):
        self.conn.commit()

    def close(self):
        pass


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.executemany("INSERT INTO services(name,description,department,fee,processing_time) VALUES(?,?,?,?,?)", SERVICES)
        appmod.sync_service_guide(SqliteAdapter(self.conn))
        self.conn.commit()
        self.upload_dir = tempfile.mkdtemp()
        self._saved = (appmod.db, appmod.UPLOAD_DIR)
        appmod.db = lambda: SqliteAdapter(self.conn)
        appmod.UPLOAD_DIR = self.upload_dir
        appmod.app.config.update(TESTING=True)
        self.client = appmod.app.test_client()

    def tearDown(self):
        appmod.db, appmod.UPLOAD_DIR = self._saved
        shutil.rmtree(self.upload_dir, ignore_errors=True)
        self.conn.close()

    # ---- helpers ----
    def add_user(self, name="Rina", email="rina@example.com", password="Passw0rd!", role="user"):
        cur = self.conn.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                                (name, email, generate_password_hash(password), role))
        self.conn.commit()
        return cur.lastrowid

    def login_as(self, client, user_id, role="user", name="Rina"):
        with client.session_transaction() as s:
            s.update(user_id=user_id, role=role, name=name)

    def one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def service_id(self, name):
        return self.one("SELECT id FROM services WHERE name=?", (name,))["id"]

    def valid_form(self, service_name="NID Application (New NID)", skip_docs=(), **over):
        sid = self.service_id(service_name)
        data = {"full_name": "Rina Akter", "phone": "01712345678", "dob": "2000-05-10",
                "address": "House 5, Road 3, Dhaka", "declare": "on"}
        for r in self.conn.execute("SELECT * FROM requirements WHERE service_id=?", (sid,)).fetchall():
            if r["id"] in skip_docs or (not r["required"]):
                continue
            data[f"doc_{r['id']}"] = (io.BytesIO(b"%PDF-1.4 test document"), "proof.pdf")
        data.update(over)
        return sid, data
