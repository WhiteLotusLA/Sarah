"""
Calendar Agent - Manages schedules and calendar events via Microsoft 365
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import json

from sarah.agents.base import BaseAgent, AgentMessage
from sarah.bridges.microsoft_graph import MicrosoftGraphClient

logger = logging.getLogger(__name__)


@dataclass
class CalendarEvent:
    """Represents a calendar event"""
    id: Optional[str] = None
    subject: str = ""
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    location: Optional[str] = None
    body: Optional[str] = None
    attendees: List[str] = None
    is_all_day: bool = False
    reminder_minutes: int = 15
    categories: List[str] = None
    importance: str = "normal"  # low, normal, high
    is_recurring: bool = False
    recurrence_pattern: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.attendees is None:
            self.attendees = []
        if self.categories is None:
            self.categories = []
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls"""
        return {
            'subject': self.subject,
            'start': {
                'dateTime': self.start.isoformat() if self.start else None,
                'timeZone': 'UTC'
            },
            'end': {
                'dateTime': self.end.isoformat() if self.end else None,
                'timeZone': 'UTC'
            },
            'location': {'displayName': self.location} if self.location else None,
            'body': {
                'contentType': 'text',
                'content': self.body or ''
            },
            'attendees': [{'emailAddress': {'address': email}} for email in self.attendees],
            'isAllDay': self.is_all_day,
            'reminderMinutesBeforeStart': self.reminder_minutes,
            'categories': self.categories,
            'importance': self.importance
        }


class CalendarAgent(BaseAgent):
    """
    Manages calendar and scheduling through Microsoft 365
    
    Capabilities:
    - View and manage calendar events
    - Schedule meetings
    - Find available time slots
    - Set reminders
    - Handle recurring events
    - Manage multiple calendars
    """
    
    def __init__(self):
        super().__init__("calendar", "Calendar Manager")
        self.graph_client: Optional[MicrosoftGraphClient] = None
        self.calendar_cache: Dict[str, List[CalendarEvent]] = {}
        self.default_calendar_id = "primary"
        
    async def initialize(self) -> None:
        """Initialize the calendar agent"""
        await super().start()
        
        # Initialize Microsoft Graph client
        self.graph_client = MicrosoftGraphClient()
        await self.graph_client.initialize()
        
        # Register command handlers
        self.register_handler("get_events", self._handle_get_events)
        self.register_handler("create_event", self._handle_create_event)
        self.register_handler("update_event", self._handle_update_event)
        self.register_handler("delete_event", self._handle_delete_event)
        self.register_handler("find_free_time", self._handle_find_free_time)
        self.register_handler("get_upcoming", self._handle_get_upcoming)
        self.register_handler("search_events", self._handle_search_events)
        
        logger.info("📅 Calendar agent initialized")
        
    async def get_events(self, start_date: datetime, end_date: datetime,
                        calendar_id: Optional[str] = None) -> List[CalendarEvent]:
        """Get calendar events within a date range"""
        calendar_id = calendar_id or self.default_calendar_id
        
        try:
            # Check cache first
            cache_key = f"{calendar_id}:{start_date.date()}:{end_date.date()}"
            if cache_key in self.calendar_cache:
                logger.debug(f"Returning cached events for {cache_key}")
                return self.calendar_cache[cache_key]
            
            # Fetch from Microsoft Graph
            events_data = await self.graph_client.get_calendar_events(
                calendar_id, start_date, end_date
            )
            
            # Convert to CalendarEvent objects
            events = []
            for event_data in events_data:
                event = self._parse_event(event_data)
                events.append(event)
                
            # Cache the results
            self.calendar_cache[cache_key] = events
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get calendar events: {e}")
            raise
            
    async def create_event(self, event: CalendarEvent, 
                         calendar_id: Optional[str] = None) -> CalendarEvent:
        """Create a new calendar event"""
        calendar_id = calendar_id or self.default_calendar_id
        
        try:
            # Convert to API format
            event_data = event.to_dict()
            
            # Create via Microsoft Graph
            created_data = await self.graph_client.create_calendar_event(
                calendar_id, event_data
            )
            
            # Parse the created event
            created_event = self._parse_event(created_data)
            
            # Invalidate cache
            self._invalidate_cache(calendar_id)
            
            logger.info(f"Created calendar event: {created_event.subject}")
            return created_event
            
        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}")
            raise
            
    async def update_event(self, event_id: str, updates: Dict[str, Any],
                         calendar_id: Optional[str] = None) -> CalendarEvent:
        """Update an existing calendar event"""
        calendar_id = calendar_id or self.default_calendar_id
        
        try:
            # Update via Microsoft Graph
            updated_data = await self.graph_client.update_calendar_event(
                calendar_id, event_id, updates
            )
            
            # Parse the updated event
            updated_event = self._parse_event(updated_data)
            
            # Invalidate cache
            self._invalidate_cache(calendar_id)
            
            logger.info(f"Updated calendar event: {updated_event.subject}")
            return updated_event
            
        except Exception as e:
            logger.error(f"Failed to update calendar event: {e}")
            raise
            
    async def delete_event(self, event_id: str, calendar_id: Optional[str] = None) -> bool:
        """Delete a calendar event"""
        calendar_id = calendar_id or self.default_calendar_id
        
        try:
            # Delete via Microsoft Graph
            success = await self.graph_client.delete_calendar_event(
                calendar_id, event_id
            )
            
            if success:
                # Invalidate cache
                self._invalidate_cache(calendar_id)
                logger.info(f"Deleted calendar event: {event_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete calendar event: {e}")
            raise
            
    async def find_free_time(self, duration_minutes: int,
                           search_start: datetime,
                           search_end: datetime,
                           attendees: List[str] = None) -> List[Tuple[datetime, datetime]]:
        """Find available time slots"""
        try:
            # Get all events in the search period
            events = await self.get_events(search_start, search_end)
            
            # Sort events by start time
            events.sort(key=lambda e: e.start)
            
            # Find free slots
            free_slots = []
            current_time = search_start
            
            for event in events:
                # Check if there's a gap before this event
                if event.start > current_time:
                    gap_duration = (event.start - current_time).total_seconds() / 60
                    if gap_duration >= duration_minutes:
                        free_slots.append((current_time, event.start))
                        
                # Update current time to end of this event
                current_time = max(current_time, event.end)
                
            # Check if there's time after the last event
            if current_time < search_end:
                gap_duration = (search_end - current_time).total_seconds() / 60
                if gap_duration >= duration_minutes:
                    free_slots.append((current_time, search_end))
                    
            # If attendees specified, check their availability too
            if attendees and self.graph_client:
                # This would require checking other people's calendars
                # Implementation depends on permissions
                pass
                
            return free_slots
            
        except Exception as e:
            logger.error(f"Failed to find free time: {e}")
            raise
            
    async def get_upcoming_events(self, hours: int = 24, limit: int = 10) -> List[CalendarEvent]:
        """Get upcoming events"""
        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=hours)
        
        events = await self.get_events(start, end)
        events.sort(key=lambda e: e.start)
        
        return events[:limit]
        
    async def search_events(self, query: str, days_back: int = 30, 
                          days_forward: int = 30) -> List[CalendarEvent]:
        """Search for events by text"""
        start = datetime.now(timezone.utc) - timedelta(days=days_back)
        end = datetime.now(timezone.utc) + timedelta(days=days_forward)
        
        all_events = await self.get_events(start, end)
        
        # Filter events that match the query
        query_lower = query.lower()
        matching_events = []
        
        for event in all_events:
            if (query_lower in event.subject.lower() or
                (event.body and query_lower in event.body.lower()) or
                (event.location and query_lower in event.location.lower())):
                matching_events.append(event)
                
        return matching_events
        
    def _parse_event(self, event_data: Dict[str, Any]) -> CalendarEvent:
        """Parse Microsoft Graph event data into CalendarEvent"""
        return CalendarEvent(
            id=event_data.get('id'),
            subject=event_data.get('subject', ''),
            start=datetime.fromisoformat(event_data['start']['dateTime'].replace('Z', '+00:00'))
                  if event_data.get('start') else None,
            end=datetime.fromisoformat(event_data['end']['dateTime'].replace('Z', '+00:00'))
                if event_data.get('end') else None,
            location=event_data.get('location', {}).get('displayName'),
            body=event_data.get('body', {}).get('content'),
            attendees=[att['emailAddress']['address'] 
                      for att in event_data.get('attendees', [])],
            is_all_day=event_data.get('isAllDay', False),
            reminder_minutes=event_data.get('reminderMinutesBeforeStart', 15),
            categories=event_data.get('categories', []),
            importance=event_data.get('importance', 'normal'),
            is_recurring=event_data.get('recurrence') is not None,
            recurrence_pattern=event_data.get('recurrence')
        )
        
    def _invalidate_cache(self, calendar_id: str) -> None:
        """Invalidate cache for a calendar"""
        keys_to_remove = [k for k in self.calendar_cache.keys() 
                         if k.startswith(f"{calendar_id}:")]
        for key in keys_to_remove:
            del self.calendar_cache[key]
            
    # Command handlers
    async def _handle_get_events(self, message: AgentMessage) -> None:
        """Handle get_events command"""
        data = message.data
        start = datetime.fromisoformat(data['start'])
        end = datetime.fromisoformat(data['end'])
        calendar_id = data.get('calendar_id')
        
        events = await self.get_events(start, end, calendar_id)
        
        # Send response
        await self.send_message(
            message.from_agent,
            "events_response",
            {
                'events': [self._event_to_dict(e) for e in events],
                'count': len(events)
            }
        )
        
    async def _handle_create_event(self, message: AgentMessage) -> None:
        """Handle create_event command"""
        event_data = message.data['event']
        calendar_id = message.data.get('calendar_id')
        
        # Create CalendarEvent from data
        event = CalendarEvent(**event_data)
        
        created = await self.create_event(event, calendar_id)
        
        # Send response
        await self.send_message(
            message.from_agent,
            "event_created",
            {'event': self._event_to_dict(created)}
        )
        
    async def _handle_update_event(self, message: AgentMessage) -> None:
        """Handle update_event command"""
        event_id = message.data['event_id']
        updates = message.data['updates']
        calendar_id = message.data.get('calendar_id')
        
        updated = await self.update_event(event_id, updates, calendar_id)
        
        # Send response
        await self.send_message(
            message.from_agent,
            "event_updated",
            {'event': self._event_to_dict(updated)}
        )
        
    async def _handle_delete_event(self, message: AgentMessage) -> None:
        """Handle delete_event command"""
        event_id = message.data['event_id']
        calendar_id = message.data.get('calendar_id')
        
        success = await self.delete_event(event_id, calendar_id)
        
        # Send response
        await self.send_message(
            message.from_agent,
            "event_deleted",
            {'success': success, 'event_id': event_id}
        )
        
    async def _handle_find_free_time(self, message: AgentMessage) -> None:
        """Handle find_free_time command"""
        duration = message.data['duration_minutes']
        start = datetime.fromisoformat(message.data['search_start'])
        end = datetime.fromisoformat(message.data['search_end'])
        attendees = message.data.get('attendees', [])
        
        free_slots = await self.find_free_time(duration, start, end, attendees)
        
        # Send response
        await self.send_message(
            message.from_agent,
            "free_time_response",
            {
                'slots': [(s.isoformat(), e.isoformat()) for s, e in free_slots],
                'count': len(free_slots)
            }
        )
        
    async def _handle_get_upcoming(self, message: AgentMessage) -> None:
        """Handle get_upcoming command"""
        hours = message.data.get('hours', 24)
        limit = message.data.get('limit', 10)
        
        events = await self.get_upcoming_events(hours, limit)
        
        # Send response
        await self.send_message(
            message.from_agent,
            "upcoming_events",
            {
                'events': [self._event_to_dict(e) for e in events],
                'count': len(events)
            }
        )
        
    async def _handle_search_events(self, message: AgentMessage) -> None:
        """Handle search_events command"""
        query = message.data['query']
        days_back = message.data.get('days_back', 30)
        days_forward = message.data.get('days_forward', 30)
        
        events = await self.search_events(query, days_back, days_forward)
        
        # Send response
        await self.send_message(
            message.from_agent,
            "search_results",
            {
                'events': [self._event_to_dict(e) for e in events],
                'count': len(events),
                'query': query
            }
        )
        
    def _event_to_dict(self, event: CalendarEvent) -> Dict[str, Any]:
        """Convert CalendarEvent to dictionary for responses"""
        return {
            'id': event.id,
            'subject': event.subject,
            'start': event.start.isoformat() if event.start else None,
            'end': event.end.isoformat() if event.end else None,
            'location': event.location,
            'body': event.body,
            'attendees': event.attendees,
            'is_all_day': event.is_all_day,
            'reminder_minutes': event.reminder_minutes,
            'categories': event.categories,
            'importance': event.importance,
            'is_recurring': event.is_recurring
        }