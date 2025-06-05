"""
Tests for the Finance agent
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from sarah.agents.finance import (
    FinanceAgent,
    TransactionType,
    ExpenseCategory,
    RecurrenceType,
)
from sarah.agents.base import Message, MessageType, Priority


@pytest.fixture
async def finance_agent():
    """Create a Finance agent for testing"""
    with patch("sarah.agents.finance.AIService"), patch(
        "sarah.agents.finance.MemoryPalace"
    ):
        agent = FinanceAgent()
        # Mock AI service
        agent.ai_service = AsyncMock()
        agent.memory = AsyncMock()

        # Start the agent
        await agent.start()
        yield agent
        await agent.stop()


@pytest.fixture
def sample_message():
    """Create a sample message"""
    return Message(
        id="test_123",
        agent_id="user",
        content="Test message",
        message_type=MessageType.REQUEST,
        priority=Priority.MEDIUM,
        timestamp=datetime.now().isoformat(),
    )


class TestFinanceAgent:
    """Test Finance agent functionality"""

    async def test_initialization(self, finance_agent):
        """Test agent initialization"""
        assert finance_agent.agent_id == "finance_agent"
        assert len(finance_agent.accounts) == 3
        assert "checking" in finance_agent.accounts
        assert "savings" in finance_agent.accounts
        assert "credit" in finance_agent.accounts

    async def test_add_income_transaction(self, finance_agent, sample_message):
        """Test adding an income transaction"""
        sample_message.content = "I received $1500 salary payment"

        # Mock AI responses
        finance_agent.ai_service.get_completion.side_effect = [
            "add_transaction",  # Intent
            json.dumps(
                {  # Transaction parsing
                    "amount": 1500,
                    "type": "income",
                    "category": "salary",
                    "description": "Monthly salary",
                    "account": "checking",
                }
            ),
        ]

        response = await finance_agent.handle_request(sample_message)

        assert response is not None
        assert "Transaction recorded" in response.content
        assert "$1500.00" in response.content
        assert len(finance_agent.transactions) == 1
        assert finance_agent.accounts["checking"]["balance"] == Decimal("1500.00")

    async def test_add_expense_transaction(self, finance_agent, sample_message):
        """Test adding an expense transaction"""
        # Set initial balance
        finance_agent.accounts["checking"]["balance"] = Decimal("2000.00")

        sample_message.content = "Spent $50 on groceries"

        # Mock AI responses
        finance_agent.ai_service.get_completion.side_effect = [
            "add_transaction",  # Intent
            json.dumps(
                {  # Transaction parsing
                    "amount": 50,
                    "type": "expense",
                    "category": "food",
                    "description": "Grocery shopping",
                    "account": "checking",
                }
            ),
        ]

        response = await finance_agent.handle_request(sample_message)

        assert response is not None
        assert "Transaction recorded" in response.content
        assert len(finance_agent.transactions) == 1
        assert finance_agent.accounts["checking"]["balance"] == Decimal("1950.00")

    async def test_view_balance(self, finance_agent, sample_message):
        """Test viewing account balances"""
        # Set up test balances
        finance_agent.accounts["checking"]["balance"] = Decimal("1500.00")
        finance_agent.accounts["savings"]["balance"] = Decimal("5000.00")
        finance_agent.accounts["credit"]["balance"] = Decimal("300.00")

        sample_message.content = "What's my balance?"

        # Mock AI response
        finance_agent.ai_service.get_completion.return_value = "view_balance"

        response = await finance_agent.handle_request(sample_message)

        assert response is not None
        assert "Account Balances" in response.content
        assert "Main Checking: $1500.00" in response.content
        assert "Emergency Savings: $5000.00" in response.content
        assert "Credit Card: $300.00" in response.content
        assert "Net Worth: $6200.00" in response.content

    async def test_set_budget(self, finance_agent, sample_message):
        """Test setting a budget"""
        sample_message.content = "Set a $500 monthly budget for food"

        # Mock AI responses
        finance_agent.ai_service.get_completion.side_effect = [
            "set_budget",  # Intent
            json.dumps(
                {  # Budget parsing
                    "category": "food",
                    "amount": 500,
                    "period": "monthly",
                }
            ),
        ]

        response = await finance_agent.handle_request(sample_message)

        assert response is not None
        assert "Budget set" in response.content
        assert "$500.00 monthly for food" in response.content
        assert "food" in finance_agent.budgets
        assert finance_agent.budgets["food"]["amount"] == Decimal("500.00")

    async def test_view_budget_status(self, finance_agent, sample_message):
        """Test viewing budget status"""
        # Set up budget and transactions
        finance_agent.budgets["food"] = {
            "amount": Decimal("500.00"),
            "period": "monthly",
            "created": datetime.now().isoformat(),
        }

        # Add some food expenses for current month
        finance_agent.transactions = [
            {
                "id": 1,
                "date": datetime.now().isoformat(),
                "amount": Decimal("150.00"),
                "type": TransactionType.EXPENSE.value,
                "category": "food",
            },
            {
                "id": 2,
                "date": datetime.now().isoformat(),
                "amount": Decimal("75.00"),
                "type": TransactionType.EXPENSE.value,
                "category": "food",
            },
        ]

        sample_message.content = "Show my budget status"

        # Mock AI response
        finance_agent.ai_service.get_completion.return_value = "view_budget"

        response = await finance_agent.handle_request(sample_message)

        assert response is not None
        assert "Budget Status" in response.content
        assert "food: $225.00 / $500.00 (45.0%)" in response.content
        assert "$275.00 remaining" in response.content

    async def test_add_bill(self, finance_agent, sample_message):
        """Test adding a bill reminder"""
        sample_message.content = "Add monthly internet bill for $80 due on the 15th"

        # Mock AI responses
        finance_agent.ai_service.get_completion.side_effect = [
            "add_bill",  # Intent
            json.dumps(
                {  # Bill parsing
                    "name": "Internet",
                    "amount": 80,
                    "due_date": "15",
                    "recurrence": "monthly",
                    "category": "utilities",
                    "auto_pay": False,
                }
            ),
        ]

        response = await finance_agent.handle_request(sample_message)

        assert response is not None
        assert "Bill reminder added" in response.content
        assert "Internet for $80.00" in response.content
        assert len(finance_agent.bills) == 1
        assert finance_agent.bills[0]["name"] == "Internet"

    async def test_view_bills(self, finance_agent, sample_message):
        """Test viewing upcoming bills"""
        # Add test bills
        finance_agent.bills = [
            {
                "id": 1,
                "name": "Rent",
                "amount": Decimal("1200.00"),
                "due_date": "2024-01-01",
                "auto_pay": True,
            },
            {
                "id": 2,
                "name": "Electric",
                "amount": Decimal("100.00"),
                "due_date": "2024-01-05",
                "auto_pay": False,
            },
        ]

        sample_message.content = "Show my bills"

        # Mock AI response
        finance_agent.ai_service.get_completion.return_value = "view_bills"

        response = await finance_agent.handle_request(sample_message)

        assert response is not None
        assert "Upcoming Bills" in response.content
        assert "Rent: $1200.00" in response.content
        assert "Auto-pay enabled" in response.content
        assert "Total Due: $1300.00" in response.content

    async def test_financial_summary(self, finance_agent, sample_message):
        """Test generating financial summary"""
        # Set up test data
        current_date = datetime.now()
        finance_agent.accounts["checking"]["balance"] = Decimal("2000.00")
        finance_agent.accounts["savings"]["balance"] = Decimal("5000.00")
        finance_agent.accounts["credit"]["balance"] = Decimal("500.00")

        # Add transactions for current month
        finance_agent.transactions = [
            {
                "id": 1,
                "date": current_date.isoformat(),
                "amount": Decimal("3000.00"),
                "type": TransactionType.INCOME.value,
                "category": "salary",
            },
            {
                "id": 2,
                "date": current_date.isoformat(),
                "amount": Decimal("1200.00"),
                "type": TransactionType.EXPENSE.value,
                "category": "housing",
            },
            {
                "id": 3,
                "date": current_date.isoformat(),
                "amount": Decimal("400.00"),
                "type": TransactionType.EXPENSE.value,
                "category": "food",
            },
        ]

        sample_message.content = "Give me a financial summary"

        # Mock AI response
        finance_agent.ai_service.get_completion.return_value = "financial_summary"

        response = await finance_agent.handle_request(sample_message)

        assert response is not None
        assert "Financial Summary" in response.content
        assert "Income: $3000.00" in response.content
        assert "Expenses: $1600.00" in response.content
        assert "Net: $1400.00" in response.content
        assert "Net Worth: $6500.00" in response.content

    async def test_expense_analysis(self, finance_agent, sample_message):
        """Test expense analysis"""
        # Add various expenses
        finance_agent.transactions = [
            {
                "id": i,
                "date": (datetime.now() - timedelta(days=i)).isoformat(),
                "amount": Decimal(str(100 + i * 10)),
                "type": TransactionType.EXPENSE.value,
                "category": ["food", "transportation", "entertainment"][i % 3],
            }
            for i in range(10)
        ]

        sample_message.content = "Analyze my spending"

        # Mock AI responses
        finance_agent.ai_service.get_completion.side_effect = [
            "expense_analysis",  # Intent
            "Based on your spending patterns:\n1. Food is your highest expense\n2. Consider setting a budget\n3. Look for ways to reduce transportation costs",  # AI insights
        ]

        response = await finance_agent.handle_request(sample_message)

        assert response is not None
        assert "Total expenses:" in response.content
        assert "Daily average:" in response.content
        assert "Top spending categories:" in response.content

    async def test_financial_health_score(self, finance_agent):
        """Test financial health score calculation"""
        # Set up healthy financial situation
        finance_agent.accounts["checking"]["balance"] = Decimal("2000.00")
        finance_agent.accounts["savings"]["balance"] = Decimal("10000.00")
        finance_agent.accounts["credit"]["balance"] = Decimal("500.00")

        # Add income and expenses
        current_date = datetime.now()
        finance_agent.transactions = [
            {
                "id": 1,
                "date": current_date.isoformat(),
                "amount": Decimal("5000.00"),
                "type": TransactionType.INCOME.value,
            },
            {
                "id": 2,
                "date": current_date.isoformat(),
                "amount": Decimal("3000.00"),
                "type": TransactionType.EXPENSE.value,
            },
        ]

        score = await finance_agent.get_financial_health_score()

        assert isinstance(score, int)
        assert 0 <= score <= 100
        assert score > 50  # Should have decent score with savings and low debt

    async def test_invalid_transaction(self, finance_agent, sample_message):
        """Test handling invalid transaction input"""
        sample_message.content = "Something random"

        # Mock AI responses
        finance_agent.ai_service.get_completion.side_effect = [
            "add_transaction",  # Intent
            "null",  # Failed parsing
        ]

        response = await finance_agent.handle_request(sample_message)

        assert response is not None
        assert "couldn't understand" in response.content
        assert len(finance_agent.transactions) == 0

    async def test_general_query(self, finance_agent, sample_message):
        """Test handling general financial queries"""
        sample_message.content = "How can I save more money?"

        # Mock AI responses
        finance_agent.ai_service.get_completion.side_effect = [
            "general",  # Intent
            "Here are some tips to save more money:\n1. Track your expenses\n2. Create a budget\n3. Automate savings",
        ]

        response = await finance_agent.handle_request(sample_message)

        assert response is not None
        assert "Track your expenses" in response.content

    async def test_error_handling(self, finance_agent, sample_message):
        """Test error handling"""
        sample_message.content = "Check my balance"

        # Mock AI service to raise an error
        finance_agent.ai_service.get_completion.side_effect = Exception(
            "AI service error"
        )

        response = await finance_agent.handle_request(sample_message)

        assert response is not None
        assert "encountered an error" in response.content
        assert response.priority == Priority.HIGH

    async def test_budget_overspending_alert(self, finance_agent, sample_message):
        """Test budget overspending detection"""
        # Set up budget
        finance_agent.budgets["food"] = {
            "amount": Decimal("300.00"),
            "period": "monthly",
            "created": datetime.now().isoformat(),
        }

        # Add expenses that exceed budget
        finance_agent.transactions = [
            {
                "id": i,
                "date": datetime.now().isoformat(),
                "amount": Decimal("150.00"),
                "type": TransactionType.EXPENSE.value,
                "category": "food",
            }
            for i in range(3)  # $450 total
        ]

        sample_message.content = "Check my food budget"

        # Mock AI response
        finance_agent.ai_service.get_completion.return_value = "view_budget"

        response = await finance_agent.handle_request(sample_message)

        assert response is not None
        assert "OVER BUDGET" in response.content
        assert "$150.00" in response.content  # Over by amount

    async def test_multiple_account_types(self, finance_agent):
        """Test handling different account types"""
        # Add investment account
        finance_agent.accounts["investment"] = {
            "name": "Brokerage",
            "type": "investment",
            "balance": Decimal("15000.00"),
            "currency": "USD",
        }

        # Calculate net worth
        total_assets = sum(
            acc["balance"]
            for acc in finance_agent.accounts.values()
            if acc["type"] in ["checking", "savings", "investment"]
        )

        assert total_assets == Decimal("15000.00")  # Only investment has balance
