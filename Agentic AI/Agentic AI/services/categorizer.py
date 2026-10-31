from typing import List, Dict, Any
import os
from google import genai
from services.db_service import DBService
from db import get_db_connection

class CategorizerService:
    # Default fallback categories
    DEFAULT_MAPPINGS = {
        "Swiggy": "Food",
        "Zomato": "Food",
        "Cult.fit": "Health",
        "Netflix": "Entertainment",
        "Spotify": "Entertainment",
        "Uber": "Transport",
        "Ola": "Transport",
        "Amazon": "Shopping",
        "Flipkart": "Shopping",
        "BigBasket": "Groceries",
        "Blinkit": "Groceries",
        "Electricity": "Utilities",
        "Rent": "Housing",
    }

    @classmethod
    def smart_categorize_with_gemini(cls, merchant: str, description: str) -> str:
        """
        Uses Gemini AI to intelligently categorize unmapped transactions.
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return "Uncategorized"
            
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"""
            Categorize the following transaction into one of these standard personal finance categories:
            - Food & Dining (e.g., Zomato, Swiggy, Canteen, Mess, Nescafe, Restaurants)
            - Rent & Housing (e.g., Hostel, PG, House Rent)
            - Education & Supplies (e.g., Printouts, Photocopy, Stationery, Books, Library Fine)
            - Transport (e.g., Metro, Auto, Uber, Ola, Fuel)
            - Shopping (e.g., Amazon, Flipkart, Clothes)
            - Entertainment (e.g., Movies, PVR, Netflix, Gaming)
            - Utilities & Bills (e.g., Mobile Recharge, Internet, Electricity)
            - Income (e.g., Stipend, Salary, Payout, Cash_In)
            - Miscellaneous / Other

            Merchant: "{merchant}"
            Description: "{description}"

            Return ONLY the category name. Do not include any extra text, punctuation, or markdown.
            """
            
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            category = response.text.strip()
            return category if category else "Uncategorized"
        except Exception as e:
            print(f"Gemini Categorization error: {e}")
            return "Uncategorized"

    @classmethod
    def categorize(cls, merchant: str, description: str) -> str:
        """
        Assigns a category to a transaction based on learned rules,
        then default mappings, then Gemini AI, and finally "Uncategorized".
        """
        # 1. Check learned rules in DB
        rules = DBService.get_rules()
        for rule in rules:
            if rule.pattern.lower() in merchant.lower() or rule.pattern.lower() in description.lower():
                return rule.category

        # 2. Check default mappings
        for pattern, category in cls.DEFAULT_MAPPINGS.items():
            if pattern.lower() in merchant.lower() or pattern.lower() in description.lower():
                return category

        # 3. Fallback to Gemini AI Smart Categorization
        ai_category = cls.smart_categorize_with_gemini(merchant, description)
        if ai_category and ai_category != "Uncategorized":
            return ai_category

        return "Uncategorized"

    @classmethod
    def apply_category_correction(cls, tx_id: int, new_category: str) -> Dict[str, Any]:
        """
        Learns from a category correction:
        1. Updates the specific transaction.
        2. Creates a rule for the merchant.
        3. Updates all other transactions matching that merchant.
        """
        # Fetch the transaction to get the merchant
        with get_db_connection() as conn:
            row = conn.execute("SELECT merchant FROM transactions WHERE id = ?", (tx_id,)).fetchone()
            if not row:
                raise ValueError("Transaction not found")
            merchant = row['merchant']

        # 1. Update the specific transaction
        DBService.update_transaction_category(tx_id, new_category)

        # 2. Persist the rule
        DBService.save_rule(merchant, new_category)

        # 3. Update all other transactions matching this merchant
        with get_db_connection() as conn:
            cursor = conn.execute(
                "UPDATE transactions SET category = ? WHERE merchant = ? AND category != ?",
                (new_category, merchant, new_category)
            )
            affected_count = cursor.rowcount
            conn.commit()

        return {
            "rule": f"{merchant} -> {new_category}",
            "affected_count": affected_count,
            "transactions_updated": affected_count + 1
        }

    @classmethod
    def categorize_batch(cls, transactions: List[Dict[str, Any]]):
        """
        Categorizes a list of raw transactions.
        """
        for tx in transactions:
            tx['category'] = cls.categorize(tx['merchant'], tx['description'])
        return transactions
