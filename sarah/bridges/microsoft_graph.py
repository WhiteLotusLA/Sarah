"""
Microsoft Graph API client for Office 365 integration
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import aiohttp
from msal import ConfidentialClientApplication
import os

from sarah.config import Config
from sarah.sanctuary.encryption import get_encryptor

logger = logging.getLogger(__name__)


class MicrosoftGraphClient:
    """
    Client for interacting with Microsoft Graph API
    
    Handles:
    - Authentication via MSAL
    - Calendar operations
    - Email operations
    - OneDrive operations
    - User profile access
    """
    
    def __init__(self):
        self.tenant_id = os.getenv('MICROSOFT_TENANT_ID')
        self.client_id = os.getenv('MICROSOFT_CLIENT_ID')
        self.client_secret = os.getenv('MICROSOFT_CLIENT_SECRET')
        self.redirect_uri = os.getenv('MICROSOFT_REDIRECT_URI', 'http://localhost:8001/auth/callback')
        
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.access_token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        self.msal_app: Optional[ConfidentialClientApplication] = None
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Scopes required for operations
        self.scopes = [
            "https://graph.microsoft.com/Calendars.ReadWrite",
            "https://graph.microsoft.com/Mail.ReadWrite",
            "https://graph.microsoft.com/Files.ReadWrite",
            "https://graph.microsoft.com/User.Read"
        ]
        
    async def initialize(self) -> None:
        """Initialize the Graph client"""
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            logger.warning("Microsoft Graph credentials not configured")
            return
            
        # Create MSAL app
        self.msal_app = ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret
        )
        
        # Create aiohttp session
        self.session = aiohttp.ClientSession()
        
        logger.info("Microsoft Graph client initialized")
        
    async def close(self) -> None:
        """Close the client session"""
        if self.session:
            await self.session.close()
            
    async def _ensure_token(self) -> str:
        """Ensure we have a valid access token"""
        if self.access_token and self.token_expires and datetime.now(timezone.utc) < self.token_expires:
            return self.access_token
            
        # Acquire new token
        result = await asyncio.to_thread(
            self.msal_app.acquire_token_for_client,
            scopes=self.scopes
        )
        
        if "access_token" in result:
            self.access_token = result["access_token"]
            # Token typically expires in 1 hour
            self.token_expires = datetime.now(timezone.utc).replace(hour=datetime.now().hour + 1)
            logger.debug("Acquired new access token")
            return self.access_token
        else:
            error = result.get("error", "Unknown error")
            error_desc = result.get("error_description", "")
            raise Exception(f"Failed to acquire token: {error} - {error_desc}")
            
    async def _make_request(self, method: str, endpoint: str, 
                          data: Optional[Dict[str, Any]] = None,
                          params: Optional[Dict[str, Any]] = None) -> Any:
        """Make an authenticated request to Graph API"""
        token = await self._ensure_token()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{endpoint}"
        
        async with self.session.request(
            method, url, headers=headers, json=data, params=params
        ) as response:
            if response.status == 204:  # No content
                return True
                
            response_data = await response.json()
            
            if response.status >= 400:
                error = response_data.get("error", {})
                error_msg = error.get("message", "Unknown error")
                logger.error(f"Graph API error: {error_msg}")
                raise Exception(f"Graph API error: {error_msg}")
                
            return response_data
            
    # Calendar operations
    async def get_calendars(self) -> List[Dict[str, Any]]:
        """Get list of user's calendars"""
        response = await self._make_request("GET", "/me/calendars")
        return response.get("value", [])
        
    async def get_calendar_events(self, calendar_id: str, 
                                start_time: datetime, 
                                end_time: datetime) -> List[Dict[str, Any]]:
        """Get calendar events within a time range"""
        # Format datetime for Graph API
        start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S")
        end_str = end_time.strftime("%Y-%m-%dT%H:%M:%S")
        
        params = {
            "$filter": f"start/dateTime ge '{start_str}' and end/dateTime le '{end_str}'",
            "$orderby": "start/dateTime",
            "$top": 100
        }
        
        if calendar_id == "primary":
            endpoint = "/me/events"
        else:
            endpoint = f"/me/calendars/{calendar_id}/events"
            
        response = await self._make_request("GET", endpoint, params=params)
        return response.get("value", [])
        
    async def create_calendar_event(self, calendar_id: str, 
                                  event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new calendar event"""
        if calendar_id == "primary":
            endpoint = "/me/events"
        else:
            endpoint = f"/me/calendars/{calendar_id}/events"
            
        return await self._make_request("POST", endpoint, data=event_data)
        
    async def update_calendar_event(self, calendar_id: str, event_id: str,
                                  updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing calendar event"""
        if calendar_id == "primary":
            endpoint = f"/me/events/{event_id}"
        else:
            endpoint = f"/me/calendars/{calendar_id}/events/{event_id}"
            
        return await self._make_request("PATCH", endpoint, data=updates)
        
    async def delete_calendar_event(self, calendar_id: str, event_id: str) -> bool:
        """Delete a calendar event"""
        if calendar_id == "primary":
            endpoint = f"/me/events/{event_id}"
        else:
            endpoint = f"/me/calendars/{calendar_id}/events/{event_id}"
            
        return await self._make_request("DELETE", endpoint)
        
    # Email operations
    async def get_messages(self, folder: str = "inbox", 
                         limit: int = 50,
                         filter_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get email messages"""
        params = {
            "$top": limit,
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,toRecipients,receivedDateTime,bodyPreview,hasAttachments"
        }
        
        if filter_query:
            params["$filter"] = filter_query
            
        endpoint = f"/me/mailFolders/{folder}/messages"
        response = await self._make_request("GET", endpoint, params=params)
        return response.get("value", [])
        
    async def get_message(self, message_id: str) -> Dict[str, Any]:
        """Get a specific email message"""
        endpoint = f"/me/messages/{message_id}"
        params = {"$expand": "attachments"}
        return await self._make_request("GET", endpoint, params=params)
        
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """Send an email message"""
        endpoint = "/me/sendMail"
        data = {"message": message}
        return await self._make_request("POST", endpoint, data=data)
        
    async def reply_to_message(self, message_id: str, reply: Dict[str, Any]) -> bool:
        """Reply to an email message"""
        endpoint = f"/me/messages/{message_id}/reply"
        return await self._make_request("POST", endpoint, data=reply)
        
    async def move_message(self, message_id: str, destination_folder: str) -> Dict[str, Any]:
        """Move a message to another folder"""
        endpoint = f"/me/messages/{message_id}/move"
        data = {"destinationId": destination_folder}
        return await self._make_request("POST", endpoint, data=data)
        
    async def delete_message(self, message_id: str) -> bool:
        """Delete an email message"""
        endpoint = f"/me/messages/{message_id}"
        return await self._make_request("DELETE", endpoint)
        
    # User profile operations
    async def get_user_profile(self) -> Dict[str, Any]:
        """Get the current user's profile"""
        return await self._make_request("GET", "/me")
        
    async def get_user_photo(self) -> Optional[bytes]:
        """Get the user's profile photo"""
        try:
            # This returns binary data, so we need special handling
            token = await self._ensure_token()
            headers = {"Authorization": f"Bearer {token}"}
            
            async with self.session.get(
                f"{self.base_url}/me/photo/$value",
                headers=headers
            ) as response:
                if response.status == 200:
                    return await response.read()
                return None
        except Exception as e:
            logger.warning(f"Failed to get user photo: {e}")
            return None
            
    # OneDrive operations
    async def list_drive_items(self, folder_path: str = "/") -> List[Dict[str, Any]]:
        """List items in OneDrive folder"""
        if folder_path == "/":
            endpoint = "/me/drive/root/children"
        else:
            endpoint = f"/me/drive/root:/{folder_path}:/children"
            
        response = await self._make_request("GET", endpoint)
        return response.get("value", [])
        
    async def upload_file(self, file_path: str, content: bytes, 
                        folder_path: str = "/") -> Dict[str, Any]:
        """Upload a file to OneDrive"""
        if folder_path == "/":
            endpoint = f"/me/drive/root:/{file_path}:/content"
        else:
            endpoint = f"/me/drive/root:/{folder_path}/{file_path}:/content"
            
        # For file upload, we need to use PUT with binary data
        token = await self._ensure_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream"
        }
        
        async with self.session.put(
            f"{self.base_url}{endpoint}",
            headers=headers,
            data=content
        ) as response:
            return await response.json()
            
    async def download_file(self, file_id: str) -> bytes:
        """Download a file from OneDrive"""
        endpoint = f"/me/drive/items/{file_id}/content"
        
        token = await self._ensure_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        async with self.session.get(
            f"{self.base_url}{endpoint}",
            headers=headers
        ) as response:
            return await response.read()
            
    async def delete_file(self, file_id: str) -> bool:
        """Delete a file from OneDrive"""
        endpoint = f"/me/drive/items/{file_id}"
        return await self._make_request("DELETE", endpoint)
        
    # Authentication helpers
    def get_auth_url(self, state: str) -> str:
        """Get the OAuth2 authorization URL"""
        auth_url = self.msal_app.get_authorization_request_url(
            self.scopes,
            state=state,
            redirect_uri=self.redirect_uri
        )
        return auth_url
        
    async def acquire_token_by_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        result = await asyncio.to_thread(
            self.msal_app.acquire_token_by_authorization_code,
            code,
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )
        
        if "access_token" in result:
            # Store the token
            self.access_token = result["access_token"]
            self.token_expires = datetime.now(timezone.utc).replace(
                hour=datetime.now().hour + 1
            )
            
            # Encrypt and store refresh token if available
            if "refresh_token" in result:
                encryptor = get_encryptor()
                encrypted_token = encryptor.encrypt(result["refresh_token"])
                # Store this securely - implementation depends on your storage
                
        return result