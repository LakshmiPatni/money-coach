import unittest
import os
import sqlite3
from services.db_service import DBService
from services.ingest import IngestionService
from services.categorizer import CategorizerService
from services.sanitizer import PIISanitizer
from db import init_db, get_db_connection

class TestPhase1(unittest.TestCase):
    def setUp(self):
        # Use a separate test database
        os.environ["DATABASE_URL"] = "test_finance.db"
        init_db()

    def tearDown(self):
        if os.path.exists("test_finance.db"):
            os.remove("test_finance.db")

    def test_pii_sanitization(self):
        text = "My account is 123456789012 and email is test@example.com"
        sanitized, detected = PIISanitizer.sanitize(text)
        self.assertIn("[ACCOUNT_NUMBER]", sanitized)
        self.assertIn("[EMAIL]", sanitized)
        self.assertIn("ACCOUNT_NUMBER", detected)
        self.assertIn("EMAIL", detected)

    def test_csv_ingestion_and_dedup(self):
        csv_content = b"Date,Description,Amount,Category,Merchant\n2026-10-01,Swiggy,450.0,Food,Swiggy\n2026-10-01,Swiggy,450.0,Food,Swiggy"
        txs = IngestionService.process_csv(csv_content)
        self.assertEqual(len(txs), 2)

        count = IngestionService.ingest(txs)
        self.assertEqual(count, 1, "Should only ingest 1 transaction due to deduplication")

        all_txs = DBService.get_transactions()
        self.assertEqual(len(all_txs), 1)

    def test_sms_ingestion(self):
        sms_text = "A/c XX1234 debited for Rs 500.00 on 2026-10-20 via UPI to Swiggy"
        tx = IngestionService.process_sms(sms_text)
        self.assertIsNotNone(tx)
        self.assertEqual(tx['amount'], -500.0)
        self.assertEqual(tx['merchant'], "Swiggy")

        # Test Categorization
        tx['category'] = CategorizerService.categorize(tx['merchant'], tx['description'])
        self.assertEqual(tx['category'], "Food")

        DBService.add_transaction(tx)
        self.assertEqual(len(DBService.get_transactions()), 1)

    def test_category_correction_and_rules(self):
        # Ingest a transaction
        tx = {
            "date": "2026-10-01",
            "description": "Amazon Market",
            "amount": 1000.0,
            "category": "Shopping",
            "merchant": "Amazon",
            "source": "test",
            "hash": "hash1"
        }
        tx_id = DBService.add_transaction(tx)

        # Correct category to "Business"
        result = CategorizerService.apply_category_correction(tx_id, "Business")
        self.assertEqual(result['rule'], "Amazon -> Business")

        # Verify the transaction is updated
        tx_updated = DBService.get_transactions()[0]
        self.assertEqual(tx_updated.category, "Business")

        # Ingest another Amazon transaction
        tx2 = {
            "date": "2026-10-02",
            "description": "Amazon Books",
            "amount": 500.0,
            "category": "Shopping",
            "merchant": "Amazon",
            "source": "test",
            "hash": "hash2"
        }
        # The a priori category is "Shopping", but Categorizer should fix it
        tx2['category'] = CategorizerService.categorize(tx2['merchant'], tx2['description'])
        self.assertEqual(tx2['category'], "Business")

    def test_database_profile_goals(self):
        # Test Profile
        DBService.update_profile("user_1", {"monthly_budget": 5000.0})
        profile = DBService.get_profile("user_1")
        self.assertEqual(profile.monthly_budget, 5000.0)

        # Test Goals
        goal_id = DBService.add_goal({"name": "Emergency Fund", "target_amount": 1000.0, "current_amount": 100.0, "deadline": "2026-12-31"})
        self.assertIsNotNone(goal_id)
        goals = DBService.get_goals()
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0].name, "Emergency Fund")

if __name__ == "__main__":
    unittest.main()
