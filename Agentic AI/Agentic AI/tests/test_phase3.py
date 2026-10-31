import unittest
import os
from decimal import Decimal
from services.db_service import DBService
from services.engine import FinancialEngine
from services.agent import CoachAgent
from db import init_db

class TestPhase3(unittest.TestCase):
    def setUp(self):
        os.environ["DATABASE_URL"] = "test_phase3.db"
        init_db()

    def tearDown(self):
        if os.path.exists("test_phase3.db"):
            os.remove("test_phase3.db")

    def test_whatif_savings_increase(self):
        # Setup basic transactions
        txs = [
            {"date": "2026-10-01", "description": "Salary", "amount": 60000.0, "category": "Income", "merchant": "Employer", "source": "test", "hash": "h1"},
            {"date": "2026-10-02", "description": "Rent", "amount": -15000.0, "category": "Housing", "merchant": "Rent", "source": "test", "hash": "h2"},
        ]
        for t in txs:
            DBService.add_transaction(t)

        # Simulation: Reduce Rent by 1000
        changes = {"Housing": 1000.0} # Positive value here means savings for a cost category in our logic?
        # Wait, let's check engine.py:
        # if isinstance(change, float) ... savings = current_cat_spend * Decimal(str(-change))
        # if not float ... projected_expenses += cls.to_decimal(change)

        # To reduce rent by 1000, change should be -1000.0
        result = FinancialEngine.simulate_what_if({"Housing": -1000.0})
        self.assertGreater(result['projected_savings'], 45000.0) # 60k - 15k + 1k = 46k

    def test_whatif_subscription_cancel(self):
        # Setup a subscription in DB (need transactions first to be detected)
        for m in ["2026-08-01", "2026-09-01", "2026-10-01"]:
            DBService.add_transaction({
                "date": m, "description": "Netflix", "amount": -649.0, "category": "Entertainment", "merchant": "Netflix", "source": "test", "hash": f"net_{m}"
            })

        # Detection happens inside simulate_what_if via RecurringService
        from services.recurring import RecurringService
        RecurringService.sync_subscriptions()

        # Simulation: Cancel Netflix
        result = FinancialEngine.simulate_what_if({"cancel": ["Netflix"]})
        self.assertIn("Cancelling Netflix saves 649.00/mo", result['impact_summary'])

    def test_coach_affordability(self):
        # Setup high surplus
        DBService.add_transaction({
            "date": "2026-10-01", "description": "Salary", "amount": 10000.0, "category": "Income", "merchant": "Employer", "source": "test", "hash": "h1"
        })
        DBService.add_transaction({
            "date": "2026-10-02", "description": "Rent", "amount": -1000.0, "category": "Housing", "merchant": "Rent", "source": "test", "hash": "h2"
        })

        res = CoachAgent.handle_chat("Can I afford a new laptop?")
        self.assertEqual(res.intent, "affordability_check")
        self.assertIn("surplus of 9000.00", res.reply)

    def test_coach_spending_analysis(self):
        # Setup spending in one category
        for i in range(5):
            DBService.add_transaction({
                "date": f"2026-10-0{i+1}", "description": "Swiggy", "amount": -500.0, "category": "Food", "merchant": "Swiggy", "source": "test", "hash": f"s{i}"
            })

        res = CoachAgent.handle_chat("Analyze my spending patterns")
        self.assertEqual(res.intent, "spending_analysis")
        self.assertIn("Food", res.reply)
        self.assertIn("2500.00", res.reply)

    def test_insufficient_data_handling(self):
        # Empty DB
        res = CoachAgent.handle_chat("Analyze my spending")
        self.assertIn("don't have enough transaction data", res.reply)

if __name__ == "__main__":
    unittest.main()
