"""
Integration tests for the Personal Finance Coach API.

Each test runs against an isolated temporary database.
The FastAPI TestClient is created fresh per test to ensure the correct
DATABASE_URL environment variable is in effect.
"""
import unittest
import os
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = ":memory:"


class TestIntegration(unittest.TestCase):
    def setUp(self):
        """Set up a fresh test database and TestClient for each test."""
        self.db_path = "test_integration.db"
        os.environ["DATABASE_URL"] = self.db_path

        from db import init_db
        init_db()

        from main import app
        self.client = TestClient(app)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.environ.pop("ENABLE_RESET", None)
        os.environ.pop("ENVIRONMENT", None)

    # ------------------------------------------------------------------ #
    # Health
    # ------------------------------------------------------------------ #
    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    # ------------------------------------------------------------------ #
    # Ingestion
    # ------------------------------------------------------------------ #
    def test_ingest_sample_and_retrieve(self):
        resp = self.client.post("/ingest/sample")
        self.assertEqual(resp.status_code, 200)
        count = resp.json().get("transactions_count")
        self.assertGreater(count, 0)

        resp = self.client.get("/transactions")
        self.assertEqual(resp.status_code, 200)
        txs = resp.json()
        self.assertGreater(len(txs), 0)
        self.assertIn("description", txs[0])

    def test_duplicate_ingestion(self):
        self.client.post("/ingest/sample")
        resp = self.client.post("/ingest/sample")
        self.assertEqual(resp.json().get("transactions_count"), 0)

    def test_ingest_sms(self):
        payload = {"text": "A/c XX1234 debited for Rs 500.00 on 2026-10-20 via UPI to Swiggy"}
        resp = self.client.post("/ingest/sms", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.json().get("detected_amount"))

    def test_ingest_sms_invalid(self):
        resp = self.client.post("/ingest/sms", json={"text": "not a bank sms at all"})
        self.assertEqual(resp.status_code, 400)

    def test_ingest_csv_file(self):
        csv_content = b"Date,Description,Amount,Category,Merchant\n2026-10-01,Test,100.0,Food,Test\n"
        resp = self.client.post(
            "/ingest/file",
            files={"file": ("test.csv", csv_content, "text/csv")},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(resp.json().get("transactions_count", 0), 0)

    def test_ingest_oversized_file(self):
        oversized = b"Date,Description,Amount,Category,Merchant\n" + b"X" * (10 * 1024 * 1024 + 1024)
        resp = self.client.post(
            "/ingest/file",
            files={"file": ("oversized.csv", oversized, "text/csv")},
        )
        self.assertEqual(resp.status_code, 413)
        self.assertIn("File too large", resp.json()["detail"])

    def test_ingest_unsupported_filetype(self):
        resp = self.client.post(
            "/ingest/file",
            files={"file": ("test.xyz", b"data", "application/octet-stream")},
        )
        self.assertEqual(resp.status_code, 400)

    # ------------------------------------------------------------------ #
    # Transactions
    # ------------------------------------------------------------------ #
    def test_transactions_filter_by_month(self):
        self.client.post("/ingest/sample")
        resp = self.client.get("/transactions", params={"month": "2026-10"})
        self.assertEqual(resp.status_code, 200)
        txs = resp.json()
        for tx in txs:
            self.assertTrue(tx["date"].startswith("2026-10"))

    def test_category_update(self):
        from services.db_service import DBService
        tx = {
            "date": "2026-10-01", "description": "Test", "amount": -100.0,
            "category": "Uncategorized", "merchant": "TestMerch",
            "source": "test", "hash": "uniq_hash_cat_test",
        }
        tx_id = DBService.add_transaction(tx)
        resp = self.client.patch(f"/transactions/{tx_id}/category", json={"category": "Food"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("rule", resp.json())

    def test_category_update_not_found(self):
        resp = self.client.patch("/transactions/99999/category", json={"category": "Food"})
        self.assertEqual(resp.status_code, 404)

    # ------------------------------------------------------------------ #
    # Profile
    # ------------------------------------------------------------------ #
    def test_profile_get_default(self):
        resp = self.client.get("/profile")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("user_id", data)
        self.assertEqual(data["currency"], "INR")

    def test_profile_update_and_retrieve(self):
        update_data = {"monthly_budget": 60000.0}
        resp = self.client.put("/profile", json=update_data)
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/profile")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["monthly_budget"], 60000.0)

    def test_profile_update_invalid_field(self):
        resp = self.client.put("/profile", json={"hacked_field": "bad"})
        self.assertEqual(resp.status_code, 400)

    # ------------------------------------------------------------------ #
    # Goals
    # ------------------------------------------------------------------ #
    def test_goal_lifecycle(self):
        goal_data = {
            "name": "New Car", "target_amount": 10000.0,
            "current_amount": 0.0, "deadline": "2026-12-31",
        }
        resp = self.client.post("/goals", json=goal_data)
        self.assertEqual(resp.status_code, 201)
        goal_id = resp.json()["id"]

        resp = self.client.put(f"/goals/{goal_id}", json={"current_amount": 1000.0})
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/goals")
        self.assertEqual(resp.status_code, 200)
        goals = resp.json()
        goal = next(g for g in goals if g["id"] == goal_id)
        self.assertEqual(goal["current_amount"], 1000.0)

        resp = self.client.delete(f"/goals/{goal_id}")
        self.assertEqual(resp.status_code, 200)

        resp = self.client.get("/goals")
        self.assertFalse(any(g["id"] == goal_id for g in resp.json()))

    # ------------------------------------------------------------------ #
    # Rules
    # ------------------------------------------------------------------ #
    def test_rules(self):
        resp = self.client.get("/rules")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_delete_nonexistent_rule(self):
        resp = self.client.delete("/rules/99999")
        self.assertEqual(resp.status_code, 200)

    # ------------------------------------------------------------------ #
    # What-If
    # ------------------------------------------------------------------ #
    def test_whatif_simulation(self):
        self.client.post("/ingest/sample")
        payload = {"changes": {"Food": -0.30}}
        resp = self.client.post("/whatif", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("projected_savings", data)
        self.assertIn("impact_summary", data)

    def test_whatif_presets(self):
        resp = self.client.get("/presets")
        self.assertEqual(resp.status_code, 200)
        presets = resp.json()
        self.assertGreater(len(presets), 0)
        self.assertIn("name", presets[0])

    def test_whatif_preset_apply(self):
        self.client.post("/ingest/sample")
        resp = self.client.post("/presets/Minimalist/apply")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("projected_savings", resp.json())

    # ------------------------------------------------------------------ #
    # Coach
    # ------------------------------------------------------------------ #
    def test_coach_chat(self):
        self.client.post("/ingest/sample")
        payload = {"message": "Can I afford a new phone?"}
        resp = self.client.post("/coach/chat", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("reply", data)
        self.assertIn("intent", data)

    def test_coach_spending_analysis(self):
        self.client.post("/ingest/sample")
        resp = self.client.post("/coach/chat", json={"message": "Analyze my spending"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["intent"], "spending_analysis")

    # ------------------------------------------------------------------ #
    # Subscriptions
    # ------------------------------------------------------------------ #
    def test_subscriptions(self):
        self.client.post("/ingest/sample")
        resp = self.client.get("/subscriptions")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_subscription_unused_flag(self):
        self.client.post("/ingest/sample")
        subs = self.client.get("/subscriptions").json()
        if subs:
            merchant = subs[0]["merchant"]
            resp = self.client.post(
                f"/subscriptions/{merchant}/unused",
                json={"unused": True},
            )
            self.assertEqual(resp.status_code, 200)

    # ------------------------------------------------------------------ #
    # Dashboard & Nudges
    # ------------------------------------------------------------------ #
    def test_dashboard(self):
        resp = self.client.get("/dashboard")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("runway", data)
        self.assertIn("category_totals", data)
        self.assertIn("top_nudges", data)

    def test_nudges(self):
        resp = self.client.get("/nudges")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #
    def test_monthly_report(self):
        self.client.post("/ingest/sample")
        resp = self.client.get("/report/monthly", params={"month": "2026-10"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("total_spent", data)
        self.assertIn("savings_rate", data)

    def test_invalid_month_report(self):
        resp = self.client.get("/report/monthly", params={"month": "invalid-month"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Invalid month format", resp.json()["detail"])

    # ------------------------------------------------------------------ #
    # Guardrail log
    # ------------------------------------------------------------------ #
    def test_guardrail_log(self):
        resp = self.client.get("/guardrail/log")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    # ------------------------------------------------------------------ #
    # Reset
    # ------------------------------------------------------------------ #
    def test_reset_disabled_by_default(self):
        os.environ.pop("ENABLE_RESET", None)
        os.environ.pop("ENVIRONMENT", None)
        resp = self.client.post("/reset")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Reset endpoint is disabled", resp.json()["detail"])

    def test_reset_disabled_in_production(self):
        os.environ["ENABLE_RESET"] = "true"
        os.environ["ENVIRONMENT"] = "production"
        resp = self.client.post("/reset")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Reset endpoint is disabled", resp.json()["detail"])

    def test_reset_enabled_in_development(self):
        os.environ["ENABLE_RESET"] = "true"
        os.environ["ENVIRONMENT"] = "development"
        self.client.post("/ingest/sample")
        resp = self.client.post("/reset")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"message": "Data reset successfully"})
        resp = self.client.get("/transactions")
        self.assertEqual(len(resp.json()), 0)


if __name__ == "__main__":
    unittest.main()
