# Tool-assisted tests (Claude, Anthropic). Logged in Test Report section 10. Team must review and own them.
import os
from tests.base import AppTestCase


class ApplyTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.uid = self.add_user()
        self.login_as(self.client, self.uid)

    def submit(self, **kw):
        sid, data = self.valid_form(**kw)
        return sid, self.client.post(f"/apply/{sid}", data=data, content_type="multipart/form-data")

    def count(self, table):
        return self.one(f"SELECT COUNT(*) n FROM {table}")["n"]

    def test_tc60_apply_requires_login(self):                             # FR-6, negative
        anon = self.client.application.test_client()
        r = anon.get("/apply/1")
        self.assertTrue(r.headers["Location"].endswith("/login"))

    def test_tc61_valid_application_creates_record_and_files(self):       # FR-6 scenario / acceptance
        sid, r = self.submit()
        self.assertEqual(r.status_code, 302)
        self.assertIn("/tracking/CF-", r.headers["Location"])
        app_row = self.one("SELECT * FROM applications")
        self.assertEqual(app_row["status"], "Submitted")
        self.assertEqual(app_row["applicant_name"], "Rina Akter")
        self.assertEqual(app_row["estimated_days"], 15)
        self.assertGreaterEqual(self.count("application_documents"), 4)
        for d in self.conn.execute("SELECT stored_name FROM application_documents").fetchall():
            self.assertTrue(os.path.exists(os.path.join(self.upload_dir, d["stored_name"])))

    def test_tc62_missing_required_document_blocks_submission(self):      # FR-5/FR-6, negative
        sid, data = self.valid_form()
        first_doc = sorted(k for k in data if k.startswith("doc_"))[0]
        del data[first_doc]
        r = self.client.post(f"/apply/{sid}", data=data, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Please upload", r.data)
        self.assertEqual(self.count("applications"), 0)

    def test_tc63_missing_declaration_blocks_submission(self):            # FR-6, negative
        sid, data = self.valid_form()
        del data["declare"]
        r = self.client.post(f"/apply/{sid}", data=data, content_type="multipart/form-data")
        self.assertIn(b"confirmation box", r.data)
        self.assertEqual(self.count("applications"), 0)

    def test_tc64_invalid_phone_rejected(self):                           # FR-6, EP invalid
        sid, data = self.valid_form(phone="abc")
        r = self.client.post(f"/apply/{sid}", data=data, content_type="multipart/form-data")
        self.assertIn(b"valid phone", r.data)
        self.assertEqual(self.count("applications"), 0)

    def test_tc65_future_date_of_birth_rejected(self):                    # FR-6, BVA
        sid, data = self.valid_form(dob="2999-01-01")
        r = self.client.post(f"/apply/{sid}", data=data, content_type="multipart/form-data")
        self.assertIn(b"valid date of birth", r.data)

    def test_tc66_name_length_boundary(self):                             # FR-6, BVA 2 vs 3
        sid, data = self.valid_form(full_name="Al")
        r = self.client.post(f"/apply/{sid}", data=data, content_type="multipart/form-data")
        self.assertIn(b"full name", r.data)
        self.assertEqual(self.count("applications"), 0)
        sid, data = self.valid_form(full_name="Ali")
        r = self.client.post(f"/apply/{sid}", data=data, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 302)

    def test_tc67_disallowed_file_type_rejected(self):                    # FR-5, negative
        import io
        sid, data = self.valid_form()
        key = sorted(k for k in data if k.startswith("doc_"))[0]
        data[key] = (io.BytesIO(b"MZ0000"), "tool.exe")
        r = self.client.post(f"/apply/{sid}", data=data, content_type="multipart/form-data")
        self.assertIn(b"only PDF, JPG or PNG", r.data)
        self.assertEqual(self.count("applications"), 0)

    def test_tc68_optional_documents_may_be_skipped(self):                # FR-6, EP
        sid, r = self.submit()
        self.assertEqual(r.status_code, 302)
        total_docs = self.one("SELECT COUNT(*) n FROM requirements WHERE service_id=?", (sid,))["n"]
        self.assertLess(self.count("application_documents"), total_docs)

    def test_tc69_uploaded_file_name_is_random_and_safe(self):            # NFR-1 (path traversal)
        import io
        sid, data = self.valid_form()
        key = sorted(k for k in data if k.startswith("doc_"))[0]
        data[key] = (io.BytesIO(b"%PDF-1.4 x"), "../../evil.pdf")
        self.client.post(f"/apply/{sid}", data=data, content_type="multipart/form-data")
        for d in self.conn.execute("SELECT stored_name FROM application_documents").fetchall():
            self.assertNotIn("..", d["stored_name"])
            self.assertNotIn("/", d["stored_name"])
        # every saved file sits directly inside the upload folder (nothing escaped it)
        self.assertEqual(len(os.listdir(self.upload_dir)), self.count("application_documents"))

    def test_tc70_notification_created_on_submit(self):                   # FR-8
        self.submit()
        n = self.one("SELECT * FROM notifications")
        self.assertEqual(n["user_id"], self.uid)
        self.assertIn("submitted", n["message"])

    def test_tc71_tracking_page_shows_reference_and_status(self):         # FR-6 acceptance
        self.submit()
        ref = self.one("SELECT reference FROM applications")["reference"]
        r = self.client.get(f"/tracking/{ref}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(ref.encode(), r.data)
        self.assertIn(b"Submitted", r.data)

    def test_tc72_unknown_reference_returns_404(self):                    # FR-6, negative
        self.assertEqual(self.client.get("/tracking/CF-DOESNOTEXIST").status_code, 404)

    def test_tc73_dashboard_lists_own_applications(self):                 # FR-6
        self.submit()
        r = self.client.get("/dashboard")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"NID Application", r.data)


class AdminAndAccessTests(AppTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.add_user(name="Owner", email="owner@example.com")
        self.other = self.add_user(name="Other", email="other@example.com")
        self.admin = self.add_user(name="Admin", email="admin@civicflow.com", role="admin")
        self.owner_client = self.client
        self.login_as(self.owner_client, self.owner, name="Owner")
        sid, data = self.valid_form()
        self.owner_client.post(f"/apply/{sid}", data=data, content_type="multipart/form-data")
        self.app_id = self.one("SELECT id FROM applications")["id"]
        self.doc_id = self.one("SELECT id FROM application_documents ORDER BY id")["id"]

    def client_for(self, uid, role="user"):
        c = self.client.application.test_client()
        self.login_as(c, uid, role=role)
        return c

    def test_tc80_owner_can_open_own_document(self):                      # NFR-1
        r = self.owner_client.get(f"/files/{self.doc_id}")
        r.close()
        self.assertEqual(r.status_code, 200)

    def test_tc81_other_user_cannot_open_document(self):                  # NFR-1 access control
        self.assertEqual(self.client_for(self.other).get(f"/files/{self.doc_id}").status_code, 403)

    def test_tc82_admin_can_open_document(self):                          # NFR-1 / FR-9
        r = self.client_for(self.admin, "admin").get(f"/files/{self.doc_id}")
        r.close()
        self.assertEqual(r.status_code, 200)

    def test_tc83_anonymous_cannot_open_document(self):                   # NFR-1
        r = self.client.application.test_client().get(f"/files/{self.doc_id}")
        self.assertTrue(r.headers["Location"].endswith("/login"))

    def test_tc84_unknown_document_returns_404(self):                     # NFR-1
        self.assertEqual(self.client_for(self.admin, "admin").get("/files/99999").status_code, 404)

    def test_tc85_admin_adds_service(self):                               # FR-9
        c = self.client_for(self.admin, "admin")
        c.post("/admin", data={"action": "add", "name": "Land Mutation", "description": "d",
                               "department": "Land Office", "fee": "varies", "days": "20"})
        self.assertEqual(self.one("SELECT processing_time FROM services WHERE name='Land Mutation'")["processing_time"], 20)

    def test_tc86_admin_updates_status_and_user_is_notified(self):        # FR-9 / FR-8
        c = self.client_for(self.admin, "admin")
        c.post("/admin", data={"action": "status", "app_id": str(self.app_id), "status": "Approved"})
        self.assertEqual(self.one("SELECT status FROM applications")["status"], "Approved")
        msgs = [n["message"] for n in self.conn.execute("SELECT message FROM notifications").fetchall()]
        self.assertTrue(any("Approved" in m for m in msgs))

    def test_tc87_admin_can_view_application_documents(self):             # FR-9
        r = self.client_for(self.admin, "admin").get(f"/admin/application/{self.app_id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Uploaded documents", r.data)

    def test_tc88_normal_user_cannot_view_admin_application(self):        # NFR-1 RBAC
        r = self.client_for(self.other).get(f"/admin/application/{self.app_id}")
        self.assertTrue(r.headers["Location"].endswith("/login"))

    def test_tc89_normal_user_cannot_post_to_admin(self):                 # NFR-1 RBAC
        c = self.client_for(self.other)
        c.post("/admin", data={"action": "add", "name": "Hack", "description": "d", "department": "x", "fee": "0", "days": "1"})
        self.assertIsNone(self.one("SELECT id FROM services WHERE name='Hack'"))
