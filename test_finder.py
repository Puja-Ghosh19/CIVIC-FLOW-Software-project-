# Tool-assisted tests (Claude, Anthropic). Logged in Test Report section 10. Team must review and own them.
import unittest
from ai.service_finder import find_service
from ai.time_prediction import predict_days
from tests.base import AppTestCase

SERVICES = [{"id": 1, "name": "NID Information Correction"}, {"id": 2, "name": "NID Application (New NID)"},
            {"id": 3, "name": "Birth Certificate Correction"}, {"id": 4, "name": "Passport Application"},
            {"id": 5, "name": "Trade License"}]


class FinderUnitTests(unittest.TestCase):
    def test_tc20_new_nid_maps_to_new_nid_service(self):                 # FR-2, EP
        self.assertEqual(find_service("I need a new nid card", SERVICES)["name"], "NID Application (New NID)")

    def test_tc21_nid_correction_maps_to_correction(self):               # FR-2, EP
        self.assertEqual(find_service("I need to correct my NID information.", SERVICES)["name"], "NID Information Correction")

    def test_tc22_passport(self):                                         # FR-2, EP
        self.assertEqual(find_service("I want to apply for a passport", SERVICES)["name"], "Passport Application")

    def test_tc23_birth_certificate(self):                                # FR-2, EP
        self.assertEqual(find_service("my birth certificate has a mistake", SERVICES)["name"], "Birth Certificate Correction")

    def test_tc24_trade_license(self):                                    # FR-2, EP
        self.assertEqual(find_service("I want a trade license for my shop", SERVICES)["name"], "Trade License")

    def test_tc25_lost_certificate_gives_tips(self):                      # FR-2, scenario
        r = find_service("i need a new nid card but lost my ssc hsc certificate", SERVICES)
        self.assertEqual(r["name"], "NID Application (New NID)")
        self.assertTrue(any("duplicate" in t.lower() for t in r["tips"]))

    def test_tc26_unknown_text_still_gives_guidance(self):                # FR-2, negative
        r = find_service("hello", SERVICES)
        self.assertEqual(r["name"], "No direct match found")
        self.assertTrue(r["tips"])

    def test_tc27_empty_text_does_not_crash(self):                        # FR-2, BVA empty input
        r = find_service("", SERVICES)
        self.assertEqual(r["name"], "No direct match found")

    def test_tc28_at_most_five_tips(self):                                # FR-2
        r = find_service("new nid lost ssc fee urgent documents address wrong age 16 abroad", SERVICES)
        self.assertLessEqual(len(r["tips"]), 5)

    def test_tc29_service_id_comes_from_database_rows(self):              # FR-2 regression (no hard-coded ids)
        self.assertEqual(find_service("new nid", SERVICES)["id"], 2)

    def test_tc30_lost_nid_card_is_not_treated_as_new_application(self):  # FR-2
        self.assertEqual(find_service("lost my nid card", SERVICES)["name"], "No direct match found")

    def test_tc31_estimate_boundaries(self):                              # FR-7, BVA
        self.assertEqual(predict_days(15), 15)
        self.assertEqual(predict_days(1), 1)
        self.assertEqual(predict_days(0), 1)
        self.assertEqual(predict_days(-3), 1)


class FinderRouteTests(AppTestCase):
    def test_tc32_finder_page_shows_result_and_tips(self):                # FR-2 integration
        r = self.client.post("/finder", data={"problem": "new nid but lost ssc certificate"})
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Helpful tips", r.data)
        sid = self.service_id("NID Application (New NID)")
        self.assertIn(f"/service/{sid}".encode(), r.data)
