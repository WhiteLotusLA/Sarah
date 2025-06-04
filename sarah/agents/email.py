"""
Email agent for managing electronic communications through Microsoft 365
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import re
from email.utils import parseaddr

from sarah.agents.base import BaseAgent, MessageType, Priority
from sarah.bridges.microsoft_graph import MicrosoftGraphClient
from sarah.services.ai_service import ollama_service, ModelType

logger = logging.getLogger(__name__)


class EmailPriority(str, Enum):
    """Email priority levels"""
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    SPAM = "spam"


class EmailCategory(str, Enum):
    """Email categories for organization"""
    WORK = "work"
    PERSONAL = "personal"
    NEWSLETTER = "newsletter"
    NOTIFICATION = "notification"
    SOCIAL = "social"
    PROMOTIONAL = "promotional"
    TRANSACTION = "transaction"
    OTHER = "other"


@dataclass
class EmailMessage:
    """Represents an email message"""
    id: Optional[str] = None
    subject: str = ""
    from_address: str = ""
    from_name: Optional[str] = None
    to_addresses: List[str] = field(default_factory=list)
    cc_addresses: List[str] = field(default_factory=list)
    body_preview: str = ""
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    received_at: Optional[datetime] = None
    has_attachments: bool = False
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    importance: str = "normal"
    is_read: bool = False
    is_flagged: bool = False
    categories: List[str] = field(default_factory=list)
    conversation_id: Optional[str] = None
    
    # AI-enhanced fields
    priority: Optional[EmailPriority] = None
    category: Optional[EmailCategory] = None
    summary: Optional[str] = None
    action_required: bool = False
    action_summary: Optional[str] = None
    sentiment: Optional[str] = None


class EmailAgent(BaseAgent):
    """
    Manages email communications through Microsoft 365
    
    Capabilities:
    - Read and send emails
    - Smart categorization and prioritization
    - Automatic responses
    - Email search and filtering
    - Attachment handling
    - Conversation threading
    - Spam detection
    """
    
    def __init__(self):
        super().__init__("email", "Email Manager")
        self.graph_client: Optional[MicrosoftGraphClient] = None
        self.email_cache: Dict[str, EmailMessage] = {}
        self.conversation_cache: Dict[str, List[EmailMessage]] = {}
        self.auto_response_enabled = False
        self.spam_threshold = 0.8
        
    async def initialize(self) -> None:
        """Initialize the email agent"""
        await super().start()
        
        # Initialize Microsoft Graph client
        self.graph_client = MicrosoftGraphClient()
        await self.graph_client.initialize()
        
        # Register command handlers
        self.register_handler("get_emails", self._handle_get_emails)
        self.register_handler("send_email", self._handle_send_email)
        self.register_handler("reply_email", self._handle_reply_email)
        self.register_handler("forward_email", self._handle_forward_email)
        self.register_handler("delete_email", self._handle_delete_email)
        self.register_handler("mark_read", self._handle_mark_read)
        self.register_handler("flag_email", self._handle_flag_email)
        self.register_handler("search_emails", self._handle_search_emails)
        self.register_handler("categorize_inbox", self._handle_categorize_inbox)
        
        # Start background tasks
        asyncio.create_task(self._monitor_inbox())
        
        logger.info("📧 Email agent initialized")
        
    async def get_emails(
        self,
        folder: str = "inbox",
        limit: int = 50,
        unread_only: bool = False,
        category: Optional[EmailCategory] = None
    ) -> List[EmailMessage]:
        """Get emails from a folder with optional filters"""
        try:
            # Build filter query
            filters = []
            if unread_only:
                filters.append("isRead eq false")
            if category:
                filters.append(f"categories/any(c:c eq '{category.value}')")
                
            filter_query = " and ".join(filters) if filters else None
            
            # Fetch from Microsoft Graph
            messages_data = await self.graph_client.get_messages(
                folder, limit, filter_query
            )
            
            # Convert to EmailMessage objects
            emails = []
            for msg_data in messages_data:
                email = await self._parse_email(msg_data)
                emails.append(email)
                
                # Cache the email
                if email.id:
                    self.email_cache[email.id] = email
                    
            return emails
            
        except Exception as e:
            logger.error(f"Failed to get emails: {e}")
            raise
            
    async def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        importance: str = "normal"
    ) -> bool:
        """Send an email"""
        try:
            # Build message
            message = {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body
                },
                "toRecipients": [
                    {"emailAddress": {"address": addr}} for addr in to
                ],
                "importance": importance
            }
            
            if cc:
                message["ccRecipients"] = [
                    {"emailAddress": {"address": addr}} for addr in cc
                ]
                
            if attachments:
                # TODO: Handle attachments
                pass
                
            # Send via Microsoft Graph
            success = await self.graph_client.send_message(message)
            
            if success:
                logger.info(f"Sent email: {subject} to {', '.join(to)}")
                
            return success
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise
            
    async def reply_to_email(
        self,
        email_id: str,
        body: str,
        reply_all: bool = False
    ) -> bool:
        """Reply to an email"""
        try:
            reply_data = {
                "message": {
                    "body": {
                        "contentType": "HTML",
                        "content": body
                    }
                }
            }
            
            if reply_all:
                # TODO: Implement reply all
                pass
            else:
                success = await self.graph_client.reply_to_message(
                    email_id, reply_data
                )
                
            return success
            
        except Exception as e:
            logger.error(f"Failed to reply to email: {e}")
            raise
            
    async def categorize_email(self, email: EmailMessage) -> EmailCategory:
        """Categorize an email using AI"""
        if not ollama_service.is_available():
            return EmailCategory.OTHER
            
        prompt = f"""
        Categorize this email into one of these categories:
        - work: Work-related emails
        - personal: Personal correspondence
        - newsletter: Newsletters and subscriptions
        - notification: System notifications and alerts
        - social: Social media notifications
        - promotional: Marketing and promotional emails
        - transaction: Receipts, orders, confirmations
        - other: Doesn't fit other categories
        
        Email:
        From: {email.from_address}
        Subject: {email.subject}
        Preview: {email.body_preview[:200]}
        
        Category:"""
        
        try:
            response = await ollama_service.generate(
                prompt, ModelType.GENERAL, temperature=0.3
            )
            
            # Extract category
            category_text = response.strip().lower()
            for cat in EmailCategory:
                if cat.value in category_text:
                    return cat
                    
            return EmailCategory.OTHER
            
        except Exception as e:
            logger.error(f"Error categorizing email: {e}")
            return EmailCategory.OTHER
            
    async def prioritize_email(self, email: EmailMessage) -> EmailPriority:
        """Determine email priority using AI and rules"""
        # Rule-based priority
        if any(word in email.subject.lower() for word in ["urgent", "asap", "emergency"]):
            return EmailPriority.URGENT
            
        if email.is_flagged or email.importance == "high":
            return EmailPriority.HIGH
            
        # AI-based priority if available
        if ollama_service.is_available():
            prompt = f"""
            Determine the priority of this email (urgent/high/normal/low):
            
            From: {email.from_address}
            Subject: {email.subject}
            Preview: {email.body_preview[:200]}
            
            Consider urgency, action requirements, and importance.
            Priority:"""
            
            try:
                response = await ollama_service.generate(
                    prompt, ModelType.GENERAL, temperature=0.3
                )
                
                priority_text = response.strip().lower()
                for priority in EmailPriority:
                    if priority.value in priority_text:
                        return priority
                        
            except Exception as e:
                logger.error(f"Error prioritizing email: {e}")
                
        return EmailPriority.NORMAL
        
    async def summarize_email(self, email: EmailMessage) -> str:
        """Generate a concise summary of an email"""
        if not ollama_service.is_available():
            return email.body_preview[:100]
            
        prompt = f"""
        Summarize this email in 1-2 sentences:
        
        Subject: {email.subject}
        From: {email.from_address}
        Body: {email.body_preview[:500]}
        
        Summary:"""
        
        try:
            summary = await ollama_service.generate(
                prompt, ModelType.GENERAL, temperature=0.5
            )
            return summary.strip()
            
        except Exception as e:
            logger.error(f"Error summarizing email: {e}")
            return email.body_preview[:100]
            
    async def detect_spam(self, email: EmailMessage) -> float:
        """Detect spam probability (0-1)"""
        spam_indicators = 0
        total_checks = 0
        
        # Check subject
        spam_subject_words = ["free", "winner", "congratulations", "click here", 
                             "limited time", "act now", "100%", "guarantee"]
        for word in spam_subject_words:
            total_checks += 1
            if word in email.subject.lower():
                spam_indicators += 1
                
        # Check sender
        if email.from_address:
            total_checks += 1
            # Check for suspicious domains
            if any(x in email.from_address for x in ["noreply", "donotreply", ".tk", ".ml"]):
                spam_indicators += 1
                
        # Check body
        if email.body_preview:
            spam_body_words = ["unsubscribe", "click here", "verify account", 
                              "suspended", "winner", "prize"]
            for word in spam_body_words:
                total_checks += 1
                if word in email.body_preview.lower():
                    spam_indicators += 0.5  # Less weight for body
                    
        # Calculate spam score
        spam_score = spam_indicators / total_checks if total_checks > 0 else 0
        
        return min(spam_score, 1.0)
        
    async def generate_auto_response(self, email: EmailMessage) -> Optional[str]:
        """Generate an automatic response if appropriate"""
        if not self.auto_response_enabled or not ollama_service.is_available():
            return None
            
        # Don't auto-respond to certain emails
        if (email.category in [EmailCategory.NEWSLETTER, EmailCategory.PROMOTIONAL] or
            email.priority == EmailPriority.SPAM):
            return None
            
        prompt = f"""
        Determine if this email needs an automatic response. If yes, generate a brief, 
        professional response. If no, respond with "NO_RESPONSE".
        
        Email:
        From: {email.from_address}
        Subject: {email.subject}
        Body: {email.body_preview[:300]}
        
        Response:"""
        
        try:
            response = await ollama_service.generate(
                prompt, ModelType.GENERAL, temperature=0.7
            )
            
            if "NO_RESPONSE" not in response:
                return response.strip()
                
        except Exception as e:
            logger.error(f"Error generating auto response: {e}")
            
        return None
        
    async def _parse_email(self, msg_data: Dict[str, Any]) -> EmailMessage:
        """Parse Microsoft Graph email data into EmailMessage"""
        email = EmailMessage(
            id=msg_data.get("id"),
            subject=msg_data.get("subject", ""),
            from_address=msg_data.get("from", {}).get("emailAddress", {}).get("address", ""),
            from_name=msg_data.get("from", {}).get("emailAddress", {}).get("name"),
            to_addresses=[
                r["emailAddress"]["address"] 
                for r in msg_data.get("toRecipients", [])
            ],
            cc_addresses=[
                r["emailAddress"]["address"] 
                for r in msg_data.get("ccRecipients", [])
            ],
            body_preview=msg_data.get("bodyPreview", ""),
            received_at=datetime.fromisoformat(
                msg_data["receivedDateTime"].replace("Z", "+00:00")
            ) if msg_data.get("receivedDateTime") else None,
            has_attachments=msg_data.get("hasAttachments", False),
            importance=msg_data.get("importance", "normal"),
            is_read=msg_data.get("isRead", False),
            is_flagged=msg_data.get("flag", {}).get("flagStatus") == "flagged",
            categories=msg_data.get("categories", []),
            conversation_id=msg_data.get("conversationId")
        )
        
        # Get full body if needed
        if "body" in msg_data:
            if msg_data["body"]["contentType"] == "html":
                email.body_html = msg_data["body"]["content"]
            else:
                email.body_text = msg_data["body"]["content"]
                
        # Enhance with AI
        email.category = await self.categorize_email(email)
        email.priority = await self.prioritize_email(email)
        
        # Generate summary for important emails
        if email.priority in [EmailPriority.URGENT, EmailPriority.HIGH]:
            email.summary = await self.summarize_email(email)
            
        # Check for spam
        spam_score = await self.detect_spam(email)
        if spam_score >= self.spam_threshold:
            email.priority = EmailPriority.SPAM
            
        return email
        
    async def _monitor_inbox(self):
        """Background task to monitor inbox for new emails"""
        while self.running:
            try:
                # Check for new emails every 5 minutes
                await asyncio.sleep(300)
                
                # Get unread emails
                new_emails = await self.get_emails(unread_only=True, limit=20)
                
                for email in new_emails:
                    # Process new email
                    await self._process_new_email(email)
                    
            except Exception as e:
                logger.error(f"Error monitoring inbox: {e}")
                
    async def _process_new_email(self, email: EmailMessage):
        """Process a new email"""
        # Check if auto-response is needed
        if self.auto_response_enabled:
            response = await self.generate_auto_response(email)
            if response and email.id:
                await self.reply_to_email(email.id, response)
                
        # Notify director agent of important emails
        if email.priority in [EmailPriority.URGENT, EmailPriority.HIGH]:
            await self.send_command(
                "director",
                "email_notification",
                {
                    "email_id": email.id,
                    "from": email.from_address,
                    "subject": email.subject,
                    "priority": email.priority.value,
                    "summary": email.summary
                },
                priority=Priority.HIGH
            )
            
    # Command handlers
    async def _handle_get_emails(self, message):
        """Handle get_emails command"""
        data = message.payload
        emails = await self.get_emails(
            folder=data.get("folder", "inbox"),
            limit=data.get("limit", 50),
            unread_only=data.get("unread_only", False)
        )
        
        await self.send_command(
            message.from_agent,
            "emails_response",
            {
                "emails": [self._email_to_dict(e) for e in emails],
                "count": len(emails)
            }
        )
        
    async def _handle_send_email(self, message):
        """Handle send_email command"""
        data = message.payload
        success = await self.send_email(
            to=data["to"],
            subject=data["subject"],
            body=data["body"],
            cc=data.get("cc"),
            attachments=data.get("attachments"),
            importance=data.get("importance", "normal")
        )
        
        await self.send_command(
            message.from_agent,
            "email_sent",
            {"success": success}
        )
        
    async def _handle_reply_email(self, message):
        """Handle reply_email command"""
        data = message.payload
        success = await self.reply_to_email(
            email_id=data["email_id"],
            body=data["body"],
            reply_all=data.get("reply_all", False)
        )
        
        await self.send_command(
            message.from_agent,
            "email_replied",
            {"success": success}
        )
        
    async def _handle_forward_email(self, message):
        """Handle forward_email command"""
        # TODO: Implement email forwarding
        pass
        
    async def _handle_delete_email(self, message):
        """Handle delete_email command"""
        data = message.payload
        email_id = data["email_id"]
        
        success = await self.graph_client.delete_message(email_id)
        
        if success and email_id in self.email_cache:
            del self.email_cache[email_id]
            
        await self.send_command(
            message.from_agent,
            "email_deleted",
            {"success": success, "email_id": email_id}
        )
        
    async def _handle_mark_read(self, message):
        """Handle mark_read command"""
        # TODO: Implement mark as read
        pass
        
    async def _handle_flag_email(self, message):
        """Handle flag_email command"""
        # TODO: Implement email flagging
        pass
        
    async def _handle_search_emails(self, message):
        """Handle search_emails command"""
        data = message.payload
        query = data["query"]
        
        # TODO: Implement email search
        
    async def _handle_categorize_inbox(self, message):
        """Handle categorize_inbox command"""
        # Get all uncategorized emails
        emails = await self.get_emails(limit=100)
        
        categorized = 0
        for email in emails:
            if not email.categories:
                category = await self.categorize_email(email)
                # TODO: Update email categories in Graph API
                categorized += 1
                
        await self.send_command(
            message.from_agent,
            "inbox_categorized",
            {"count": categorized}
        )
        
    def _email_to_dict(self, email: EmailMessage) -> Dict[str, Any]:
        """Convert EmailMessage to dictionary for responses"""
        return {
            "id": email.id,
            "subject": email.subject,
            "from_address": email.from_address,
            "from_name": email.from_name,
            "to_addresses": email.to_addresses,
            "cc_addresses": email.cc_addresses,
            "body_preview": email.body_preview,
            "received_at": email.received_at.isoformat() if email.received_at else None,
            "has_attachments": email.has_attachments,
            "importance": email.importance,
            "is_read": email.is_read,
            "is_flagged": email.is_flagged,
            "categories": email.categories,
            "priority": email.priority.value if email.priority else None,
            "category": email.category.value if email.category else None,
            "summary": email.summary,
            "action_required": email.action_required
        }