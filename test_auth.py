# Tool-assisted tests (Claude, Anthropic). Logged in Test Report section 10. Team must review and own them.
from tests.base import AppTestCase
import app as appmod


class AuthTests(AppTestCase):
    def post_register(self, **over):
        d = {"name": "Rina", "email": "rina@example.com", "password": "Passw0rd!"}
        d.update(over)
        return self.client.post("/register", data=d)

    def test_tc01_register_valid_user_redirects_to_login(self):          # FR-1, EP valid
        r = self.post_register()
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/login"))
        self.assertIsNotNone(self.one("SELECT id FROM users WHERE email=?", ("rina@example.com",)))

    def test_tc02_password_is_stored_hashed_not_plain(self):             # FR-1 / NFR-1
        self.post_register()
        stored = self.one("SELECT password FROM users WHERE email=?", ("rina@example.com",))["password"]
        self.assertNotEqual(stored, "Passw0rd!")
        self.assertTrue(stored.startswith(("scrypt:", "pbkdf2:")))

    def test_tc03_duplicate_email_is_rejected(self):                      # FR-1, EP invalid
        self.post_register()
        r = self.post_register()
        self.assertEqual(self.one("SELECT COUNT(*) n FROM users")["n"], 1)
        self.assertIn(b"Email already registered", r.data)

    def test_tc04_valid_login_goes_to_dashboard(self):                    # FR-1
        self.add_user()
        r = self.client.post("/login", data={"email": "rina@example.com", "password": "Passw0rd!"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/dashboard"))
        with self.client.session_transaction() as s:
            self.assertIn("user_id", s)

    def test_tc05_wrong_password_is_rejected(self):                       # FR-1, EP invalid
        self.add_user()
        r = self.client.post("/login", data={"email": "rina@example.com", "password": "wrong"})
        self.assertIn(b"Invalid email or password", r.data)
        with self.client.session_transaction() as s:
            self.assertNotIn("user_id", s)

    def test_tc06_unknown_email_is_rejected(self):                        # FR-1, EP invalid
        r = self.client.post("/login", data={"email": "nobody@example.com", "password": "x"})
        self.assertIn(b"Invalid email or password", r.data)

    def test_tc07_admin_login_goes_to_admin_page(self):                   # FR-1 / FR-9, RBAC
        self.add_user(name="Admin", email="admin@civicflow.com", password="admin123", role="admin")
        r = self.client.post("/login", data={"email": "admin@civicflow.com", "password": "admin123"})
        self.assertTrue(r.headers["Location"].endswith("/admin"))

    def test_tc08_old_plain_text_password_is_upgraded_to_hash(self):      # FR-1 regression
        self.conn.execute("INSERT INTO users(name,email,password,role) VALUES('Old','old@example.com','plain123','user')")
        self.conn.commit()
        r = self.client.post("/login", data={"email": "old@example.com", "password": "plain123"})
        self.assertEqual(r.status_code, 302)
        stored = self.one("SELECT password FROM users WHERE email='old@example.com'")["password"]
        self.assertTrue(stored.startswith(("scrypt:", "pbkdf2:")))

    def test_tc09_logout_clears_session(self):                            # FR-1
        uid = self.add_user()
        self.login_as(self.client, uid)
        self.client.get("/logout")
        with self.client.session_transaction() as s:
            self.assertNotIn("user_id", s)

    def test_tc10_dashboard_requires_login(self):                         # FR-1, negative
        r = self.client.get("/dashboard")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/login"))

    def test_tc11_normal_user_cannot_open_admin_page(self):               # NFR-1 RBAC
        uid = self.add_user()
        self.login_as(self.client, uid, role="user")
        r = self.client.get("/admin")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/login"))

    def test_tc12_sql_injection_in_login_does_not_log_in(self):           # NFR-1 abuse case
        self.add_user()
        r = self.client.post("/login", data={"email": "' OR '1'='1", "password": "' OR '1'='1"})
        self.assertIn(b"Invalid email or password", r.data)
        with self.client.session_transaction() as s:
            self.assertNotIn("user_id", s)

    def test_tc13_password_check_helper(self):                            # FR-1 unit
        ok, legacy = appmod.password_ok("secret", "secret")
        self.assertTrue(ok and legacy)
        ok, _ = appmod.password_ok("secret", "other")
        self.assertFalse(ok)
