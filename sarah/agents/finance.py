"""
Finance agent for budget tracking, expense management, and financial insights
"""

import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from sarah.agents.base import BaseAgent, Message, MessageType, Priority
from sarah.services.ai_service import AIService
from sarah.core.memory import MemoryPalace


class TransactionType(Enum):
    """Types of financial transactions"""

    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class ExpenseCategory(Enum):
    """Common expense categories"""

    HOUSING = "housing"
    TRANSPORTATION = "transportation"
    FOOD = "food"
    UTILITIES = "utilities"
    INSURANCE = "insurance"
    HEALTHCARE = "healthcare"
    ENTERTAINMENT = "entertainment"
    SHOPPING = "shopping"
    EDUCATION = "education"
    SAVINGS = "savings"
    DEBT = "debt"
    OTHER = "other"


class RecurrenceType(Enum):
    """Types of recurring transactions"""

    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


class FinanceAgent(BaseAgent):
    """Agent for managing finances, budgets, and expenses"""

    def __init__(self, agent_id: str = "finance_agent"):
        super().__init__(agent_id)
        self.ai_service = AIService()
        self.memory = MemoryPalace()

        # In-memory storage (would be database in production)
        self.transactions: List[Dict[str, Any]] = []
        self.budgets: Dict[str, Dict[str, Any]] = {}
        self.bills: List[Dict[str, Any]] = []
        self.accounts: Dict[str, Dict[str, Any]] = {}

        # Initialize with default accounts
        self._initialize_default_accounts()

    def _initialize_default_accounts(self):
        """Initialize default accounts"""
        self.accounts = {
            "checking": {
                "name": "Main Checking",
                "type": "checking",
                "balance": Decimal("0.00"),
                "currency": "USD",
            },
            "savings": {
                "name": "Emergency Savings",
                "type": "savings",
                "balance": Decimal("0.00"),
                "currency": "USD",
            },
            "credit": {
                "name": "Credit Card",
                "type": "credit",
                "balance": Decimal("0.00"),
                "currency": "USD",
                "credit_limit": Decimal("5000.00"),
            },
        }

    async def handle_request(self, message: Message) -> Optional[Message]:
        """Handle finance-related requests"""
        try:
            content = message.content

            # Parse intent using AI
            intent = await self._parse_intent(content)

            if intent == "add_transaction":
                return await self._handle_add_transaction(message)
            elif intent == "view_balance":
                return await self._handle_view_balance(message)
            elif intent == "set_budget":
                return await self._handle_set_budget(message)
            elif intent == "view_budget":
                return await self._handle_view_budget(message)
            elif intent == "add_bill":
                return await self._handle_add_bill(message)
            elif intent == "view_bills":
                return await self._handle_view_bills(message)
            elif intent == "financial_summary":
                return await self._handle_financial_summary(message)
            elif intent == "expense_analysis":
                return await self._handle_expense_analysis(message)
            else:
                return await self._handle_general_query(message)

        except Exception as e:
            self.logger.error(f"Error handling finance request: {e}")
            return self.create_response(
                original_message=message,
                content=f"I encountered an error processing your financial request: {str(e)}",
                priority=Priority.HIGH,
            )

    async def _parse_intent(self, content: str) -> str:
        """Parse user intent from message"""
        prompt = f"""
        Analyze this financial request and determine the intent.
        
        Request: {content}
        
        Possible intents:
        - add_transaction: Recording income/expense
        - view_balance: Checking account balances
        - set_budget: Creating or updating a budget
        - view_budget: Viewing budget status
        - add_bill: Adding a bill reminder
        - view_bills: Viewing upcoming bills
        - financial_summary: Overall financial overview
        - expense_analysis: Analyzing spending patterns
        - general: General financial question
        
        Return only the intent keyword.
        """

        response = await self.ai_service.get_completion(prompt)
        return response.strip().lower()

    async def _handle_add_transaction(self, message: Message) -> Message:
        """Handle adding a new transaction"""
        content = message.content

        # Parse transaction details
        transaction_data = await self._parse_transaction(content)

        if not transaction_data:
            return self.create_response(
                original_message=message,
                content="I couldn't understand the transaction details. Please specify the amount, type (income/expense), and category.",
                priority=Priority.MEDIUM,
            )

        # Create transaction
        transaction = {
            "id": len(self.transactions) + 1,
            "date": datetime.now().isoformat(),
            "amount": transaction_data["amount"],
            "type": transaction_data["type"],
            "category": transaction_data.get("category", ExpenseCategory.OTHER.value),
            "description": transaction_data.get("description", ""),
            "account": transaction_data.get("account", "checking"),
        }

        # Update account balance
        self._update_account_balance(transaction)

        # Store transaction
        self.transactions.append(transaction)

        # Save to memory
        await self.memory.remember(
            content=json.dumps(transaction),
            category="finance",
            metadata={"type": "transaction", "transaction_id": transaction["id"]},
        )

        return self.create_response(
            original_message=message,
            content=f"Transaction recorded: {transaction['type']} of ${transaction['amount']:.2f} in {transaction['category']}. "
            f"New {transaction['account']} balance: ${self.accounts[transaction['account']]['balance']:.2f}",
            priority=Priority.MEDIUM,
        )

    async def _handle_view_balance(self, message: Message) -> Message:
        """Handle viewing account balances"""
        balances = []
        total_assets = Decimal("0.00")
        total_liabilities = Decimal("0.00")

        for account_id, account in self.accounts.items():
            balance = account["balance"]
            if account["type"] in ["checking", "savings"]:
                total_assets += balance
                balances.append(f"{account['name']}: ${balance:.2f}")
            else:  # credit
                total_liabilities += balance
                available = account.get("credit_limit", Decimal("0.00")) - balance
                balances.append(
                    f"{account['name']}: ${balance:.2f} (${available:.2f} available)"
                )

        net_worth = total_assets - total_liabilities

        response = "Account Balances:\n" + "\n".join(balances)
        response += f"\n\nTotal Assets: ${total_assets:.2f}"
        response += f"\nTotal Liabilities: ${total_liabilities:.2f}"
        response += f"\nNet Worth: ${net_worth:.2f}"

        return self.create_response(
            original_message=message, content=response, priority=Priority.MEDIUM
        )

    async def _handle_set_budget(self, message: Message) -> Message:
        """Handle setting a budget"""
        budget_data = await self._parse_budget(message.content)

        if not budget_data:
            return self.create_response(
                original_message=message,
                content="Please specify the category and amount for the budget.",
                priority=Priority.MEDIUM,
            )

        category = budget_data["category"]
        self.budgets[category] = {
            "amount": budget_data["amount"],
            "period": budget_data.get("period", "monthly"),
            "created": datetime.now().isoformat(),
        }

        # Save to memory
        await self.memory.remember(
            content=json.dumps(self.budgets[category]),
            category="finance",
            metadata={"type": "budget", "budget_category": category},
        )

        return self.create_response(
            original_message=message,
            content=f"Budget set: ${budget_data['amount']:.2f} {budget_data.get('period', 'monthly')} for {category}",
            priority=Priority.MEDIUM,
        )

    async def _handle_view_budget(self, message: Message) -> Message:
        """Handle viewing budget status"""
        if not self.budgets:
            return self.create_response(
                original_message=message,
                content="No budgets have been set yet.",
                priority=Priority.MEDIUM,
            )

        # Calculate spending for each budget category
        current_month = datetime.now().month
        current_year = datetime.now().year

        budget_status = []
        for category, budget in self.budgets.items():
            # Calculate spent amount
            spent = sum(
                Decimal(str(t["amount"]))
                for t in self.transactions
                if t["type"] == TransactionType.EXPENSE.value
                and t.get("category") == category
                and datetime.fromisoformat(t["date"]).month == current_month
                and datetime.fromisoformat(t["date"]).year == current_year
            )

            budget_amount = Decimal(str(budget["amount"]))
            remaining = budget_amount - spent
            percentage = (spent / budget_amount * 100) if budget_amount > 0 else 0

            status = (
                f"{category}: ${spent:.2f} / ${budget_amount:.2f} ({percentage:.1f}%)"
            )
            if remaining < 0:
                status += f" - OVER BUDGET by ${abs(remaining):.2f}"
            else:
                status += f" - ${remaining:.2f} remaining"

            budget_status.append(status)

        return self.create_response(
            original_message=message,
            content="Budget Status:\n" + "\n".join(budget_status),
            priority=Priority.MEDIUM,
        )

    async def _handle_add_bill(self, message: Message) -> Message:
        """Handle adding a bill reminder"""
        bill_data = await self._parse_bill(message.content)

        if not bill_data:
            return self.create_response(
                original_message=message,
                content="Please specify the bill name, amount, and due date.",
                priority=Priority.MEDIUM,
            )

        bill = {
            "id": len(self.bills) + 1,
            "name": bill_data["name"],
            "amount": bill_data["amount"],
            "due_date": bill_data["due_date"],
            "recurrence": bill_data.get("recurrence", RecurrenceType.MONTHLY.value),
            "category": bill_data.get("category", ExpenseCategory.OTHER.value),
            "auto_pay": bill_data.get("auto_pay", False),
            "created": datetime.now().isoformat(),
        }

        self.bills.append(bill)

        # Save to memory
        await self.memory.remember(
            content=json.dumps(bill),
            category="finance",
            metadata={"type": "bill", "bill_id": bill["id"]},
        )

        return self.create_response(
            original_message=message,
            content=f"Bill reminder added: {bill['name']} for ${bill['amount']:.2f} due on {bill['due_date']}",
            priority=Priority.MEDIUM,
        )

    async def _handle_view_bills(self, message: Message) -> Message:
        """Handle viewing upcoming bills"""
        if not self.bills:
            return self.create_response(
                original_message=message,
                content="No bills have been added yet.",
                priority=Priority.MEDIUM,
            )

        # Sort bills by due date
        upcoming_bills = []
        total_due = Decimal("0.00")

        for bill in sorted(self.bills, key=lambda x: x["due_date"]):
            amount = Decimal(str(bill["amount"]))
            total_due += amount

            status = f"{bill['name']}: ${amount:.2f} due on {bill['due_date']}"
            if bill.get("auto_pay"):
                status += " (Auto-pay enabled)"

            upcoming_bills.append(status)

        response = "Upcoming Bills:\n" + "\n".join(upcoming_bills)
        response += f"\n\nTotal Due: ${total_due:.2f}"

        return self.create_response(
            original_message=message, content=response, priority=Priority.MEDIUM
        )

    async def _handle_financial_summary(self, message: Message) -> Message:
        """Handle generating a financial summary"""
        # Calculate key metrics
        current_month = datetime.now().month
        current_year = datetime.now().year

        # Monthly income/expenses
        monthly_income = sum(
            Decimal(str(t["amount"]))
            for t in self.transactions
            if t["type"] == TransactionType.INCOME.value
            and datetime.fromisoformat(t["date"]).month == current_month
            and datetime.fromisoformat(t["date"]).year == current_year
        )

        monthly_expenses = sum(
            Decimal(str(t["amount"]))
            for t in self.transactions
            if t["type"] == TransactionType.EXPENSE.value
            and datetime.fromisoformat(t["date"]).month == current_month
            and datetime.fromisoformat(t["date"]).year == current_year
        )

        monthly_savings = monthly_income - monthly_expenses
        savings_rate = (
            (monthly_savings / monthly_income * 100) if monthly_income > 0 else 0
        )

        # Account totals
        total_assets = sum(
            acc["balance"]
            for acc in self.accounts.values()
            if acc["type"] in ["checking", "savings"]
        )

        total_debt = sum(
            acc["balance"] for acc in self.accounts.values() if acc["type"] == "credit"
        )

        # Generate summary
        summary = f"""Financial Summary for {datetime.now().strftime('%B %Y')}:

Income: ${monthly_income:.2f}
Expenses: ${monthly_expenses:.2f}
Net: ${monthly_savings:.2f} ({savings_rate:.1f}% savings rate)

Total Assets: ${total_assets:.2f}
Total Debt: ${total_debt:.2f}
Net Worth: ${total_assets - total_debt:.2f}

Top Expense Categories:"""

        # Add top expense categories
        expense_by_category = {}
        for t in self.transactions:
            if t["type"] == TransactionType.EXPENSE.value:
                cat = t.get("category", "other")
                expense_by_category[cat] = expense_by_category.get(
                    cat, Decimal("0")
                ) + Decimal(str(t["amount"]))

        for cat, amount in sorted(
            expense_by_category.items(), key=lambda x: x[1], reverse=True
        )[:3]:
            summary += f"\n- {cat}: ${amount:.2f}"

        return self.create_response(
            original_message=message, content=summary, priority=Priority.MEDIUM
        )

    async def _handle_expense_analysis(self, message: Message) -> Message:
        """Handle analyzing expense patterns"""
        # Analyze spending patterns
        analysis = await self._analyze_spending_patterns()

        return self.create_response(
            original_message=message, content=analysis, priority=Priority.MEDIUM
        )

    async def _analyze_spending_patterns(self) -> str:
        """Analyze spending patterns and provide insights"""
        if not self.transactions:
            return "No transaction data available for analysis."

        # Group expenses by category
        expense_by_category = {}
        total_expenses = Decimal("0.00")

        for t in self.transactions:
            if t["type"] == TransactionType.EXPENSE.value:
                cat = t.get("category", "other")
                amount = Decimal(str(t["amount"]))
                expense_by_category[cat] = (
                    expense_by_category.get(cat, Decimal("0")) + amount
                )
                total_expenses += amount

        # Calculate daily average
        if self.transactions:
            first_date = min(
                datetime.fromisoformat(t["date"]) for t in self.transactions
            )
            days_tracked = (datetime.now() - first_date).days + 1
            daily_average = total_expenses / days_tracked
        else:
            daily_average = Decimal("0.00")

        # Generate insights
        insights = [
            f"Total expenses: ${total_expenses:.2f}",
            f"Daily average: ${daily_average:.2f}",
            f"Categories tracked: {len(expense_by_category)}",
        ]

        # Top categories
        insights.append("\nTop spending categories:")
        for cat, amount in sorted(
            expense_by_category.items(), key=lambda x: x[1], reverse=True
        )[:5]:
            percentage = (amount / total_expenses * 100) if total_expenses > 0 else 0
            insights.append(f"- {cat}: ${amount:.2f} ({percentage:.1f}%)")

        # AI-generated insights
        if expense_by_category:
            ai_prompt = f"""
            Analyze these spending patterns and provide 2-3 actionable insights:
            {json.dumps({k: float(v) for k, v in expense_by_category.items()})}
            
            Total expenses: ${total_expenses}
            Daily average: ${daily_average}
            
            Provide brief, practical advice for improving financial health.
            """

            ai_insights = await self.ai_service.get_completion(ai_prompt)
            insights.append(f"\nInsights:\n{ai_insights}")

        return "\n".join(insights)

    async def _handle_general_query(self, message: Message) -> Message:
        """Handle general finance queries"""
        # Use AI to answer general questions
        context = {
            "accounts": {
                k: {**v, "balance": float(v["balance"])}
                for k, v in self.accounts.items()
            },
            "recent_transactions": self.transactions[-10:] if self.transactions else [],
            "budgets": self.budgets,
            "bills": self.bills,
        }

        prompt = f"""
        Answer this financial question using the provided context.
        
        Question: {message.content}
        
        Context: {json.dumps(context, indent=2)}
        
        Provide a helpful, accurate response.
        """

        response = await self.ai_service.get_completion(prompt)

        return self.create_response(
            original_message=message, content=response, priority=Priority.MEDIUM
        )

    async def _parse_transaction(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse transaction details from user input"""
        prompt = f"""
        Extract transaction details from this text: {content}
        
        Return JSON with:
        - amount: number (required)
        - type: "income" or "expense" (required)
        - category: one of {[c.value for c in ExpenseCategory]}
        - description: string
        - account: "checking", "savings", or "credit"
        
        Return null if details cannot be extracted.
        """

        response = await self.ai_service.get_completion(prompt)
        try:
            data = json.loads(response)
            if data and "amount" in data and "type" in data:
                data["amount"] = Decimal(str(data["amount"]))
                return data
        except:
            pass
        return None

    async def _parse_budget(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse budget details from user input"""
        prompt = f"""
        Extract budget details from this text: {content}
        
        Return JSON with:
        - category: string (required)
        - amount: number (required)
        - period: "daily", "weekly", "monthly", "quarterly", "annually"
        
        Return null if details cannot be extracted.
        """

        response = await self.ai_service.get_completion(prompt)
        try:
            data = json.loads(response)
            if data and "category" in data and "amount" in data:
                data["amount"] = Decimal(str(data["amount"]))
                return data
        except:
            pass
        return None

    async def _parse_bill(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse bill details from user input"""
        prompt = f"""
        Extract bill details from this text: {content}
        
        Return JSON with:
        - name: string (required)
        - amount: number (required)
        - due_date: string in format "YYYY-MM-DD" or "DD" for day of month
        - recurrence: one of {[r.value for r in RecurrenceType]}
        - category: one of {[c.value for c in ExpenseCategory]}
        - auto_pay: boolean
        
        Return null if details cannot be extracted.
        """

        response = await self.ai_service.get_completion(prompt)
        try:
            data = json.loads(response)
            if data and all(k in data for k in ["name", "amount", "due_date"]):
                data["amount"] = Decimal(str(data["amount"]))
                return data
        except:
            pass
        return None

    def _update_account_balance(self, transaction: Dict[str, Any]):
        """Update account balance based on transaction"""
        account_id = transaction["account"]
        amount = Decimal(str(transaction["amount"]))

        if transaction["type"] == TransactionType.INCOME.value:
            self.accounts[account_id]["balance"] += amount
        elif transaction["type"] == TransactionType.EXPENSE.value:
            self.accounts[account_id]["balance"] -= amount
        elif transaction["type"] == TransactionType.TRANSFER.value:
            # Handle transfers between accounts
            pass  # TODO: Implement transfer logic

    async def get_financial_health_score(self) -> int:
        """Calculate a financial health score (0-100)"""
        score = 50  # Base score

        # Factor 1: Savings rate (up to 20 points)
        current_month = datetime.now().month
        monthly_income = sum(
            Decimal(str(t["amount"]))
            for t in self.transactions
            if t["type"] == TransactionType.INCOME.value
            and datetime.fromisoformat(t["date"]).month == current_month
        )
        monthly_expenses = sum(
            Decimal(str(t["amount"]))
            for t in self.transactions
            if t["type"] == TransactionType.EXPENSE.value
            and datetime.fromisoformat(t["date"]).month == current_month
        )

        if monthly_income > 0:
            savings_rate = (monthly_income - monthly_expenses) / monthly_income
            score += int(min(20, savings_rate * 100))

        # Factor 2: Emergency fund (up to 15 points)
        savings_balance = self.accounts.get("savings", {}).get("balance", Decimal("0"))
        if monthly_expenses > 0:
            months_covered = savings_balance / monthly_expenses
            score += int(min(15, months_covered * 5))

        # Factor 3: Debt-to-income ratio (up to 15 points)
        total_debt = sum(
            acc["balance"] for acc in self.accounts.values() if acc["type"] == "credit"
        )
        if monthly_income > 0:
            debt_ratio = total_debt / (monthly_income * 12)
            score += int(max(0, 15 - debt_ratio * 50))

        return min(100, max(0, score))
