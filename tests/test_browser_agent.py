"""
Test suite for the Browser Agent
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import base64
from datetime import datetime

from sarah.agents.browser import (
    BrowserAgent,
    BrowserAction,
    BrowserActionType,
    WebElement,
    WebPageInfo,
)


@pytest.fixture
def browser_agent():
    """Create a BrowserAgent instance for testing"""
    agent = BrowserAgent()
    agent.redis = AsyncMock()
    return agent


@pytest.fixture
def mock_page():
    """Create a mock Playwright page"""
    page = AsyncMock()
    page.url = "https://example.com"
    page.title = AsyncMock(return_value="Example Page")
    page.content = AsyncMock(return_value="<html><body>Test</body></html>")
    page.goto = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.type = AsyncMock()
    page.screenshot = AsyncMock()
    page.evaluate = AsyncMock()
    page.query_selector = AsyncMock()
    page.query_selector_all = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.select_option = AsyncMock()
    page.check = AsyncMock()
    page.uncheck = AsyncMock()
    return page


@pytest.fixture
def mock_context():
    """Create a mock browser context"""
    context = AsyncMock()
    context.new_page = AsyncMock()
    return context


@pytest.fixture
def mock_browser():
    """Create a mock browser"""
    browser = AsyncMock()
    browser.new_context = AsyncMock()
    return browser


@pytest.fixture
def sample_page_content():
    """Sample HTML page content"""
    return """
    <html>
    <head>
        <title>Test Page</title>
        <meta name="description" content="A test page">
        <meta name="keywords" content="test, example, demo">
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "WebPage", "name": "Test"}
        </script>
    </head>
    <body>
        <h1>Welcome</h1>
        <form action="/submit" method="post">
            <input type="text" name="username" id="username" required>
            <input type="password" name="password" id="password" required>
            <input type="checkbox" name="remember" id="remember">
            <select name="role" id="role">
                <option value="user">User</option>
                <option value="admin">Admin</option>
            </select>
            <button type="submit">Login</button>
        </form>
        <a href="/about">About Us</a>
        <a href="/contact">Contact</a>
        <img src="/logo.png" alt="Logo">
        <p>This is a test page content.</p>
    </body>
    </html>
    """


@pytest.mark.asyncio
async def test_browser_agent_initialization(browser_agent):
    """Test BrowserAgent initialization"""
    assert browser_agent.name == "browser"
    assert browser_agent.agent_type == "Browser Automation"
    assert browser_agent.headless is True
    assert browser_agent.default_timeout == 30000


@pytest.mark.asyncio
async def test_navigate(browser_agent, mock_page):
    """Test page navigation"""
    browser_agent.pages = {"default": mock_page}

    success = await browser_agent.navigate("https://example.com")

    assert success is True
    mock_page.goto.assert_called_once_with(
        "https://example.com", wait_until="domcontentloaded"
    )


@pytest.mark.asyncio
async def test_click(browser_agent, mock_page):
    """Test clicking elements"""
    browser_agent.pages = {"default": mock_page}

    # Test normal click
    success = await browser_agent.click("button#submit")

    assert success is True
    mock_page.wait_for_selector.assert_called_with("button#submit", state="visible")
    mock_page.click.assert_called_with("button#submit")

    # Test click with navigation
    mock_page.expect_navigation = AsyncMock()
    success = await browser_agent.click("a#link", wait_for_navigation=True)

    assert success is True


@pytest.mark.asyncio
async def test_type_text(browser_agent, mock_page):
    """Test typing text"""
    browser_agent.pages = {"default": mock_page}

    # Test with clear first (default)
    success = await browser_agent.type_text("input#username", "testuser")

    assert success is True
    mock_page.wait_for_selector.assert_called_with("input#username", state="visible")
    mock_page.fill.assert_called_with("input#username", "testuser")

    # Test without clearing
    success = await browser_agent.type_text("input#search", "query", clear_first=False)

    mock_page.type.assert_called_with("input#search", "query")


@pytest.mark.asyncio
async def test_extract_data(browser_agent, mock_page):
    """Test data extraction"""
    browser_agent.pages = {"default": mock_page}

    # Mock elements
    mock_element = AsyncMock()
    mock_element.text_content = AsyncMock(return_value="Test Text")
    mock_page.query_selector = AsyncMock(return_value=mock_element)

    # Test single element extraction
    selectors = {"title": "h1", "description": "p.desc"}

    result = await browser_agent.extract_data(selectors)

    assert result["title"] == "Test Text"
    assert mock_page.query_selector.call_count == 2

    # Test list extraction
    mock_elements = [mock_element, mock_element]
    mock_page.query_selector_all = AsyncMock(return_value=mock_elements)

    result = await browser_agent.extract_data({"items": "li"}, as_list=True)

    assert len(result["items"]) == 2
    assert all(item == "Test Text" for item in result["items"])


@pytest.mark.asyncio
async def test_screenshot(browser_agent, mock_page):
    """Test screenshot capture"""
    browser_agent.pages = {"default": mock_page}

    # Mock file operations
    mock_image_data = b"fake_image_data"

    with patch("builtins.open", create=True) as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = (
            mock_image_data
        )

        result = await browser_agent.screenshot()

        assert result == base64.b64encode(mock_image_data).decode()
        mock_page.screenshot.assert_called_once()


@pytest.mark.asyncio
async def test_execute_script(browser_agent, mock_page):
    """Test JavaScript execution"""
    browser_agent.pages = {"default": mock_page}
    mock_page.evaluate.return_value = {"result": "success"}

    result = await browser_agent.execute_script("return document.title")

    assert result == {"result": "success"}
    mock_page.evaluate.assert_called_with("return document.title")


@pytest.mark.asyncio
async def test_fill_form(browser_agent, mock_page):
    """Test form filling"""
    browser_agent.pages = {"default": mock_page}

    # Mock element queries
    mock_input = AsyncMock()
    mock_input.evaluate = AsyncMock(side_effect=["input", "text"])

    mock_select = AsyncMock()
    mock_select.evaluate = AsyncMock(return_value="select")

    mock_checkbox = AsyncMock()
    mock_checkbox.evaluate = AsyncMock(side_effect=["input", "checkbox"])

    mock_page.query_selector = AsyncMock(
        side_effect=[mock_input, mock_select, mock_checkbox]
    )

    # Test form filling
    form_data = {
        "input#username": "testuser",
        "select#role": "admin",
        "input#remember": "true",
    }

    success = await browser_agent.fill_form(form_data, "button#submit")

    assert success is True
    assert mock_page.fill.call_count == 1
    assert mock_page.select_option.call_count == 1
    assert mock_page.check.call_count == 1
    mock_page.click.assert_called_with("button#submit")


@pytest.mark.asyncio
async def test_get_page_info(browser_agent, mock_page, sample_page_content):
    """Test getting page information"""
    browser_agent.pages = {"default": mock_page}
    mock_page.content.return_value = sample_page_content

    info = await browser_agent.get_page_info()

    assert info.url == "https://example.com"
    assert info.title == "Example Page"
    assert info.description == "A test page"
    assert info.keywords == ["test", "example", "demo"]
    assert len(info.forms) == 1
    assert len(info.links) == 2
    assert len(info.images) == 1
    assert "Test" in info.structured_data.get("name", "")


@pytest.mark.asyncio
async def test_search_web(browser_agent, mock_page):
    """Test web search"""
    browser_agent.pages = {"default": mock_page}
    browser_agent.navigate = AsyncMock(return_value=True)
    browser_agent.type_text = AsyncMock(return_value=True)
    browser_agent.click = AsyncMock(return_value=True)

    # Mock search results
    mock_results = []
    for i in range(3):
        result = AsyncMock()
        title_elem = AsyncMock()
        title_elem.text_content = AsyncMock(return_value=f"Result {i+1}")
        link_elem = AsyncMock()
        link_elem.get_attribute = AsyncMock(return_value=f"https://example{i+1}.com")
        snippet_elem = AsyncMock()
        snippet_elem.text_content = AsyncMock(return_value=f"Snippet {i+1}")

        result.query_selector = AsyncMock(
            side_effect=[title_elem, link_elem, snippet_elem]
        )
        mock_results.append(result)

    mock_page.query_selector_all = AsyncMock(return_value=mock_results)

    results = await browser_agent.search_web("test query", num_results=3)

    assert len(results) == 3
    assert results[0]["title"] == "Result 1"
    assert results[0]["url"] == "https://example1.com"
    assert results[0]["snippet"] == "Snippet 1"


@pytest.mark.asyncio
async def test_smart_click(browser_agent, mock_page):
    """Test AI-powered smart click"""
    browser_agent.pages = {"default": mock_page}

    # Mock clickable elements
    mock_page.evaluate.return_value = [
        {
            "index": 0,
            "tag": "button",
            "text": "Submit Form",
            "selector": "button:nth-of-type(1)",
        },
        {
            "index": 1,
            "tag": "a",
            "text": "Click here to continue",
            "selector": "a:nth-of-type(1)",
        },
    ]

    # Mock AI service
    with patch("sarah.agents.browser.ollama_service") as mock_ollama:
        mock_ollama.is_available.return_value = True
        mock_ollama.generate = AsyncMock(return_value="1")

        success = await browser_agent.smart_click("continue button")

        assert success is True
        mock_page.click.assert_called_with("a:nth-of-type(1)")


@pytest.mark.asyncio
async def test_wait_for_condition(browser_agent, mock_page):
    """Test waiting for JavaScript condition"""
    browser_agent.pages = {"default": mock_page}

    # Test successful wait
    mock_page.wait_for_function = AsyncMock()

    success = await browser_agent.wait_for_condition(
        "document.readyState === 'complete'"
    )

    assert success is True
    mock_page.wait_for_function.assert_called_once()

    # Test timeout
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    mock_page.wait_for_function = AsyncMock(side_effect=PlaywrightTimeout("Timeout"))

    success = await browser_agent.wait_for_condition("false")

    assert success is False


@pytest.mark.asyncio
async def test_browser_action_dataclass():
    """Test BrowserAction dataclass"""
    action = BrowserAction(
        action_type=BrowserActionType.CLICK,
        selector="button#submit",
        description="Submit the form",
    )

    assert action.action_type == BrowserActionType.CLICK
    assert action.selector == "button#submit"
    assert action.description == "Submit the form"
    assert action.options == {}


@pytest.mark.asyncio
async def test_web_element_dataclass():
    """Test WebElement dataclass"""
    element = WebElement(
        tag="button", text="Click Me", selector="button.primary", is_interactive=True
    )

    assert element.tag == "button"
    assert element.text == "Click Me"
    assert element.is_interactive is True
    assert element.is_visible is True


@pytest.mark.asyncio
async def test_error_handling(browser_agent, mock_page):
    """Test error handling in various methods"""
    browser_agent.pages = {"default": mock_page}

    # Test navigation error
    mock_page.goto = AsyncMock(side_effect=Exception("Network error"))
    success = await browser_agent.navigate("https://invalid.url")
    assert success is False

    # Test click error
    mock_page.click = AsyncMock(side_effect=Exception("Element not found"))
    success = await browser_agent.click("invalid-selector")
    assert success is False

    # Test type error
    mock_page.fill = AsyncMock(side_effect=Exception("Input not found"))
    success = await browser_agent.type_text("invalid-input", "text")
    assert success is False
