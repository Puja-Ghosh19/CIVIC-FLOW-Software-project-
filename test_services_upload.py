# Tool-assisted tests (Claude, Anthropic). Logged in Test Report section 10. Team must review and own them.
import io
import unittest
from werkzeug.datastructures import FileStorage
import app as appmod
from tests.base import AppTestCase


def fs(name, data):
    return FileStorage(stream=io.BytesIO(data), filename=name)


class UploadValidationUnitTests(unittest.TestCase):
    MAX = appmod.MAX_FILE_BYTES

    def test_tc40_valid_pdf_accepted(self):                               # FR-5, EP valid
        self.assertEqual(appmod.check_upload(fs("a.pdf", b"%PDF-1.4 x")), (".pdf", None))

    def test_tc41_valid_png_and_jpg_accepted(self):                       # FR-5, EP valid
        self.assertEqual(appmod.check_upload(fs("a.png", b"\x89PNG0000"))[0], ".png")
        self.assertEqual(appmod.check_upload(fs("a.jpg", b"\xff\xd8\xff\xe0"))[0], ".jpg")

    def test_tc42_exe_rejected(self):                                     # FR-5, EP invalid type
        self.assertIsNotNone(appmod.check_upload(fs("virus.exe", b"MZ0000"))[1])

    def test_tc43_fake_pdf_content_rejected(self):                        # FR-5 / NFR-1 abuse
        self.assertIn("content", appmod.check_upload(fs("a.pdf", b"not a pdf at all"))[1])

    def test_tc44_size_boundary_exactly_5mb_accepted(self):               # FR-5, BVA max
        data = b"%PDF" + b"0" * (self.MAX - 4)
        self.assertIsNone(appmod.check_upload(fs("a.pdf", data))[1])

    def test_tc45_size_boundary_5mb_plus_one_rejected(self):              # FR-5, BVA max+1
        data = b"%PDF" + b"0" * (self.MAX - 3)
        self.assertIsNotNone(appmod.check_upload(fs("a.pdf", data))[1])

    def test_tc46_empty_file_rejected(self):                              # FR-5, BVA min-1
        self.assertIsNotNone(appmod.check_upload(fs("a.pdf", b""))[1])

    def test_tc47_smallest_valid_file_accepted(self):                     # FR-5, BVA min
        self.assertIsNone(appmod.check_upload(fs("a.pdf", b"%PDF"))[1])

    def test_tc48_uppercase_extension_accepted(self):                     # FR-5, EP
        self.assertEqual(appmod.check_upload(fs("SCAN.PDF", b"%PDF-1"))[0], ".pdf")


class ServiceGuideTests(AppTestCase):
    def test_tc50_details_page_lists_documents_and_steps_in_order(self):  # FR-3 / FR-4
        sid = self.service_id("NID Application (New NID)")
        r = self.client.get(f"/service/{sid}")
        self.assertEqual(r.status_code, 200)
        html = r.data.decode()
        self.assertIn("Birth registration certificate", html)
        self.assertIn("REQUIRED", html)
        self.assertIn("IF APPLICABLE", html)
        self.assertLess(html.index("Check eligibility"), html.index("Collect the documents"))

    def test_tc51_unknown_service_returns_404(self):                      # FR-3, negative
        self.assertEqual(self.client.get("/service/9999").status_code, 404)

    def test_tc52_every_builtin_service_has_required_doc_and_steps(self): # FR-3 / FR-4 data check
        for name in appmod.SERVICE_GUIDE:
            sid = self.service_id(name)
            req = self.one("SELECT COUNT(*) n FROM requirements WHERE service_id=? AND required=1", (sid,))["n"]
            steps = self.one("SELECT COUNT(*) n FROM service_steps WHERE service_id=?", (sid,))["n"]
            self.assertGreaterEqual(req, 1, name)
            self.assertGreaterEqual(steps, 3, name)

    def test_tc53_guide_sync_is_idempotent(self):                         # FR-4 regression
        before = self.one("SELECT COUNT(*) n FROM requirements")["n"]
        from tests.base import SqliteAdapter
        appmod.sync_service_guide(SqliteAdapter(self.conn))
        self.assertEqual(self.one("SELECT COUNT(*) n FROM requirements")["n"], before)

    def test_tc54_correction_and_services_pages_load(self):               # FR-4
        for path in ("/", "/services", "/correction", "/finder", "/login", "/register"):
            self.assertEqual(self.client.get(path).status_code, 200, path)
