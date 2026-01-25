# Project 5: Screen Analysis (StreamMind)

## Overview
An intelligent screen analysis system that captures your screen periodically, analyzes content using Qwen2-VL vision model, and provides insights via menu bar notifications. Can detect context switches, summarize meetings, and extract actionable items.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Screen Analysis                              │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                         Menu Bar App (rumps)                        │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  │  Start/  │   │ Settings │   │ History  │   │  Status  │        │
│  │   Stop   │   │          │   │  View    │   │          │        │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘        │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                      Analysis Pipeline                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐           │
│  │   Screen     │──▶│   Vision     │──▶│   Context    │           │
│  │   Capture    │   │   Analysis   │   │   Tracker    │           │
│  │    (mss)     │   │  (Qwen2-VL)  │   │              │           │
│  └──────────────┘   └──────────────┘   └──────┬───────┘           │
│                                                │                    │
│  ┌──────────────┐   ┌──────────────┐          │                    │
│  │  Reasoning   │◀──│   Action     │◀─────────┘                    │
│  │ (DeepSeek R1)│   │  Extractor   │                               │
│  └──────────────┘   └──────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   Ollama     │       │   SQLite     │       │   Knowledge  │
│  (Qwen2-VL)  │       │  (History)   │       │   Engine     │
│  (DeepSeek)  │       │              │       │    (MCP)     │
└──────────────┘       └──────────────┘       └──────────────┘
```

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Screen Capture** | mss + ScreenCaptureKit | Fast, low overhead |
| **Vision Model** | Qwen2-VL 7B | Best open-source VLM |
| **Reasoning** | DeepSeek R1 14B | Chain-of-thought analysis |
| **Menu Bar** | rumps | Native macOS integration |
| **Storage** | SQLite | Local history, fast queries |
| **Notifications** | pyobjc | Native macOS notifications |

## Project Structure

```
screen-analysis/
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── capture/
│   │   ├── __init__.py
│   │   ├── screen.py        # Screen capture logic
│   │   └── window.py        # Window detection
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── vision.py        # Qwen2-VL analysis
│   │   ├── reasoning.py     # DeepSeek reasoning
│   │   └── context.py       # Context tracking
│   ├── actions/
│   │   ├── __init__.py
│   │   ├── extractor.py     # Action item extraction
│   │   └── notifications.py # macOS notifications
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py      # SQLite operations
│   │   └── models.py        # Data models
│   ├── ui/
│   │   ├── __init__.py
│   │   └── menubar.py       # rumps menu bar app
│   └── config.py
├── tests/
├── pyproject.toml
└── README.md
```

## Implementation

### Phase 1: Screen Capture (Week 1)

#### Screen Capture with mss
```python
# src/capture/screen.py
import mss
import mss.tools
from PIL import Image
import io
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import subprocess
import json

@dataclass
class ScreenCapture:
    timestamp: datetime
    image: Image.Image
    active_app: Optional[str]
    active_window: Optional[str]

class ScreenCaptureService:
    def __init__(self, capture_dir: Path = Path("~/.screen-analysis/captures").expanduser()):
        self.capture_dir = capture_dir
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.sct = mss.mss()

    def capture(self, monitor: int = 1) -> ScreenCapture:
        """Capture the screen and get active window info."""
        # Capture screen
        screenshot = self.sct.grab(self.sct.monitors[monitor])
        image = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        # Get active window info
        active_app, active_window = self._get_active_window()

        return ScreenCapture(
            timestamp=datetime.now(),
            image=image,
            active_app=active_app,
            active_window=active_window
        )

    def _get_active_window(self) -> tuple[Optional[str], Optional[str]]:
        """Get the active application and window title using AppleScript."""
        script = '''
        tell application "System Events"
            set frontApp to name of first application process whose frontmost is true
            set frontWindow to ""
            try
                tell process frontApp
                    set frontWindow to name of front window
                end tell
            end try
            return frontApp & "|" & frontWindow
        end tell
        '''
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split("|")
                return parts[0], parts[1] if len(parts) > 1 else None
        except Exception:
            pass
        return None, None

    def save_capture(self, capture: ScreenCapture) -> Path:
        """Save capture to disk."""
        filename = f"{capture.timestamp.strftime('%Y%m%d_%H%M%S')}.png"
        filepath = self.capture_dir / filename
        capture.image.save(filepath, "PNG", optimize=True)
        return filepath
```

#### Periodic Capture Scheduler
```python
# src/capture/scheduler.py
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Optional
from capture.screen import ScreenCaptureService, ScreenCapture

class CaptureScheduler:
    def __init__(
        self,
        capture_service: ScreenCaptureService,
        interval_seconds: int = 30,
        on_capture: Optional[Callable[[ScreenCapture], None]] = None
    ):
        self.capture_service = capture_service
        self.interval = interval_seconds
        self.on_capture = on_capture
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start periodic capture."""
        self._running = True
        self._task = asyncio.create_task(self._capture_loop())

    async def stop(self):
        """Stop periodic capture."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _capture_loop(self):
        """Main capture loop."""
        while self._running:
            try:
                capture = self.capture_service.capture()

                if self.on_capture:
                    # Run callback (analysis) in background
                    asyncio.create_task(self._run_callback(capture))

            except Exception as e:
                print(f"Capture error: {e}")

            await asyncio.sleep(self.interval)

    async def _run_callback(self, capture: ScreenCapture):
        """Run the capture callback."""
        try:
            if asyncio.iscoroutinefunction(self.on_capture):
                await self.on_capture(capture)
            else:
                self.on_capture(capture)
        except Exception as e:
            print(f"Callback error: {e}")
```

### Phase 2: Vision Analysis (Week 1-2)

#### Qwen2-VL Vision Analyzer
```python
# src/analysis/vision.py
import httpx
import base64
from io import BytesIO
from PIL import Image
from dataclasses import dataclass
from typing import Optional

@dataclass
class VisionAnalysis:
    description: str
    detected_apps: list[str]
    detected_content: list[str]
    is_meeting: bool
    is_code: bool
    is_document: bool
    raw_text: Optional[str]

class VisionAnalyzer:
    def __init__(
        self,
        model: str = "qwen2-vl:7b",
        base_url: str = "http://localhost:11434"
    ):
        self.model = model
        self.base_url = base_url

    async def analyze(self, image: Image.Image) -> VisionAnalysis:
        """Analyze a screen capture using Qwen2-VL."""
        # Convert image to base64
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        prompt = """Analyze this screenshot and provide:
1. A brief description of what's on screen
2. What application(s) are visible
3. What type of content is shown (meeting, code, document, browser, etc.)
4. Any visible text that might be important
5. Whether this appears to be a video meeting

Format your response as JSON:
{
    "description": "...",
    "apps": ["..."],
    "content_types": ["..."],
    "important_text": ["..."],
    "is_meeting": true/false
}"""

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "images": [img_base64],
                    "stream": False,
                    "format": "json"
                }
            )

            result = response.json()
            analysis_text = result.get("response", "{}")

            # Parse JSON response
            import json
            try:
                data = json.loads(analysis_text)
            except json.JSONDecodeError:
                data = {}

            return VisionAnalysis(
                description=data.get("description", "Unable to analyze"),
                detected_apps=data.get("apps", []),
                detected_content=data.get("content_types", []),
                is_meeting=data.get("is_meeting", False),
                is_code="code" in str(data.get("content_types", [])).lower(),
                is_document="document" in str(data.get("content_types", [])).lower(),
                raw_text="\n".join(data.get("important_text", []))
            )
```

### Phase 3: Context Tracking (Week 2)

#### Context State Machine
```python
# src/analysis/context.py
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
from collections import deque

class ActivityType(Enum):
    CODING = "coding"
    MEETING = "meeting"
    BROWSING = "browsing"
    DOCUMENTS = "documents"
    COMMUNICATION = "communication"
    OTHER = "other"

@dataclass
class ContextState:
    activity_type: ActivityType
    start_time: datetime
    apps: set[str] = field(default_factory=set)
    duration: timedelta = timedelta()

@dataclass
class ContextSwitch:
    from_context: ContextState
    to_context: ContextState
    timestamp: datetime

class ContextTracker:
    def __init__(self, switch_threshold_minutes: int = 2):
        self.current_context: Optional[ContextState] = None
        self.context_history: deque[ContextState] = deque(maxlen=100)
        self.switch_threshold = timedelta(minutes=switch_threshold_minutes)
        self.on_context_switch: Optional[callable] = None

    def update(self, analysis: "VisionAnalysis", active_app: str) -> Optional[ContextSwitch]:
        """Update context based on new analysis."""
        # Determine activity type
        activity_type = self._determine_activity(analysis, active_app)

        now = datetime.now()

        if self.current_context is None:
            # First context
            self.current_context = ContextState(
                activity_type=activity_type,
                start_time=now,
                apps={active_app} if active_app else set()
            )
            return None

        # Check if context changed
        if activity_type != self.current_context.activity_type:
            # Context switch detected
            old_context = self.current_context
            old_context.duration = now - old_context.start_time

            # Save to history
            self.context_history.append(old_context)

            # Create new context
            self.current_context = ContextState(
                activity_type=activity_type,
                start_time=now,
                apps={active_app} if active_app else set()
            )

            switch = ContextSwitch(
                from_context=old_context,
                to_context=self.current_context,
                timestamp=now
            )

            if self.on_context_switch:
                self.on_context_switch(switch)

            return switch
        else:
            # Same context, update apps
            if active_app:
                self.current_context.apps.add(active_app)
            self.current_context.duration = now - self.current_context.start_time
            return None

    def _determine_activity(self, analysis: "VisionAnalysis", active_app: str) -> ActivityType:
        """Determine activity type from analysis."""
        if analysis.is_meeting:
            return ActivityType.MEETING

        if analysis.is_code:
            return ActivityType.CODING

        coding_apps = {"code", "cursor", "xcode", "terminal", "iterm", "warp"}
        if active_app and active_app.lower() in coding_apps:
            return ActivityType.CODING

        meeting_apps = {"zoom", "meet", "teams", "slack huddle", "facetime"}
        if active_app and any(m in active_app.lower() for m in meeting_apps):
            return ActivityType.MEETING

        browser_apps = {"safari", "chrome", "firefox", "arc", "brave"}
        if active_app and active_app.lower() in browser_apps:
            return ActivityType.BROWSING

        comm_apps = {"slack", "discord", "messages", "mail", "outlook"}
        if active_app and active_app.lower() in comm_apps:
            return ActivityType.COMMUNICATION

        if analysis.is_document:
            return ActivityType.DOCUMENTS

        return ActivityType.OTHER

    def get_daily_summary(self) -> dict[ActivityType, timedelta]:
        """Get time spent in each activity today."""
        today = datetime.now().date()
        summary = {t: timedelta() for t in ActivityType}

        for ctx in self.context_history:
            if ctx.start_time.date() == today:
                summary[ctx.activity_type] += ctx.duration

        # Add current context
        if self.current_context and self.current_context.start_time.date() == today:
            summary[self.current_context.activity_type] += (
                datetime.now() - self.current_context.start_time
            )

        return summary
```

### Phase 4: Action Extraction (Week 3)

#### DeepSeek Reasoning for Actions
```python
# src/actions/extractor.py
import httpx
from dataclasses import dataclass
from typing import Optional
import json

@dataclass
class ActionItem:
    description: str
    priority: str  # high, medium, low
    source: str    # meeting, document, etc.
    deadline: Optional[str]

class ActionExtractor:
    def __init__(
        self,
        model: str = "deepseek-r1:14b",
        base_url: str = "http://localhost:11434"
    ):
        self.model = model
        self.base_url = base_url

    async def extract_actions(
        self,
        vision_analysis: "VisionAnalysis",
        context: Optional[str] = None
    ) -> list[ActionItem]:
        """Extract action items from screen content."""

        prompt = f"""Analyze this screen content and extract any action items, tasks, or important notes.

Screen Description: {vision_analysis.description}
Detected Content: {', '.join(vision_analysis.detected_content)}
Visible Text: {vision_analysis.raw_text or 'None detected'}
Additional Context: {context or 'None'}

If this appears to be a meeting, look for:
- Action items assigned to anyone
- Decisions made
- Follow-up tasks mentioned

If this is a document or email, look for:
- Tasks or requests
- Deadlines mentioned
- Important information to remember

Return a JSON array of action items:
[
  {{
    "description": "Task description",
    "priority": "high|medium|low",
    "source": "meeting|document|email|chat",
    "deadline": "YYYY-MM-DD or null"
  }}
]

If no action items found, return an empty array: []"""

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )

            result = response.json()
            response_text = result.get("response", "[]")

            try:
                items = json.loads(response_text)
                return [
                    ActionItem(
                        description=item.get("description", ""),
                        priority=item.get("priority", "medium"),
                        source=item.get("source", "unknown"),
                        deadline=item.get("deadline")
                    )
                    for item in items
                    if item.get("description")
                ]
            except json.JSONDecodeError:
                return []
```

#### macOS Notifications
```python
# src/actions/notifications.py
import subprocess
from dataclasses import dataclass

@dataclass
class Notification:
    title: str
    message: str
    sound: bool = True

class NotificationService:
    def send(self, notification: Notification):
        """Send macOS notification using osascript."""
        sound_cmd = 'sound name "default"' if notification.sound else ""
        script = f'''
        display notification "{notification.message}" with title "{notification.title}" {sound_cmd}
        '''
        subprocess.run(["osascript", "-e", script], capture_output=True)

    def notify_context_switch(self, from_activity: str, to_activity: str, duration: str):
        """Notify user of context switch."""
        self.send(Notification(
            title="Context Switch",
            message=f"Switched from {from_activity} ({duration}) to {to_activity}",
            sound=False
        ))

    def notify_action_item(self, action: "ActionItem"):
        """Notify user of detected action item."""
        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(action.priority, "⚪")
        self.send(Notification(
            title=f"{priority_emoji} Action Detected",
            message=action.description[:100],
            sound=action.priority == "high"
        ))

    def notify_meeting_summary(self, summary: str, action_count: int):
        """Notify user of meeting summary."""
        self.send(Notification(
            title="Meeting Ended",
            message=f"{action_count} action items detected. {summary[:80]}",
            sound=True
        ))
```

### Phase 5: Storage (Week 3)

#### SQLite Database
```python
# src/storage/database.py
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

class Database:
    def __init__(self, db_path: Path = Path("~/.screen-analysis/data.db").expanduser()):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS captures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    active_app TEXT,
                    active_window TEXT,
                    image_path TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capture_id INTEGER REFERENCES captures(id),
                    description TEXT,
                    detected_apps TEXT,
                    detected_content TEXT,
                    is_meeting BOOLEAN,
                    raw_text TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS contexts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    activity_type TEXT NOT NULL,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    duration_seconds INTEGER,
                    apps TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS action_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capture_id INTEGER REFERENCES captures(id),
                    description TEXT NOT NULL,
                    priority TEXT,
                    source TEXT,
                    deadline DATE,
                    completed BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_captures_timestamp ON captures(timestamp);
                CREATE INDEX IF NOT EXISTS idx_contexts_start ON contexts(start_time);
                CREATE INDEX IF NOT EXISTS idx_actions_completed ON action_items(completed);
            ''')

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save_capture(
        self,
        timestamp: datetime,
        active_app: Optional[str],
        active_window: Optional[str],
        image_path: Optional[str]
    ) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute(
                '''INSERT INTO captures (timestamp, active_app, active_window, image_path)
                   VALUES (?, ?, ?, ?)''',
                (timestamp, active_app, active_window, image_path)
            )
            return cursor.lastrowid

    def save_analysis(self, capture_id: int, analysis: "VisionAnalysis"):
        with self._get_connection() as conn:
            conn.execute(
                '''INSERT INTO analyses
                   (capture_id, description, detected_apps, detected_content, is_meeting, raw_text)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (
                    capture_id,
                    analysis.description,
                    ",".join(analysis.detected_apps),
                    ",".join(analysis.detected_content),
                    analysis.is_meeting,
                    analysis.raw_text
                )
            )

    def save_action_item(self, capture_id: int, action: "ActionItem"):
        with self._get_connection() as conn:
            conn.execute(
                '''INSERT INTO action_items
                   (capture_id, description, priority, source, deadline)
                   VALUES (?, ?, ?, ?, ?)''',
                (capture_id, action.description, action.priority, action.source, action.deadline)
            )

    def get_pending_actions(self) -> list[dict]:
        with self._get_connection() as conn:
            rows = conn.execute(
                '''SELECT * FROM action_items WHERE completed = FALSE ORDER BY created_at DESC'''
            ).fetchall()
            return [dict(row) for row in rows]

    def get_daily_summary(self, date: datetime) -> dict:
        with self._get_connection() as conn:
            # Get context time breakdown
            contexts = conn.execute(
                '''SELECT activity_type, SUM(duration_seconds) as total
                   FROM contexts
                   WHERE DATE(start_time) = DATE(?)
                   GROUP BY activity_type''',
                (date,)
            ).fetchall()

            # Get action items
            actions = conn.execute(
                '''SELECT COUNT(*) as count, priority
                   FROM action_items
                   WHERE DATE(created_at) = DATE(?)
                   GROUP BY priority''',
                (date,)
            ).fetchall()

            return {
                "contexts": {row["activity_type"]: row["total"] for row in contexts},
                "actions": {row["priority"]: row["count"] for row in actions}
            }
```

### Phase 6: Menu Bar App (Week 3)

#### Full Menu Bar Implementation
```python
# src/ui/menubar.py
import rumps
import asyncio
import threading
from datetime import datetime, timedelta

from capture.screen import ScreenCaptureService
from capture.scheduler import CaptureScheduler
from analysis.vision import VisionAnalyzer
from analysis.context import ContextTracker, ActivityType
from actions.extractor import ActionExtractor
from actions.notifications import NotificationService
from storage.database import Database

class ScreenAnalysisApp(rumps.App):
    def __init__(self):
        super().__init__(
            "Screen Analysis",
            icon="👁️",
            quit_button=None
        )

        # Initialize services
        self.capture_service = ScreenCaptureService()
        self.vision_analyzer = VisionAnalyzer()
        self.context_tracker = ContextTracker()
        self.action_extractor = ActionExtractor()
        self.notifications = NotificationService()
        self.database = Database()

        # State
        self.is_running = False
        self.scheduler = None
        self.loop = None
        self.thread = None

        # Set up context switch notifications
        self.context_tracker.on_context_switch = self._on_context_switch

        # Menu
        self.menu = [
            rumps.MenuItem("Start Monitoring", callback=self.toggle_monitoring),
            None,
            rumps.MenuItem("Daily Summary", callback=self.show_summary),
            rumps.MenuItem("Pending Actions", callback=self.show_actions),
            None,
            rumps.MenuItem("Settings", callback=self.open_settings),
            rumps.MenuItem("Quit", callback=self.quit_app)
        ]

    def toggle_monitoring(self, sender):
        if self.is_running:
            self.stop_monitoring()
            sender.title = "Start Monitoring"
            self.icon = "👁️"
        else:
            self.start_monitoring()
            sender.title = "Stop Monitoring"
            self.icon = "🔴"

    def start_monitoring(self):
        self.is_running = True

        def run_async():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            self.scheduler = CaptureScheduler(
                capture_service=self.capture_service,
                interval_seconds=30,
                on_capture=self._process_capture
            )

            self.loop.run_until_complete(self.scheduler.start())
            self.loop.run_forever()

        self.thread = threading.Thread(target=run_async, daemon=True)
        self.thread.start()

        self.notifications.send(rumps.notification(
            "Screen Analysis",
            "Monitoring started",
            "Capturing every 30 seconds"
        ))

    def stop_monitoring(self):
        self.is_running = False
        if self.loop and self.scheduler:
            self.loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.scheduler.stop())
            )
            self.loop.call_soon_threadsafe(self.loop.stop)

    async def _process_capture(self, capture):
        """Process a screen capture."""
        try:
            # Save capture
            image_path = self.capture_service.save_capture(capture)
            capture_id = self.database.save_capture(
                capture.timestamp,
                capture.active_app,
                capture.active_window,
                str(image_path)
            )

            # Analyze with vision model
            analysis = await self.vision_analyzer.analyze(capture.image)
            self.database.save_analysis(capture_id, analysis)

            # Update context
            self.context_tracker.update(analysis, capture.active_app)

            # Extract actions if meeting or document
            if analysis.is_meeting or analysis.is_document:
                actions = await self.action_extractor.extract_actions(analysis)
                for action in actions:
                    self.database.save_action_item(capture_id, action)
                    if action.priority == "high":
                        self.notifications.notify_action_item(action)

        except Exception as e:
            print(f"Processing error: {e}")

    def _on_context_switch(self, switch):
        """Handle context switch notification."""
        duration = str(switch.from_context.duration).split(".")[0]  # Remove microseconds
        self.notifications.notify_context_switch(
            switch.from_context.activity_type.value,
            switch.to_context.activity_type.value,
            duration
        )

    def show_summary(self, sender):
        """Show daily summary."""
        summary = self.context_tracker.get_daily_summary()

        lines = ["Today's Activity:"]
        for activity, duration in summary.items():
            if duration.total_seconds() > 0:
                hours = duration.total_seconds() / 3600
                lines.append(f"  {activity.value}: {hours:.1f}h")

        rumps.alert(
            title="Daily Summary",
            message="\n".join(lines)
        )

    def show_actions(self, sender):
        """Show pending action items."""
        actions = self.database.get_pending_actions()

        if not actions:
            rumps.alert("No pending actions")
            return

        lines = [f"• {a['description'][:50]}..." for a in actions[:10]]
        rumps.alert(
            title=f"Pending Actions ({len(actions)})",
            message="\n".join(lines)
        )

    def open_settings(self, sender):
        # TODO: Settings window
        pass

    def quit_app(self, sender):
        self.stop_monitoring()
        rumps.quit_application()

if __name__ == "__main__":
    ScreenAnalysisApp().run()
```

---

## Configuration

```python
# src/config.py
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ScreenAnalysisConfig:
    # Capture settings
    capture_interval: int = 30  # seconds
    save_images: bool = True
    image_quality: int = 85

    # Models
    vision_model: str = "qwen2-vl:7b"
    reasoning_model: str = "deepseek-r1:14b"

    # Storage
    data_dir: Path = Path("~/.screen-analysis").expanduser()
    max_history_days: int = 30

    # Notifications
    notify_context_switch: bool = True
    notify_high_priority_actions: bool = True

    # Privacy
    blur_sensitive: bool = False
    excluded_apps: list[str] = None  # Apps to skip
```

---

## Timeline

| Week | Task |
|------|------|
| Week 1 | Screen capture + Vision analysis |
| Week 2 | Context tracking + Action extraction |
| Week 3 | Menu bar app + Storage + Notifications |

**Total: 3 weeks**
