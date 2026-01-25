# Project 6: Browser Automation

## Overview
An intelligent browser automation system combining Playwright for reliable web interaction with LangGraph for task orchestration. Exposes capabilities via MCP for Claude Code integration.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Claude Code / MCP Client                         │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ MCP Protocol
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                      Browser MCP Server                             │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    LangGraph Orchestrator                     │  │
│  │  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐      │  │
│  │  │  Plan   │──▶│Navigate │──▶│ Extract │──▶│ Report  │      │  │
│  │  │  Node   │   │  Node   │   │  Node   │   │  Node   │      │  │
│  │  └─────────┘   └─────────┘   └─────────┘   └─────────┘      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                 │                                   │
│  ┌──────────────────────────────▼──────────────────────────────┐  │
│  │                    Playwright Controller                     │  │
│  │  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐     │  │
│  │  │Navigate │   │  Click  │   │  Fill   │   │ Extract │     │  │
│  │  │         │   │         │   │  Form   │   │  Data   │     │  │
│  │  └─────────┘   └─────────┘   └─────────┘   └─────────┘     │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                         ┌──────────────┐
                         │   Chromium   │
                         │   Browser    │
                         └──────────────┘
```

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Browser Engine** | Playwright | Most reliable, cross-browser |
| **Orchestration** | LangGraph | Stateful workflows |
| **MCP Server** | Python mcp SDK | Claude Code integration |
| **Data Extraction** | BeautifulSoup + LLM | Structured extraction |
| **Screenshot** | Playwright built-in | Page state capture |

## Project Structure

```
browser-automation/
├── src/
│   ├── __init__.py
│   ├── server.py            # MCP server entry
│   ├── browser/
│   │   ├── __init__.py
│   │   ├── controller.py    # Playwright controller
│   │   ├── actions.py       # Browser actions
│   │   └── extraction.py    # Data extraction
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── graph.py         # LangGraph workflow
│   │   ├── nodes.py         # Workflow nodes
│   │   └── state.py         # State schema
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── navigation.py    # MCP navigation tools
│   │   ├── interaction.py   # MCP interaction tools
│   │   └── extraction.py    # MCP extraction tools
│   └── config.py
├── tests/
│   ├── test_browser.py
│   ├── test_workflow.py
│   └── test_mcp.py
├── pyproject.toml
└── README.md
```

## Implementation

### Phase 1: Playwright Controller (Week 1)

#### Browser Controller
```python
# src/browser/controller.py
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from dataclasses import dataclass
from typing import Optional
import asyncio

@dataclass
class BrowserState:
    url: str
    title: str
    screenshot: Optional[bytes]
    html: Optional[str]

class BrowserController:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def start(self):
        """Start the browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        self.page = await self.context.new_page()

    async def stop(self):
        """Stop the browser."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def navigate(self, url: str, wait_for: str = "networkidle") -> BrowserState:
        """Navigate to a URL."""
        await self.page.goto(url, wait_until=wait_for)
        return await self._get_state()

    async def click(self, selector: str) -> BrowserState:
        """Click an element."""
        await self.page.click(selector)
        await self.page.wait_for_load_state("networkidle")
        return await self._get_state()

    async def fill(self, selector: str, value: str) -> BrowserState:
        """Fill a form field."""
        await self.page.fill(selector, value)
        return await self._get_state()

    async def type_text(self, selector: str, text: str, delay: int = 50) -> BrowserState:
        """Type text with realistic delay."""
        await self.page.type(selector, text, delay=delay)
        return await self._get_state()

    async def press(self, key: str) -> BrowserState:
        """Press a keyboard key."""
        await self.page.keyboard.press(key)
        return await self._get_state()

    async def scroll(self, direction: str = "down", amount: int = 500) -> BrowserState:
        """Scroll the page."""
        if direction == "down":
            await self.page.evaluate(f"window.scrollBy(0, {amount})")
        elif direction == "up":
            await self.page.evaluate(f"window.scrollBy(0, -{amount})")
        return await self._get_state()

    async def screenshot(self, full_page: bool = False) -> bytes:
        """Take a screenshot."""
        return await self.page.screenshot(full_page=full_page)

    async def get_html(self) -> str:
        """Get page HTML."""
        return await self.page.content()

    async def get_text(self, selector: str = "body") -> str:
        """Get text content of an element."""
        element = await self.page.query_selector(selector)
        if element:
            return await element.inner_text()
        return ""

    async def get_elements(self, selector: str) -> list[dict]:
        """Get elements matching selector."""
        elements = await self.page.query_selector_all(selector)
        results = []
        for el in elements:
            results.append({
                "tag": await el.evaluate("el => el.tagName.toLowerCase()"),
                "text": await el.inner_text(),
                "href": await el.get_attribute("href"),
                "id": await el.get_attribute("id"),
                "class": await el.get_attribute("class")
            })
        return results

    async def wait_for_selector(self, selector: str, timeout: int = 30000) -> bool:
        """Wait for a selector to appear."""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    async def execute_js(self, script: str) -> any:
        """Execute JavaScript on the page."""
        return await self.page.evaluate(script)

    async def _get_state(self) -> BrowserState:
        """Get current browser state."""
        return BrowserState(
            url=self.page.url,
            title=await self.page.title(),
            screenshot=await self.screenshot(),
            html=await self.get_html()
        )
```

#### Browser Actions
```python
# src/browser/actions.py
from dataclasses import dataclass
from typing import Optional, Literal
from enum import Enum

class ActionType(Enum):
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    TYPE = "type"
    PRESS = "press"
    SCROLL = "scroll"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    EXTRACT = "extract"

@dataclass
class BrowserAction:
    action_type: ActionType
    selector: Optional[str] = None
    value: Optional[str] = None
    url: Optional[str] = None
    timeout: int = 30000

class ActionBuilder:
    """Fluent interface for building browser actions."""

    @staticmethod
    def navigate(url: str) -> BrowserAction:
        return BrowserAction(action_type=ActionType.NAVIGATE, url=url)

    @staticmethod
    def click(selector: str) -> BrowserAction:
        return BrowserAction(action_type=ActionType.CLICK, selector=selector)

    @staticmethod
    def fill(selector: str, value: str) -> BrowserAction:
        return BrowserAction(action_type=ActionType.FILL, selector=selector, value=value)

    @staticmethod
    def type(selector: str, text: str) -> BrowserAction:
        return BrowserAction(action_type=ActionType.TYPE, selector=selector, value=text)

    @staticmethod
    def press(key: str) -> BrowserAction:
        return BrowserAction(action_type=ActionType.PRESS, value=key)

    @staticmethod
    def scroll(direction: str = "down") -> BrowserAction:
        return BrowserAction(action_type=ActionType.SCROLL, value=direction)

    @staticmethod
    def wait(selector: str, timeout: int = 30000) -> BrowserAction:
        return BrowserAction(action_type=ActionType.WAIT, selector=selector, timeout=timeout)

    @staticmethod
    def screenshot() -> BrowserAction:
        return BrowserAction(action_type=ActionType.SCREENSHOT)

    @staticmethod
    def extract(selector: str) -> BrowserAction:
        return BrowserAction(action_type=ActionType.EXTRACT, selector=selector)
```

### Phase 2: Data Extraction (Week 1)

#### Smart Data Extraction
```python
# src/browser/extraction.py
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional
import httpx
import json

@dataclass
class ExtractedData:
    title: str
    main_content: str
    links: list[dict]
    forms: list[dict]
    tables: list[list[list[str]]]
    structured_data: Optional[dict]

class DataExtractor:
    def __init__(self, llm_url: str = "http://localhost:11434"):
        self.llm_url = llm_url

    def extract_basic(self, html: str) -> ExtractedData:
        """Extract basic data from HTML."""
        soup = BeautifulSoup(html, "html.parser")

        # Title
        title = soup.title.string if soup.title else ""

        # Main content
        main = soup.find("main") or soup.find("article") or soup.find("body")
        main_content = main.get_text(strip=True)[:5000] if main else ""

        # Links
        links = []
        for a in soup.find_all("a", href=True)[:50]:
            links.append({
                "text": a.get_text(strip=True),
                "href": a["href"]
            })

        # Forms
        forms = []
        for form in soup.find_all("form"):
            form_data = {
                "action": form.get("action", ""),
                "method": form.get("method", "get"),
                "inputs": []
            }
            for inp in form.find_all(["input", "textarea", "select"]):
                form_data["inputs"].append({
                    "name": inp.get("name", ""),
                    "type": inp.get("type", "text"),
                    "placeholder": inp.get("placeholder", "")
                })
            forms.append(form_data)

        # Tables
        tables = []
        for table in soup.find_all("table")[:5]:
            table_data = []
            for row in table.find_all("tr"):
                row_data = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
                table_data.append(row_data)
            tables.append(table_data)

        return ExtractedData(
            title=title,
            main_content=main_content,
            links=links,
            forms=forms,
            tables=tables,
            structured_data=None
        )

    async def extract_structured(self, html: str, schema: dict) -> dict:
        """Extract structured data using LLM."""
        basic = self.extract_basic(html)

        prompt = f"""Extract structured data from this webpage content according to the schema.

Page Title: {basic.title}

Page Content (truncated):
{basic.main_content[:3000]}

Schema to extract:
{json.dumps(schema, indent=2)}

Return only valid JSON matching the schema. If a field cannot be found, use null."""

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.llm_url}/api/generate",
                json={
                    "model": "deepseek-r1:14b",
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            result = response.json()

            try:
                return json.loads(result.get("response", "{}"))
            except json.JSONDecodeError:
                return {}

    def find_selectors(self, html: str, description: str) -> list[str]:
        """Find CSS selectors matching a description."""
        soup = BeautifulSoup(html, "html.parser")
        selectors = []

        # Common patterns
        patterns = {
            "button": ["button", "input[type='submit']", "a.btn", "[role='button']"],
            "link": ["a[href]"],
            "input": ["input", "textarea"],
            "form": ["form"],
            "heading": ["h1", "h2", "h3"],
            "list": ["ul", "ol"],
            "table": ["table"],
            "image": ["img"],
            "video": ["video", "iframe[src*='youtube']"]
        }

        # Match description to patterns
        desc_lower = description.lower()
        for key, sels in patterns.items():
            if key in desc_lower:
                selectors.extend(sels)

        # Also try to find by text content
        for el in soup.find_all(True):
            if el.string and description.lower() in el.string.lower():
                if el.get("id"):
                    selectors.append(f"#{el['id']}")
                elif el.get("class"):
                    selectors.append(f".{'.'.join(el['class'])}")

        return list(set(selectors))
```

### Phase 3: LangGraph Orchestration (Week 2)

#### State Schema
```python
# src/orchestration/state.py
from typing import TypedDict, Optional, Annotated
from langgraph.graph.message import add_messages

class BrowserState(TypedDict):
    # Task description
    task: str

    # Current state
    current_url: str
    page_title: str
    page_content: str
    screenshot_path: Optional[str]

    # History
    actions_taken: list[dict]
    messages: Annotated[list, add_messages]

    # Results
    extracted_data: Optional[dict]
    error: Optional[str]
    completed: bool
```

#### Workflow Nodes
```python
# src/orchestration/nodes.py
from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage
from browser.controller import BrowserController
from browser.extraction import DataExtractor
import httpx
import json

class WorkflowNodes:
    def __init__(
        self,
        browser: BrowserController,
        extractor: DataExtractor,
        llm_url: str = "http://localhost:11434"
    ):
        self.browser = browser
        self.extractor = extractor
        self.llm_url = llm_url

    async def plan_node(self, state: dict) -> dict:
        """Plan the next action based on task and current state."""
        prompt = f"""You are a browser automation assistant. Plan the next action to complete the task.

Task: {state['task']}

Current URL: {state['current_url']}
Page Title: {state['page_title']}
Page Content (truncated): {state['page_content'][:2000]}

Previous actions taken:
{json.dumps(state['actions_taken'][-5:], indent=2)}

What is the next action? Choose from:
- navigate: Go to a URL
- click: Click an element (provide selector)
- fill: Fill a form field (provide selector and value)
- type: Type text (provide selector and text)
- press: Press a key (provide key name)
- scroll: Scroll the page (provide direction: up/down)
- extract: Extract data from the page
- complete: Task is complete

Return JSON:
{{
    "action": "action_type",
    "selector": "css_selector or null",
    "value": "value or null",
    "url": "url or null",
    "reasoning": "why this action"
}}"""

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.llm_url}/api/generate",
                json={
                    "model": "deepseek-r1:14b",
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            result = response.json()

            try:
                plan = json.loads(result.get("response", "{}"))
            except json.JSONDecodeError:
                plan = {"action": "complete", "reasoning": "Failed to parse response"}

        return {
            "messages": [AIMessage(content=f"Plan: {plan['reasoning']}")],
            "next_action": plan
        }

    async def execute_node(self, state: dict) -> dict:
        """Execute the planned action."""
        action = state.get("next_action", {})
        action_type = action.get("action", "complete")

        try:
            if action_type == "navigate":
                result = await self.browser.navigate(action["url"])
            elif action_type == "click":
                result = await self.browser.click(action["selector"])
            elif action_type == "fill":
                result = await self.browser.fill(action["selector"], action["value"])
            elif action_type == "type":
                result = await self.browser.type_text(action["selector"], action["value"])
            elif action_type == "press":
                result = await self.browser.press(action["value"])
            elif action_type == "scroll":
                result = await self.browser.scroll(action.get("value", "down"))
            elif action_type == "extract":
                html = await self.browser.get_html()
                extracted = self.extractor.extract_basic(html)
                return {
                    "extracted_data": {
                        "title": extracted.title,
                        "content": extracted.main_content,
                        "links": extracted.links
                    },
                    "actions_taken": state["actions_taken"] + [action]
                }
            elif action_type == "complete":
                return {"completed": True}
            else:
                return {"error": f"Unknown action: {action_type}"}

            return {
                "current_url": result.url,
                "page_title": result.title,
                "page_content": await self.browser.get_text(),
                "actions_taken": state["actions_taken"] + [action]
            }

        except Exception as e:
            return {"error": str(e)}

    async def validate_node(self, state: dict) -> dict:
        """Validate the action result."""
        if state.get("error"):
            return {
                "messages": [AIMessage(content=f"Error: {state['error']}")],
                "completed": False
            }

        if state.get("completed"):
            return {
                "messages": [AIMessage(content="Task completed successfully")],
                "completed": True
            }

        # Check if we're making progress
        if len(state.get("actions_taken", [])) > 20:
            return {
                "messages": [AIMessage(content="Too many actions, stopping")],
                "completed": True,
                "error": "Exceeded action limit"
            }

        return {"completed": False}

    def should_continue(self, state: dict) -> Literal["plan", "end"]:
        """Determine if workflow should continue."""
        if state.get("completed") or state.get("error"):
            return "end"
        return "plan"
```

#### LangGraph Workflow
```python
# src/orchestration/graph.py
from langgraph.graph import StateGraph, END
from orchestration.state import BrowserState
from orchestration.nodes import WorkflowNodes
from browser.controller import BrowserController
from browser.extraction import DataExtractor

def create_browser_workflow():
    """Create the browser automation workflow."""

    # Initialize components
    browser = BrowserController(headless=True)
    extractor = DataExtractor()
    nodes = WorkflowNodes(browser, extractor)

    # Build graph
    workflow = StateGraph(BrowserState)

    # Add nodes
    workflow.add_node("plan", nodes.plan_node)
    workflow.add_node("execute", nodes.execute_node)
    workflow.add_node("validate", nodes.validate_node)

    # Add edges
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "execute")
    workflow.add_edge("execute", "validate")
    workflow.add_conditional_edges(
        "validate",
        nodes.should_continue,
        {
            "plan": "plan",
            "end": END
        }
    )

    return workflow.compile(), browser

async def run_browser_task(task: str, start_url: str = "https://www.google.com") -> dict:
    """Run a browser automation task."""
    workflow, browser = create_browser_workflow()

    try:
        await browser.start()

        # Navigate to start URL
        state = await browser.navigate(start_url)

        # Initial state
        initial_state = {
            "task": task,
            "current_url": state.url,
            "page_title": state.title,
            "page_content": await browser.get_text(),
            "screenshot_path": None,
            "actions_taken": [],
            "messages": [],
            "extracted_data": None,
            "error": None,
            "completed": False
        }

        # Run workflow
        result = await workflow.ainvoke(initial_state)
        return result

    finally:
        await browser.stop()
```

### Phase 4: MCP Server (Week 2)

#### MCP Server Implementation
```python
# src/server.py
from mcp.server import Server
from mcp.types import Tool, TextContent
from browser.controller import BrowserController
from browser.extraction import DataExtractor
from orchestration.graph import run_browser_task
import asyncio

server = Server("browser-mcp")

# Shared browser instance
_browser: BrowserController | None = None

async def get_browser() -> BrowserController:
    global _browser
    if _browser is None:
        _browser = BrowserController(headless=True)
        await _browser.start()
    return _browser

@server.tool()
async def navigate(url: str) -> dict:
    """Navigate to a URL and return page info.

    Args:
        url: The URL to navigate to
    """
    browser = await get_browser()
    state = await browser.navigate(url)
    return {
        "url": state.url,
        "title": state.title,
        "success": True
    }

@server.tool()
async def click(selector: str) -> dict:
    """Click an element on the page.

    Args:
        selector: CSS selector for the element to click
    """
    browser = await get_browser()
    state = await browser.click(selector)
    return {
        "url": state.url,
        "title": state.title,
        "success": True
    }

@server.tool()
async def fill_form(selector: str, value: str) -> dict:
    """Fill a form field.

    Args:
        selector: CSS selector for the input field
        value: Value to enter
    """
    browser = await get_browser()
    await browser.fill(selector, value)
    return {"success": True}

@server.tool()
async def get_page_content() -> dict:
    """Get the current page content."""
    browser = await get_browser()
    extractor = DataExtractor()
    html = await browser.get_html()
    data = extractor.extract_basic(html)
    return {
        "url": browser.page.url,
        "title": data.title,
        "content": data.main_content[:5000],
        "links": data.links[:20],
        "forms": data.forms
    }

@server.tool()
async def take_screenshot() -> dict:
    """Take a screenshot of the current page."""
    browser = await get_browser()
    screenshot = await browser.screenshot(full_page=True)

    # Save to temp file
    import tempfile
    import base64
    from pathlib import Path

    temp_dir = Path(tempfile.gettempdir()) / "browser-mcp"
    temp_dir.mkdir(exist_ok=True)

    filepath = temp_dir / f"screenshot_{asyncio.get_event_loop().time()}.png"
    filepath.write_bytes(screenshot)

    return {
        "path": str(filepath),
        "base64": base64.b64encode(screenshot).decode()[:1000] + "..."  # Truncated
    }

@server.tool()
async def run_task(task: str, start_url: str = "https://www.google.com") -> dict:
    """Run an automated browser task using AI planning.

    Args:
        task: Description of the task to perform
        start_url: Starting URL (default: Google)
    """
    result = await run_browser_task(task, start_url)
    return {
        "completed": result.get("completed", False),
        "extracted_data": result.get("extracted_data"),
        "actions_count": len(result.get("actions_taken", [])),
        "error": result.get("error")
    }

@server.tool()
async def extract_data(selector: str = "body", schema: dict | None = None) -> dict:
    """Extract data from the current page.

    Args:
        selector: CSS selector for content to extract
        schema: Optional JSON schema for structured extraction
    """
    browser = await get_browser()
    extractor = DataExtractor()
    html = await browser.get_html()

    if schema:
        return await extractor.extract_structured(html, schema)
    else:
        data = extractor.extract_basic(html)
        return {
            "title": data.title,
            "content": data.main_content,
            "tables": data.tables
        }

@server.tool()
async def close_browser() -> dict:
    """Close the browser session."""
    global _browser
    if _browser:
        await _browser.stop()
        _browser = None
    return {"success": True}

# Entry point
if __name__ == "__main__":
    from mcp.server.stdio import stdio_server
    asyncio.run(stdio_server(server))
```

---

## Claude Desktop Configuration

```json
// ~/.claude/claude_desktop_config.json
{
  "mcpServers": {
    "browser": {
      "command": "python",
      "args": ["-m", "browser_automation.server"],
      "cwd": "/Users/d/claude-code/projects-2026/browser-automation"
    }
  }
}
```

---

## Usage Examples

### From Claude Code
```
User: "Go to Hacker News and get the top 5 stories"
Claude: [Uses browser-mcp navigate, then extract_data]

User: "Search Google for 'LangGraph tutorials' and get the first 3 results"
Claude: [Uses browser-mcp run_task with the search task]

User: "Fill out the contact form on example.com"
Claude: [Uses browser-mcp navigate, fill_form, click]
```

### Programmatic Usage
```python
from browser_automation.orchestration.graph import run_browser_task

# Run automated task
result = await run_browser_task(
    task="Search for Python tutorials and get the top 5 results",
    start_url="https://www.google.com"
)

print(result["extracted_data"])
```

---

## Timeline

| Week | Task |
|------|------|
| Week 1 | Playwright controller + Data extraction |
| Week 2 | LangGraph workflow + MCP server |

**Total: 2 weeks**
