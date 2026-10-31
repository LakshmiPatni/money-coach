import unittest
import os
from decimal import Decimal
from services.db_service import DBService
from services.engine import FinancialEngine
from services.recurring import RecurringService
from services.nudges import NudgeService
from db import init_db

class TestPhase2(unittest.TestCase):
    def setUp(self):
        os.environ["DATABASE_URL"] = "test_phase2.db"
        init_db()

    def tearDown(self):
        if os.path.exists("test_phase2.db"):
            os.remove("test_phase2.db")

    def test_financial_engine_stats(self):
        # Ingest some data
        txs = [
            {"date": "2026-10-01", "description": "Salary", "amount": 60000.0, "category": "Income", "merchant": "Employer", "source": "test", "hash": "h1"},
            {"date": "2026-10-02", "description": "Rent", "amount": -15000.0, "category": "Housing", "merchant": "Rent", "source": "test", "hash": "h2"},
            {"date": "2026-10-03", "description": "Swiggy", "amount": -500.0, "category": "Food", "merchant": "Swiggy", "source": "test", "hash": "h3"},
        ]
        for t in txs:
            DBService.add_transaction(t)

        stats = FinancialEngine.get_monthly_stats("2026-10")
        self.assertEqual(stats['income'], Decimal('60000.00'))
        self.assertEqual(stats['expenses'], Decimal('15500.00'))
        self.assertEqual(stats['savings'], Decimal('44500.00'))
        self.assertEqual(stats['category_totals']['Housing'], 15000.0)

    def test_financial_engine_stats_more_than_ten_transactions(self):
        # Ingest 12 expense transactions + 1 income in the same month
        for i in range(12):
            DBService.add_transaction({
                "date": f"2026-10-{i+1:02d}",
                "description": f"Expense {i}",
                "amount": -100.0,
                "category": "Food",
                "merchant": "TestMerchant",
                "source": "test",
                "hash": f"h_limit_{i}",
            })
        DBService.add_transaction({
            "date": "2026-10-01",
            "description": "Salary",
            "amount": 5000.0,
            "category": "Income",
            "merchant": "Employer",
            "source": "test",
            "hash": "h_limit_salary",
        })

        stats = FinancialEngine.get_monthly_stats("2026-10")
        self.assertEqual(stats['income'], Decimal('5000.00'))
        self.assertEqual(stats['expenses'], Decimal('1200.00'))
        self.assertEqual(stats['savings'], Decimal('3800.00'))

    def test_runway_calculation(self):
        # Add essential expenses
        txs = [
            {"date": "2026-10-01", "description": "Rent", "amount": -2000.0, "category": "Housing", "merchant": "Rent", "source": "test", "hash": "h1"},
            {"date": "2026-09-01", "description": "Rent", "amount": -2000.0, "category": "Housing", "merchant": "Rent", "source": "test", "hash": "h2"},
        ]
        for t in txs:
            DBService.add_transaction(t)

        # Savings = 10000, Avg Essential = 2000 -> Runway = 5.0
        runway = FinancialEngine.calculate_runway(10000.0)
        self.assertEqual(runway, 5.0)

    def test_recurring_detection(self):
        # Add 3 monthly payments to the same merchant
        for m in ["2026-08-01", "2026-09-01", "2026-10-01"]:
            DBService.add_transaction({
                "date": m, "description": "Netflix", "amount": -649.0, "category": "Entertainment", "merchant": "Netflix", "source": "test", "hash": f"net_{m}"
            })

        subscriptions = RecurringService.sync_subscriptions()
        self.assertTrue(any(s['merchant'] == "Netflix" for s in subscriptions))
        self.assertEqual(subscriptions[0]['billing_cycle'], "monthly")

    def test_subscription_unused_flag(self):
        # Setup a subscription in DB
        DBService.add_transaction({
            "date": "2026-10-01", "description": "Netflix", "amount": -649.0, "category": "Entertainment", "merchant": "Netflix", "source": "test", "hash": "h1"
        })
        DBService.add_transaction({
            "date": "2026-09-01", "description": "Netflix", "amount": -649.0, "category": "Entertainment", "merchant": "Netflix", "source": "test", "hash": "h2"
        })

        # Sync to populate subscriptions table
        RecurringService.sync_subscriptions()

        # Mark as unused
        DBService.update_subscription_unused("Netflix", True)

        # Retrieve and verify
        subs = DBService.get_subscriptions()
        self.assertTrue(any(s.is_unused for s in subs if s.merchant == "Netflix"))

    def test_nudges(self):
        # Setup a budget for the default user
        DBService.update_profile("default", {"monthly_budget": 1000.0})
        # Add expensive transaction
        DBService.add_transaction({
            "date": "2026-10-01", "description": "Expensive Gadget", "amount": -2000.0, "category": "Shopping", "merchant": "Amazon", "source": "test", "hash": "h1"
        })

        nudges = NudgeService.generate_nudges()
        self.assertTrue(any("exceeded your monthly budget" in n.message for n in nudges))

if __name__ == "__main__":
    unittest.main()
