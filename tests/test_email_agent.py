"""
Test suite for the Email Agent
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
import json

from sarah.agents.email import (
    EmailAgent, EmailMessage, EmailPriority, 
    EmailCategory
)


@pytest.fixture
def email_agent():
    """Create an EmailAgent instance for testing"""
    agent = EmailAgent()
    agent.graph_client = Mock()
    agent.redis = AsyncMock()
    return agent


@pytest.fixture
def sample_email_data():
    """Sample email data from Microsoft Graph"""
    return {
        "id": "AAMkAGI2THVSAAA=",
        "subject": "Important Project Update",
        "from": {
            "emailAddress": {
                "address": "john.doe@example.com",
                "name": "John Doe"
            }
        },
        "toRecipients": [{
            "emailAddress": {
                "address": "sarah.user@example.com",
                "name": "Sarah User"
            }
        }],
        "ccRecipients": [],
        "bodyPreview": "Hi team, I wanted to provide an update on our project...",
        "body": {
            "contentType": "html",
            "content": "<html><body>Hi team, I wanted to provide an update...</body></html>"
        },
        "receivedDateTime": "2024-01-15T14:30:00Z",
        "hasAttachments": False,
        "importance": "high",
        "isRead": False,
        "flag": {"flagStatus": "notFlagged"},
        "categories": [],
        "conversationId": "AAQkAGI2THVSAAA="
    }


@pytest.fixture
def sample_email_message():
    """Sample EmailMessage object"""
    return EmailMessage(
        id="test-123",
        subject="Test Email",
        from_address="sender@example.com",
        from_name="Test Sender",
        to_addresses=["recipient@example.com"],
        body_preview="This is a test email",
        received_at=datetime.now(timezone.utc),
        importance="normal",
        is_read=False
    )


@pytest.mark.asyncio
async def test_email_agent_initialization(email_agent):
    """Test EmailAgent initialization"""
    assert email_agent.name == "email"
    assert email_agent.agent_type == "Email Manager"
    assert email_agent.auto_response_enabled is False
    assert email_agent.spam_threshold == 0.8


@pytest.mark.asyncio
async def test_parse_email(email_agent, sample_email_data):
    """Test parsing Microsoft Graph email data"""
    # Mock AI methods
    email_agent.categorize_email = AsyncMock(return_value=EmailCategory.WORK)
    email_agent.prioritize_email = AsyncMock(return_value=EmailPriority.HIGH)
    email_agent.summarize_email = AsyncMock(return_value="Project update summary")
    email_agent.detect_spam = AsyncMock(return_value=0.1)
    
    # Parse email
    email = await email_agent._parse_email(sample_email_data)
    
    assert email.id == "AAMkAGI2THVSAAA="
    assert email.subject == "Important Project Update"
    assert email.from_address == "john.doe@example.com"
    assert email.from_name == "John Doe"
    assert email.to_addresses == ["sarah.user@example.com"]
    assert email.importance == "high"
    assert email.is_read is False
    assert email.category == EmailCategory.WORK
    assert email.priority == EmailPriority.HIGH
    assert email.summary == "Project update summary"


@pytest.mark.asyncio
async def test_get_emails(email_agent):
    """Test getting emails"""
    # Mock Graph client response
    email_agent.graph_client.get_messages = AsyncMock(return_value=[
        {
            "id": "1",
            "subject": "Email 1",
            "from": {"emailAddress": {"address": "test1@example.com"}},
            "bodyPreview": "Test email 1",
            "receivedDateTime": "2024-01-15T10:00:00Z",
            "isRead": False
        },
        {
            "id": "2", 
            "subject": "Email 2",
            "from": {"emailAddress": {"address": "test2@example.com"}},
            "bodyPreview": "Test email 2",
            "receivedDateTime": "2024-01-15T11:00:00Z",
            "isRead": True
        }
    ])
    
    # Mock AI methods
    email_agent.categorize_email = AsyncMock(return_value=EmailCategory.OTHER)
    email_agent.prioritize_email = AsyncMock(return_value=EmailPriority.NORMAL)
    email_agent.detect_spam = AsyncMock(return_value=0.1)
    
    # Get emails
    emails = await email_agent.get_emails(limit=10, unread_only=True)
    
    # Verify Graph client called correctly
    email_agent.graph_client.get_messages.assert_called_once_with(
        "inbox", 10, "isRead eq false"
    )
    
    assert len(emails) == 2
    assert all(isinstance(e, EmailMessage) for e in emails)
    assert emails[0].subject == "Email 1"
    assert emails[1].subject == "Email 2"


@pytest.mark.asyncio
async def test_send_email(email_agent):
    """Test sending an email"""
    # Mock Graph client
    email_agent.graph_client.send_message = AsyncMock(return_value=True)
    
    # Send email
    success = await email_agent.send_email(
        to=["recipient@example.com"],
        subject="Test Email",
        body="<p>This is a test</p>",
        cc=["cc@example.com"],
        importance="high"
    )
    
    assert success is True
    
    # Verify Graph client called correctly
    email_agent.graph_client.send_message.assert_called_once()
    call_args = email_agent.graph_client.send_message.call_args[0][0]
    assert call_args["subject"] == "Test Email"
    assert call_args["importance"] == "high"
    assert len(call_args["toRecipients"]) == 1
    assert len(call_args["ccRecipients"]) == 1


@pytest.mark.asyncio
async def test_categorize_email(email_agent, sample_email_message):
    """Test email categorization"""
    # Test rule-based categorization
    work_email = EmailMessage(
        subject="Meeting agenda",
        from_address="boss@company.com",
        body_preview="Please review the attached agenda for tomorrow's meeting"
    )
    
    # Mock AI service not available
    with patch('sarah.agents.email.ollama_service') as mock_ollama:
        mock_ollama.is_available.return_value = False
        
        category = await email_agent.categorize_email(work_email)
        assert category == EmailCategory.OTHER
    
    # Test AI-based categorization
    with patch('sarah.agents.email.ollama_service') as mock_ollama:
        mock_ollama.is_available.return_value = True
        mock_ollama.generate = AsyncMock(return_value="work")
        
        category = await email_agent.categorize_email(work_email)
        assert category == EmailCategory.WORK


@pytest.mark.asyncio
async def test_prioritize_email(email_agent):
    """Test email prioritization"""
    # Test urgent keyword detection
    urgent_email = EmailMessage(
        subject="URGENT: Server is down!",
        from_address="alerts@company.com",
        body_preview="The production server is experiencing issues"
    )
    
    priority = await email_agent.prioritize_email(urgent_email)
    assert priority == EmailPriority.URGENT
    
    # Test flagged email
    flagged_email = EmailMessage(
        subject="Please review",
        from_address="colleague@company.com",
        is_flagged=True
    )
    
    priority = await email_agent.prioritize_email(flagged_email)
    assert priority == EmailPriority.HIGH
    
    # Test normal email
    normal_email = EmailMessage(
        subject="Weekly newsletter",
        from_address="newsletter@example.com"
    )
    
    with patch('sarah.agents.email.ollama_service') as mock_ollama:
        mock_ollama.is_available.return_value = False
        
        priority = await email_agent.prioritize_email(normal_email)
        assert priority == EmailPriority.NORMAL


@pytest.mark.asyncio
async def test_detect_spam(email_agent):
    """Test spam detection"""
    # High spam probability email
    spam_email = EmailMessage(
        subject="You've won $1000000! Click here now!",
        from_address="noreply@suspicious.tk",
        body_preview="Congratulations! Click here to claim your prize. Act now!"
    )
    
    spam_score = await email_agent.detect_spam(spam_email)
    assert spam_score > 0.5
    
    # Low spam probability email
    normal_email = EmailMessage(
        subject="Project update",
        from_address="colleague@company.com",
        body_preview="Here's the latest update on our project progress"
    )
    
    spam_score = await email_agent.detect_spam(normal_email)
    assert spam_score < 0.3


@pytest.mark.asyncio
async def test_summarize_email(email_agent, sample_email_message):
    """Test email summarization"""
    # Test with AI available
    with patch('sarah.agents.email.ollama_service') as mock_ollama:
        mock_ollama.is_available.return_value = True
        mock_ollama.generate = AsyncMock(
            return_value="Project update with new timeline and deliverables"
        )
        
        summary = await email_agent.summarize_email(sample_email_message)
        assert summary == "Project update with new timeline and deliverables"
    
    # Test without AI
    with patch('sarah.agents.email.ollama_service') as mock_ollama:
        mock_ollama.is_available.return_value = False
        
        summary = await email_agent.summarize_email(sample_email_message)
        assert summary == sample_email_message.body_preview[:100]


@pytest.mark.asyncio
async def test_reply_to_email(email_agent):
    """Test replying to an email"""
    # Mock Graph client
    email_agent.graph_client.reply_to_message = AsyncMock(return_value=True)
    
    # Reply to email
    success = await email_agent.reply_to_email(
        email_id="test-123",
        body="Thanks for the update!",
        reply_all=False
    )
    
    assert success is True
    email_agent.graph_client.reply_to_message.assert_called_once()


@pytest.mark.asyncio
async def test_generate_auto_response(email_agent, sample_email_message):
    """Test auto-response generation"""
    email_agent.auto_response_enabled = True
    
    # Test with AI available
    with patch('sarah.agents.email.ollama_service') as mock_ollama:
        mock_ollama.is_available.return_value = True
        mock_ollama.generate = AsyncMock(
            return_value="Thank you for your email. I'll review this and get back to you soon."
        )
        
        sample_email_message.category = EmailCategory.WORK
        sample_email_message.priority = EmailPriority.NORMAL
        
        response = await email_agent.generate_auto_response(sample_email_message)
        assert response == "Thank you for your email. I'll review this and get back to you soon."
    
    # Test with spam email (should not auto-respond)
    sample_email_message.priority = EmailPriority.SPAM
    response = await email_agent.generate_auto_response(sample_email_message)
    assert response is None
    
    # Test with newsletter (should not auto-respond)
    sample_email_message.priority = EmailPriority.NORMAL
    sample_email_message.category = EmailCategory.NEWSLETTER
    response = await email_agent.generate_auto_response(sample_email_message)
    assert response is None


@pytest.mark.asyncio
async def test_process_new_email(email_agent, sample_email_message):
    """Test processing new emails"""
    email_agent.auto_response_enabled = True
    email_agent.generate_auto_response = AsyncMock(
        return_value="Thanks for your message"
    )
    email_agent.reply_to_email = AsyncMock(return_value=True)
    email_agent.send_command = AsyncMock()
    
    # Test with high priority email
    sample_email_message.priority = EmailPriority.HIGH
    sample_email_message.summary = "Important update"
    
    await email_agent._process_new_email(sample_email_message)
    
    # Should generate auto-response
    email_agent.generate_auto_response.assert_called_once_with(sample_email_message)
    email_agent.reply_to_email.assert_called_once()
    
    # Should notify director for high priority
    email_agent.send_command.assert_called_once()
    call_args = email_agent.send_command.call_args
    assert call_args[0][0] == "director"
    assert call_args[0][1] == "email_notification"


@pytest.mark.asyncio
async def test_email_caching(email_agent, sample_email_data):
    """Test email caching"""
    # Mock methods
    email_agent.graph_client.get_messages = AsyncMock(
        return_value=[sample_email_data]
    )
    email_agent.categorize_email = AsyncMock(return_value=EmailCategory.WORK)
    email_agent.prioritize_email = AsyncMock(return_value=EmailPriority.NORMAL)
    email_agent.detect_spam = AsyncMock(return_value=0.1)
    
    # Get emails
    emails = await email_agent.get_emails()
    
    # Check cache
    assert len(email_agent.email_cache) == 1
    assert "AAMkAGI2THVSAAA=" in email_agent.email_cache
    cached_email = email_agent.email_cache["AAMkAGI2THVSAAA="]
    assert cached_email.subject == "Important Project Update"