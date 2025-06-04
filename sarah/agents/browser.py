"""
Browser agent for web automation and data extraction
"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import base64
import re
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright.async_api import TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

from sarah.agents.base import BaseAgent, MessageType, Priority
from sarah.services.ai_service import ollama_service, ModelType

logger = logging.getLogger(__name__)


class BrowserActionType(str, Enum):
    """Types of browser actions"""
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    EXTRACT = "extract"
    SCROLL = "scroll"
    HOVER = "hover"
    SUBMIT = "submit"


@dataclass
class BrowserAction:
    """Represents a browser action"""
    action_type: BrowserActionType
    selector: Optional[str] = None
    value: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None


@dataclass
class WebElement:
    """Represents a web element"""
    tag: str
    text: Optional[str] = None
    attributes: Dict[str, str] = field(default_factory=dict)
    selector: str = ""
    children_count: int = 0
    is_visible: bool = True
    is_interactive: bool = False


@dataclass
class WebPageInfo:
    """Information about a web page"""
    url: str
    title: str
    description: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    forms: List[Dict[str, Any]] = field(default_factory=list)
    links: List[Dict[str, str]] = field(default_factory=list)
    images: List[Dict[str, str]] = field(default_factory=list)
    text_content: str = ""
    structured_data: Dict[str, Any] = field(default_factory=dict)


class BrowserAgent(BaseAgent):
    """
    Manages web browser automation and data extraction
    
    Capabilities:
    - Web page navigation and interaction
    - Form filling and submission
    - Data extraction and scraping
    - Screenshot capture
    - Multi-tab management
    - Cookie and session handling
    - JavaScript execution
    - Smart element detection
    """
    
    def __init__(self):
        super().__init__("browser", "Browser Automation")
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        self.default_timeout = 30000  # 30 seconds
        self.headless = True
        self.user_data_dir = Path.home() / ".sarah" / "browser_data"
        
    async def initialize(self) -> None:
        """Initialize the browser agent"""
        await super().start()
        
        # Create user data directory
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Start Playwright
        self.playwright = await async_playwright().start()
        
        # Launch browser
        await self._launch_browser()
        
        # Register command handlers
        self.register_handler("navigate", self._handle_navigate)
        self.register_handler("click", self._handle_click)
        self.register_handler("type", self._handle_type)
        self.register_handler("extract", self._handle_extract)
        self.register_handler("screenshot", self._handle_screenshot)
        self.register_handler("execute_script", self._handle_execute_script)
        self.register_handler("fill_form", self._handle_fill_form)
        self.register_handler("get_page_info", self._handle_get_page_info)
        self.register_handler("search_web", self._handle_search_web)
        
        logger.info("🌐 Browser agent initialized")
        
    async def shutdown(self) -> None:
        """Cleanup browser resources"""
        # Close all pages
        for page in self.pages.values():
            await page.close()
            
        # Close all contexts
        for context in self.contexts.values():
            await context.close()
            
        # Close browser
        if self.browser:
            await self.browser.close()
            
        # Stop Playwright
        if self.playwright:
            await self.playwright.stop()
            
        await super().shutdown()
        
    async def _launch_browser(self) -> None:
        """Launch the browser instance"""
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        )
        
        # Create default context
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            ignore_https_errors=True,
            java_script_enabled=True,
            accept_downloads=True,
            storage_state=None  # Could load saved state here
        )
        
        self.contexts["default"] = context
        
        # Create default page
        page = await context.new_page()
        self.pages["default"] = page
        
        # Set default timeout
        page.set_default_timeout(self.default_timeout)
        
    async def navigate(
        self, 
        url: str, 
        wait_for: str = "domcontentloaded",
        context_name: str = "default"
    ) -> bool:
        """Navigate to a URL"""
        try:
            page = self.pages.get(context_name)
            if not page:
                page = await self.contexts[context_name].new_page()
                self.pages[context_name] = page
                
            await page.goto(url, wait_until=wait_for)
            logger.info(f"Navigated to: {url}")
            return True
            
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False
            
    async def click(
        self, 
        selector: str, 
        context_name: str = "default",
        wait_for_navigation: bool = False
    ) -> bool:
        """Click an element"""
        try:
            page = self.pages[context_name]
            
            # Wait for element to be clickable
            await page.wait_for_selector(selector, state="visible")
            
            if wait_for_navigation:
                async with page.expect_navigation():
                    await page.click(selector)
            else:
                await page.click(selector)
                
            logger.info(f"Clicked: {selector}")
            return True
            
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False
            
    async def type_text(
        self, 
        selector: str, 
        text: str, 
        context_name: str = "default",
        clear_first: bool = True
    ) -> bool:
        """Type text into an element"""
        try:
            page = self.pages[context_name]
            
            # Wait for element
            await page.wait_for_selector(selector, state="visible")
            
            if clear_first:
                await page.fill(selector, text)
            else:
                await page.type(selector, text)
                
            logger.info(f"Typed text into: {selector}")
            return True
            
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return False
            
    async def extract_data(
        self, 
        selectors: Dict[str, str], 
        context_name: str = "default",
        as_list: bool = False
    ) -> Dict[str, Any]:
        """Extract data from page using selectors"""
        try:
            page = self.pages[context_name]
            extracted = {}
            
            for key, selector in selectors.items():
                try:
                    if as_list:
                        elements = await page.query_selector_all(selector)
                        extracted[key] = [
                            await elem.text_content() for elem in elements
                        ]
                    else:
                        element = await page.query_selector(selector)
                        if element:
                            extracted[key] = await element.text_content()
                        else:
                            extracted[key] = None
                            
                except Exception as e:
                    logger.warning(f"Failed to extract {key}: {e}")
                    extracted[key] = None if not as_list else []
                    
            return extracted
            
        except Exception as e:
            logger.error(f"Data extraction failed: {e}")
            return {}
            
    async def screenshot(
        self, 
        path: Optional[str] = None,
        full_page: bool = False,
        context_name: str = "default"
    ) -> Optional[str]:
        """Take a screenshot"""
        try:
            page = self.pages[context_name]
            
            if not path:
                path = f"/tmp/screenshot_{datetime.now().timestamp()}.png"
                
            await page.screenshot(path=path, full_page=full_page)
            
            # Return base64 encoded image
            with open(path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
                
            return image_data
            
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None
            
    async def execute_script(
        self, 
        script: str, 
        context_name: str = "default"
    ) -> Any:
        """Execute JavaScript on the page"""
        try:
            page = self.pages[context_name]
            result = await page.evaluate(script)
            return result
            
        except Exception as e:
            logger.error(f"Script execution failed: {e}")
            return None
            
    async def fill_form(
        self, 
        form_data: Dict[str, str],
        submit_selector: Optional[str] = None,
        context_name: str = "default"
    ) -> bool:
        """Fill and optionally submit a form"""
        try:
            page = self.pages[context_name]
            
            # Fill each field
            for selector, value in form_data.items():
                # Determine field type
                element = await page.query_selector(selector)
                if not element:
                    logger.warning(f"Field not found: {selector}")
                    continue
                    
                tag = await element.evaluate("el => el.tagName.toLowerCase()")
                input_type = await element.evaluate("el => el.type") if tag == "input" else None
                
                if tag == "select":
                    await page.select_option(selector, value)
                elif input_type == "checkbox":
                    if value.lower() == "true":
                        await page.check(selector)
                    else:
                        await page.uncheck(selector)
                elif input_type == "radio":
                    await page.click(f"{selector}[value='{value}']")
                else:
                    await page.fill(selector, value)
                    
            # Submit if requested
            if submit_selector:
                await page.click(submit_selector)
                
            logger.info("Form filled successfully")
            return True
            
        except Exception as e:
            logger.error(f"Form filling failed: {e}")
            return False
            
    async def get_page_info(self, context_name: str = "default") -> WebPageInfo:
        """Get comprehensive information about current page"""
        try:
            page = self.pages[context_name]
            
            # Get basic info
            url = page.url
            title = await page.title()
            
            # Get page content
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract description
            description = None
            desc_tag = soup.find('meta', attrs={'name': 'description'})
            if desc_tag:
                description = desc_tag.get('content', '')
                
            # Extract keywords
            keywords = []
            keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
            if keywords_tag:
                keywords = [k.strip() for k in keywords_tag.get('content', '').split(',')]
                
            # Extract forms
            forms = []
            for form in soup.find_all('form'):
                form_info = {
                    'action': form.get('action', ''),
                    'method': form.get('method', 'get'),
                    'fields': []
                }
                
                for input_elem in form.find_all(['input', 'select', 'textarea']):
                    field_info = {
                        'type': input_elem.name,
                        'name': input_elem.get('name', ''),
                        'id': input_elem.get('id', ''),
                        'required': input_elem.get('required') is not None
                    }
                    form_info['fields'].append(field_info)
                    
                forms.append(form_info)
                
            # Extract links
            links = []
            for link in soup.find_all('a', href=True):
                links.append({
                    'text': link.get_text(strip=True),
                    'href': link['href']
                })
                
            # Extract images
            images = []
            for img in soup.find_all('img'):
                images.append({
                    'src': img.get('src', ''),
                    'alt': img.get('alt', '')
                })
                
            # Get text content
            text_content = soup.get_text(separator=' ', strip=True)
            
            # Extract structured data (JSON-LD)
            structured_data = {}
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    data = json.loads(script.string)
                    structured_data.update(data)
                except:
                    pass
                    
            return WebPageInfo(
                url=url,
                title=title,
                description=description,
                keywords=keywords,
                forms=forms,
                links=links,
                images=images,
                text_content=text_content[:1000],  # First 1000 chars
                structured_data=structured_data
            )
            
        except Exception as e:
            logger.error(f"Failed to get page info: {e}")
            return WebPageInfo(url="", title="Error")
            
    async def search_web(
        self, 
        query: str, 
        search_engine: str = "google",
        num_results: int = 5
    ) -> List[Dict[str, str]]:
        """Search the web and return results"""
        try:
            # Navigate to search engine
            if search_engine == "google":
                await self.navigate("https://www.google.com")
                await self.type_text("textarea[name='q']", query)
                await self.click("input[name='btnK']", wait_for_navigation=True)
            elif search_engine == "duckduckgo":
                await self.navigate("https://duckduckgo.com")
                await self.type_text("input[name='q']", query)
                await self.click("button[type='submit']", wait_for_navigation=True)
            else:
                raise ValueError(f"Unsupported search engine: {search_engine}")
                
            # Wait for results
            await asyncio.sleep(2)
            
            # Extract search results
            results = []
            
            if search_engine == "google":
                selectors = {
                    'container': 'div.g',
                    'title': 'h3',
                    'link': 'a',
                    'snippet': 'div[data-sncf="1"]'
                }
            else:  # duckduckgo
                selectors = {
                    'container': 'article[data-testid="result"]',
                    'title': 'h2',
                    'link': 'a',
                    'snippet': 'span'
                }
                
            page = self.pages["default"]
            result_elements = await page.query_selector_all(selectors['container'])
            
            for i, element in enumerate(result_elements[:num_results]):
                try:
                    title_elem = await element.query_selector(selectors['title'])
                    link_elem = await element.query_selector(selectors['link'])
                    snippet_elem = await element.query_selector(selectors['snippet'])
                    
                    title = await title_elem.text_content() if title_elem else ""
                    link = await link_elem.get_attribute('href') if link_elem else ""
                    snippet = await snippet_elem.text_content() if snippet_elem else ""
                    
                    results.append({
                        'title': title.strip(),
                        'url': link,
                        'snippet': snippet.strip()
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to parse result {i}: {e}")
                    
            return results
            
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return []
            
    async def smart_click(
        self, 
        description: str,
        context_name: str = "default"
    ) -> bool:
        """Click an element based on description using AI"""
        if not ollama_service.is_available():
            logger.warning("AI service not available for smart click")
            return False
            
        try:
            page = self.pages[context_name]
            
            # Get all clickable elements
            clickable_elements = await page.evaluate("""
                () => {
                    const elements = document.querySelectorAll('a, button, input[type="submit"], input[type="button"], [onclick]');
                    return Array.from(elements).map((el, index) => ({
                        index: index,
                        tag: el.tagName.toLowerCase(),
                        text: el.textContent.trim(),
                        type: el.type || '',
                        href: el.href || '',
                        ariaLabel: el.getAttribute('aria-label') || '',
                        title: el.getAttribute('title') || '',
                        selector: `${el.tagName.toLowerCase()}:nth-of-type(${index + 1})`
                    }));
                }
            """)
            
            # Use AI to find best match
            prompt = f"""
            Find the best matching clickable element for: "{description}"
            
            Elements:
            {json.dumps(clickable_elements[:20], indent=2)}
            
            Return only the index number of the best match, or -1 if no good match.
            """
            
            response = await ollama_service.generate(
                prompt, ModelType.GENERAL, temperature=0.3
            )
            
            try:
                index = int(response.strip())
                if 0 <= index < len(clickable_elements):
                    element = clickable_elements[index]
                    await page.click(element['selector'])
                    logger.info(f"Smart clicked: {element['text']}")
                    return True
                    
            except ValueError:
                logger.error("AI returned invalid index")
                
        except Exception as e:
            logger.error(f"Smart click failed: {e}")
            
        return False
        
    async def wait_for_condition(
        self,
        condition: str,
        timeout: int = 30000,
        context_name: str = "default"
    ) -> bool:
        """Wait for a JavaScript condition to be true"""
        try:
            page = self.pages[context_name]
            await page.wait_for_function(condition, timeout=timeout)
            return True
            
        except PlaywrightTimeout:
            logger.warning(f"Timeout waiting for condition: {condition}")
            return False
            
    # Command handlers
    async def _handle_navigate(self, message):
        """Handle navigate command"""
        data = message.payload
        url = data["url"]
        context = data.get("context", "default")
        
        success = await self.navigate(url, context_name=context)
        
        await self.send_command(
            message.from_agent,
            "navigation_complete",
            {"success": success, "url": url}
        )
        
    async def _handle_click(self, message):
        """Handle click command"""
        data = message.payload
        selector = data.get("selector")
        description = data.get("description")
        context = data.get("context", "default")
        
        if selector:
            success = await self.click(selector, context_name=context)
        elif description:
            success = await self.smart_click(description, context_name=context)
        else:
            success = False
            
        await self.send_command(
            message.from_agent,
            "click_complete",
            {"success": success}
        )
        
    async def _handle_type(self, message):
        """Handle type command"""
        data = message.payload
        selector = data["selector"]
        text = data["text"]
        context = data.get("context", "default")
        
        success = await self.type_text(selector, text, context_name=context)
        
        await self.send_command(
            message.from_agent,
            "type_complete",
            {"success": success}
        )
        
    async def _handle_extract(self, message):
        """Handle extract command"""
        data = message.payload
        selectors = data["selectors"]
        context = data.get("context", "default")
        as_list = data.get("as_list", False)
        
        extracted = await self.extract_data(selectors, context_name=context, as_list=as_list)
        
        await self.send_command(
            message.from_agent,
            "extract_complete",
            {"data": extracted}
        )
        
    async def _handle_screenshot(self, message):
        """Handle screenshot command"""
        data = message.payload
        context = data.get("context", "default")
        full_page = data.get("full_page", False)
        
        image_data = await self.screenshot(full_page=full_page, context_name=context)
        
        await self.send_command(
            message.from_agent,
            "screenshot_complete",
            {"image": image_data}
        )
        
    async def _handle_execute_script(self, message):
        """Handle execute script command"""
        data = message.payload
        script = data["script"]
        context = data.get("context", "default")
        
        result = await self.execute_script(script, context_name=context)
        
        await self.send_command(
            message.from_agent,
            "script_complete",
            {"result": result}
        )
        
    async def _handle_fill_form(self, message):
        """Handle fill form command"""
        data = message.payload
        form_data = data["form_data"]
        submit = data.get("submit_selector")
        context = data.get("context", "default")
        
        success = await self.fill_form(form_data, submit, context_name=context)
        
        await self.send_command(
            message.from_agent,
            "form_complete",
            {"success": success}
        )
        
    async def _handle_get_page_info(self, message):
        """Handle get page info command"""
        data = message.payload
        context = data.get("context", "default")
        
        info = await self.get_page_info(context_name=context)
        
        await self.send_command(
            message.from_agent,
            "page_info",
            {
                "url": info.url,
                "title": info.title,
                "description": info.description,
                "forms_count": len(info.forms),
                "links_count": len(info.links),
                "text_preview": info.text_content[:200]
            }
        )
        
    async def _handle_search_web(self, message):
        """Handle web search command"""
        data = message.payload
        query = data["query"]
        search_engine = data.get("search_engine", "google")
        num_results = data.get("num_results", 5)
        
        results = await self.search_web(query, search_engine, num_results)
        
        await self.send_command(
            message.from_agent,
            "search_results",
            {"results": results, "query": query}
        )