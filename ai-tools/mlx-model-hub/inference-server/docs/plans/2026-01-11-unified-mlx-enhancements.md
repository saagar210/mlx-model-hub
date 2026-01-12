# Unified MLX Enhancements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add speech-to-text, conversation persistence, model hot-swapping, enhanced status dashboard, background task queue, and response caching to the Unified MLX App.

**Architecture:** Extend the existing ModelManager with a new STT model type. Add SQLite database for conversation storage. Implement async task processing with Gradio's built-in progress tracking. Add caching layer with TTL for repeated queries.

**Tech Stack:** mlx-audio STT (Whisper), SQLite via aiosqlite, asyncio for background tasks, diskcache for response caching

---

## Task 1: Add Speech-to-Text Model Support

**Files:**
- Modify: `src/unified_mlx_app/models/manager.py`
- Modify: `src/unified_mlx_app/config.py`

**Step 1: Add STT model to config**

In `src/unified_mlx_app/config.py`, add after line 17:

```python
    stt_model: str = "mlx-community/whisper-large-v3-turbo"
```

**Step 2: Add STT to ModelType enum**

In `src/unified_mlx_app/models/manager.py`, modify the ModelType enum (lines 13-18):

```python
class ModelType(Enum):
    """Types of models supported."""

    TEXT = "text"
    VISION = "vision"
    SPEECH = "speech"
    STT = "stt"
```

**Step 3: Add STT to ModelManager __init__**

In `src/unified_mlx_app/models/manager.py`, update `__init__` (lines 38-53):

```python
    def __init__(self):
        self._models: dict[ModelType, LoadedModel | None] = {
            ModelType.TEXT: None,
            ModelType.VISION: None,
            ModelType.SPEECH: None,
            ModelType.STT: None,
        }
        self._locks: dict[ModelType, Lock] = {
            ModelType.TEXT: Lock(),
            ModelType.VISION: Lock(),
            ModelType.SPEECH: Lock(),
            ModelType.STT: Lock(),
        }
        self._loading: dict[ModelType, bool] = {
            ModelType.TEXT: False,
            ModelType.VISION: False,
            ModelType.SPEECH: False,
            ModelType.STT: False,
        }
```

**Step 4: Add get_stt_model method**

In `src/unified_mlx_app/models/manager.py`, add after `get_speech_model` method (after line 169):

```python
    def get_stt_model(self, model_path: str | None = None):
        """Get or load the speech-to-text model."""
        from ..config import settings

        model_path = model_path or settings.stt_model

        with self._locks[ModelType.STT]:
            if self._models[ModelType.STT] is not None:
                loaded = self._models[ModelType.STT]
                if loaded.model_path == model_path:
                    loaded.last_used = time.time()
                    return loaded.model

            self._loading[ModelType.STT] = True

        try:
            logger.info(f"Loading STT model: {model_path}")
            from mlx_audio.stt.utils import load_model

            model = load_model(model_path)

            with self._locks[ModelType.STT]:
                self._models[ModelType.STT] = LoadedModel(
                    model=model,
                    model_path=model_path,
                    model_type=ModelType.STT,
                )
                self._loading[ModelType.STT] = False

            logger.info(f"STT model loaded: {model_path}")
            return model

        except Exception as e:
            with self._locks[ModelType.STT]:
                self._loading[ModelType.STT] = False
            logger.error(f"Failed to load STT model: {e}")
            raise
```

**Step 5: Run the app to verify no errors**

```bash
cd ~/claude-code/ai-tools/unified-mlx-app && python run.py
```

Expected: App starts without errors. STT not visible in UI yet.

**Step 6: Commit**

```bash
git add src/unified_mlx_app/models/manager.py src/unified_mlx_app/config.py
git commit -m "feat: add speech-to-text model support to ModelManager

- Add STT model type to ModelType enum
- Add get_stt_model method using mlx-audio whisper
- Configure default model: whisper-large-v3-turbo"
```

---

## Task 2: Create Transcribe Tab UI

**Files:**
- Modify: `src/unified_mlx_app/ui/app.py`

**Step 1: Add create_transcribe_tab function**

In `src/unified_mlx_app/ui/app.py`, add after `create_speech_tab` function (after line 388):

```python
# =============================================================================
# TRANSCRIBE TAB
# =============================================================================
def create_transcribe_tab():
    """Create a speech-to-text transcription interface."""

    def transcribe_audio(
        audio_file,
        progress=gr.Progress(),
    ) -> tuple[str, str]:
        """Transcribe audio file to text."""
        if audio_file is None:
            return "", "Please upload or record an audio file"

        progress(0.1, desc="Loading STT model...")
        try:
            model = model_manager.get_stt_model()
        except Exception as e:
            return "", f"Error loading model: {e}"

        progress(0.3, desc="Transcribing audio...")
        try:
            # Generate transcription
            result = model.generate(audio_file, verbose=False)

            progress(1.0, desc="Complete!")

            word_count = len(result.text.split())
            status = f"Transcribed {word_count} words"

            return result.text, status

        except Exception as e:
            return "", f"Transcription error: {e}"

    with gr.Tab("Transcribe", elem_id="transcribe-tab"):
        with gr.Row(equal_height=True):
            with gr.Column(scale=2):
                gr.Markdown("### Audio Input", elem_classes=["section-header"])

                audio_input = gr.Audio(
                    label="",
                    type="filepath",
                    sources=["upload", "microphone"],
                    elem_classes=["audio-input"],
                )

                transcribe_btn = gr.Button(
                    "Transcribe",
                    variant="primary",
                    size="lg",
                    elem_classes=["transcribe-btn"],
                )

            with gr.Column(scale=3):
                gr.Markdown("### Transcription", elem_classes=["section-header"])

                transcription_output = gr.Textbox(
                    label="",
                    lines=12,
                    max_lines=20,
                    show_copy_button=True,
                    elem_classes=["transcription-output"],
                )

                status_text = gr.Markdown("")

        # Event handlers
        transcribe_btn.click(
            transcribe_audio,
            [audio_input],
            [transcription_output, status_text],
        )
```

**Step 2: Add Transcribe tab to main UI**

In `src/unified_mlx_app/ui/app.py`, modify `create_ui` function (around line 748-753):

```python
        # Tabs
        with gr.Tabs(elem_classes=["main-tabs"]):
            create_chat_tab()
            create_vision_tab()
            create_speech_tab()
            create_transcribe_tab()
            create_pipeline_tab()
            create_status_tab()
```

**Step 3: Update Status tab with STT model**

In `src/unified_mlx_app/ui/app.py`, modify `get_status_html` in `create_status_tab` (around line 581-597):

```python
        models_info = {
            "text": {
                "name": "Text Generation",
                "icon": "https://api.iconify.design/fluent-emoji:speech-balloon.svg",
                "model": settings.text_model,
            },
            "vision": {
                "name": "Vision Analysis",
                "icon": "https://api.iconify.design/fluent-emoji:eyes.svg",
                "model": settings.vision_model,
            },
            "speech": {
                "name": "Speech Synthesis",
                "icon": "https://api.iconify.design/fluent-emoji:speaker-high-volume.svg",
                "model": settings.speech_model,
            },
            "stt": {
                "name": "Speech-to-Text",
                "icon": "https://api.iconify.design/fluent-emoji:microphone.svg",
                "model": settings.stt_model,
            },
        }
```

**Step 4: Add unload button for STT**

In `src/unified_mlx_app/ui/app.py`, modify the unload buttons section (around line 676-679):

```python
        with gr.Row():
            unload_text_btn = gr.Button("Unload Text", size="sm")
            unload_vision_btn = gr.Button("Unload Vision", size="sm")
            unload_speech_btn = gr.Button("Unload Speech", size="sm")
            unload_stt_btn = gr.Button("Unload STT", size="sm")
```

And add the event handler (around line 718-720):

```python
        unload_stt_btn.click(lambda: unload_model_action("stt"), None, status_display)
```

**Step 5: Test the Transcribe tab**

```bash
cd ~/claude-code/ai-tools/unified-mlx-app && python run.py
```

Expected: New "Transcribe" tab appears. Can upload audio and get transcription.

**Step 6: Commit**

```bash
git add src/unified_mlx_app/ui/app.py
git commit -m "feat: add Transcribe tab for speech-to-text

- New tab with audio upload and microphone input
- Displays transcription with word count
- Added STT to status dashboard and memory management"
```

---

## Task 3: Add STT API Endpoint

**Files:**
- Modify: `src/unified_mlx_app/api/routes.py`
- Modify: `src/unified_mlx_app/api/schemas.py`

**Step 1: Add TranscriptionRequest schema**

In `src/unified_mlx_app/api/schemas.py`, add at the end of the file:

```python
class TranscriptionRequest(BaseModel):
    """Request for audio transcription."""

    model: str = "mlx-community/whisper-large-v3-turbo"
    language: str | None = None


class TranscriptionResponse(BaseModel):
    """Response from transcription."""

    text: str
    duration: float | None = None
    language: str | None = None
```

**Step 2: Add transcription endpoint**

In `src/unified_mlx_app/api/routes.py`, add at the end of the file:

```python
from fastapi import UploadFile, File, Form
import tempfile
import os


@router.post("/v1/audio/transcriptions")
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form(default="mlx-community/whisper-large-v3-turbo"),
):
    """OpenAI-compatible audio transcription endpoint."""
    try:
        stt_model = model_manager.get_stt_model(model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load model: {e}")

    # Save uploaded file to temp location
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    try:
        content = await file.read()
        temp_file.write(content)
        temp_file.close()

        # Generate transcription
        result = stt_model.generate(temp_file.name, verbose=False)

        return {"text": result.text}

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp file
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
```

**Step 3: Update imports in routes.py**

At the top of `src/unified_mlx_app/api/routes.py`, ensure these imports exist:

```python
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
```

**Step 4: Test the API endpoint**

```bash
# Start the app
cd ~/claude-code/ai-tools/unified-mlx-app && python run.py &

# Test with curl (use any .wav file)
curl -X POST "http://localhost:8080/v1/audio/transcriptions" \
  -F "file=@test.wav" \
  -F "model=mlx-community/whisper-large-v3-turbo"
```

Expected: Returns JSON with transcribed text.

**Step 5: Commit**

```bash
git add src/unified_mlx_app/api/routes.py src/unified_mlx_app/api/schemas.py
git commit -m "feat: add OpenAI-compatible transcription API endpoint

- POST /v1/audio/transcriptions endpoint
- Accepts audio file upload with model selection
- Returns transcribed text"
```

---

## Task 4: Add Conversation Persistence with SQLite

**Files:**
- Create: `src/unified_mlx_app/storage/__init__.py`
- Create: `src/unified_mlx_app/storage/database.py`
- Modify: `src/unified_mlx_app/ui/app.py`
- Modify: `pyproject.toml`

**Step 1: Add aiosqlite dependency**

In `pyproject.toml`, add to dependencies (line 21):

```python
    "aiosqlite>=0.19.0",
```

**Step 2: Create storage package**

Create `src/unified_mlx_app/storage/__init__.py`:

```python
"""Storage module for conversation persistence."""

from .database import ConversationDB, Conversation, Message

__all__ = ["ConversationDB", "Conversation", "Message"]
```

**Step 3: Create database module**

Create `src/unified_mlx_app/storage/database.py`:

```python
"""SQLite database for conversation persistence."""

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Message:
    """A single message in a conversation."""
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class Conversation:
    """A conversation with messages."""
    id: Optional[int] = None
    title: str = "New Conversation"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    messages: list[Message] = field(default_factory=list)
    model_type: str = "chat"  # chat, vision


class ConversationDB:
    """SQLite database for storing conversations."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            # Default to ~/.unified-mlx/conversations.db
            db_dir = Path.home() / ".unified-mlx"
            db_dir.mkdir(exist_ok=True)
            db_path = db_dir / "conversations.db"

        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    model_type TEXT DEFAULT 'chat',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    messages TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_updated_at
                ON conversations(updated_at DESC)
            """)
            conn.commit()

    def save_conversation(self, conv: Conversation) -> int:
        """Save or update a conversation. Returns the conversation ID."""
        messages_json = json.dumps([
            {"role": m.role, "content": m.content, "timestamp": m.timestamp}
            for m in conv.messages
        ])

        with sqlite3.connect(self.db_path) as conn:
            if conv.id is None:
                cursor = conn.execute(
                    """INSERT INTO conversations
                       (title, model_type, created_at, updated_at, messages)
                       VALUES (?, ?, ?, ?, ?)""",
                    (conv.title, conv.model_type, conv.created_at, time.time(), messages_json)
                )
                conv.id = cursor.lastrowid
            else:
                conn.execute(
                    """UPDATE conversations
                       SET title=?, messages=?, updated_at=?
                       WHERE id=?""",
                    (conv.title, messages_json, time.time(), conv.id)
                )
            conn.commit()

        return conv.id

    def get_conversation(self, conv_id: int) -> Optional[Conversation]:
        """Load a conversation by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM conversations WHERE id=?", (conv_id,)
            ).fetchone()

            if row is None:
                return None

            messages_data = json.loads(row["messages"])
            messages = [
                Message(role=m["role"], content=m["content"], timestamp=m.get("timestamp", 0))
                for m in messages_data
            ]

            return Conversation(
                id=row["id"],
                title=row["title"],
                model_type=row["model_type"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                messages=messages,
            )

    def list_conversations(self, limit: int = 50, model_type: str | None = None) -> list[dict]:
        """List recent conversations (metadata only)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if model_type:
                rows = conn.execute(
                    """SELECT id, title, model_type, created_at, updated_at
                       FROM conversations
                       WHERE model_type=?
                       ORDER BY updated_at DESC LIMIT ?""",
                    (model_type, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, title, model_type, created_at, updated_at
                       FROM conversations
                       ORDER BY updated_at DESC LIMIT ?""",
                    (limit,)
                ).fetchall()

            return [dict(row) for row in rows]

    def delete_conversation(self, conv_id: int) -> bool:
        """Delete a conversation."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM conversations WHERE id=?", (conv_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def generate_title(self, messages: list[Message]) -> str:
        """Generate a title from the first user message."""
        for msg in messages:
            if msg.role == "user":
                # Take first 50 chars of first user message
                title = msg.content[:50]
                if len(msg.content) > 50:
                    title += "..."
                return title
        return "New Conversation"


# Global singleton
conversation_db = ConversationDB()
```

**Step 4: Commit the storage module**

```bash
git add src/unified_mlx_app/storage/ pyproject.toml
git commit -m "feat: add SQLite storage for conversation persistence

- ConversationDB class with save/load/list/delete
- Stores conversations at ~/.unified-mlx/conversations.db
- Auto-generates titles from first user message"
```

---

## Task 5: Integrate Persistence into Chat Tab

**Files:**
- Modify: `src/unified_mlx_app/ui/app.py`

**Step 1: Add storage import**

At the top of `src/unified_mlx_app/ui/app.py`, add:

```python
from ..storage import conversation_db, Conversation, Message
```

**Step 2: Replace create_chat_tab with persistence-enabled version**

Replace the entire `create_chat_tab` function (lines 21-158) with:

```python
def create_chat_tab():
    """Create a modern chat interface with conversation persistence."""

    # State for current conversation
    current_conv_state = gr.State(None)

    def chat_stream(
        message: str,
        history: list[dict],
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        current_conv: Conversation | None,
    ) -> Generator[tuple[list[dict], Conversation | None], None, None]:
        """Stream chat responses with modern message format."""
        if not message.strip():
            yield history, current_conv
            return

        from mlx_lm import stream_generate

        try:
            model, tokenizer = model_manager.get_text_model()
        except Exception as e:
            history.append({"role": "assistant", "content": f"Error loading model: {e}"})
            yield history, current_conv
            return

        # Build message list for tokenizer
        messages = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt})

        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": message})

        # Add user message to history
        history.append({"role": "user", "content": message})

        # Initialize conversation if needed
        if current_conv is None:
            current_conv = Conversation(model_type="chat")

        # Add user message to conversation
        current_conv.messages.append(Message(role="user", content=message))

        yield history, current_conv

        # Generate prompt
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        # Stream response
        history.append({"role": "assistant", "content": ""})
        assistant_content = ""

        try:
            for token in stream_generate(
                model, tokenizer, prompt=prompt, max_tokens=max_tokens, temp=temperature
            ):
                assistant_content += token
                history[-1]["content"] = assistant_content
                yield history, current_conv

            # Save assistant message and persist
            current_conv.messages.append(Message(role="assistant", content=assistant_content))

            # Auto-generate title if this is first exchange
            if current_conv.title == "New Conversation" and len(current_conv.messages) >= 2:
                current_conv.title = conversation_db.generate_title(current_conv.messages)

            # Save to database
            conversation_db.save_conversation(current_conv)

            yield history, current_conv

        except Exception as e:
            history[-1]["content"] = f"Generation error: {e}"
            yield history, current_conv

    def load_conversation_list():
        """Load list of saved conversations."""
        convos = conversation_db.list_conversations(limit=20, model_type="chat")
        if not convos:
            return gr.update(choices=[], value=None)

        choices = [(f"{c['title'][:40]}...", c["id"]) if len(c["title"]) > 40
                   else (c["title"], c["id"]) for c in convos]
        return gr.update(choices=choices, value=None)

    def load_selected_conversation(conv_id: int | None):
        """Load a conversation from the database."""
        if conv_id is None:
            return [], None, gr.update()

        conv = conversation_db.get_conversation(conv_id)
        if conv is None:
            return [], None, gr.update()

        history = [{"role": m.role, "content": m.content} for m in conv.messages]
        return history, conv, gr.update()

    def new_conversation():
        """Start a new conversation."""
        return [], None, gr.update(value=None)

    def delete_current_conversation(current_conv: Conversation | None):
        """Delete the current conversation."""
        if current_conv and current_conv.id:
            conversation_db.delete_conversation(current_conv.id)
            gr.Info("Conversation deleted")
        return [], None, load_conversation_list()

    with gr.Tab("Chat", elem_id="chat-tab"):
        with gr.Row():
            with gr.Column(scale=4):
                chatbot = gr.Chatbot(
                    value=[],
                    height=480,
                    type="messages",
                    show_copy_button=True,
                    avatar_images=(None, "https://api.iconify.design/fluent-emoji:robot.svg"),
                    elem_classes=["chatbot-container"],
                )

                with gr.Group():
                    with gr.Row():
                        msg = gr.Textbox(
                            placeholder="Type your message here... (Shift+Enter for new line)",
                            label="",
                            lines=2,
                            max_lines=6,
                            scale=6,
                            container=False,
                            elem_classes=["chat-input"],
                        )
                        send_btn = gr.Button(
                            "Send",
                            variant="primary",
                            scale=1,
                            min_width=100,
                            elem_classes=["send-btn"],
                        )

            with gr.Column(scale=1, min_width=280):
                gr.Markdown("### Conversations", elem_classes=["section-header"])

                with gr.Row():
                    new_conv_btn = gr.Button("New", size="sm", scale=1)
                    refresh_btn = gr.Button("Refresh", size="sm", scale=1)

                conversation_list = gr.Dropdown(
                    label="",
                    choices=[],
                    interactive=True,
                    elem_classes=["conversation-list"],
                )

                delete_conv_btn = gr.Button(
                    "Delete Conversation",
                    variant="stop",
                    size="sm",
                )

                gr.Markdown("---")
                gr.Markdown("### Settings", elem_classes=["section-header"])

                system_prompt = gr.Textbox(
                    value="You are a helpful, friendly AI assistant. Provide clear, accurate, and concise responses.",
                    label="System Prompt",
                    lines=3,
                    elem_classes=["settings-input"],
                )

                temperature = gr.Slider(
                    0.0,
                    2.0,
                    value=0.7,
                    step=0.05,
                    label="Temperature",
                    info="Higher = more creative",
                )

                max_tokens = gr.Slider(
                    64,
                    4096,
                    value=1024,
                    step=64,
                    label="Max Tokens",
                    info="Maximum response length",
                )

        # Event handlers
        msg.submit(
            chat_stream,
            [msg, chatbot, system_prompt, temperature, max_tokens, current_conv_state],
            [chatbot, current_conv_state],
        ).then(lambda: "", None, msg)

        send_btn.click(
            chat_stream,
            [msg, chatbot, system_prompt, temperature, max_tokens, current_conv_state],
            [chatbot, current_conv_state],
        ).then(lambda: "", None, msg)

        new_conv_btn.click(
            new_conversation,
            None,
            [chatbot, current_conv_state, conversation_list],
        )

        refresh_btn.click(
            load_conversation_list,
            None,
            conversation_list,
        )

        conversation_list.change(
            load_selected_conversation,
            conversation_list,
            [chatbot, current_conv_state, conversation_list],
        )

        delete_conv_btn.click(
            delete_current_conversation,
            current_conv_state,
            [chatbot, current_conv_state, conversation_list],
        )

        # Load conversations on tab load
        demo = gr.Blocks.current_context
        if demo:
            demo.load(load_conversation_list, None, conversation_list)
```

**Step 3: Test conversation persistence**

```bash
cd ~/claude-code/ai-tools/unified-mlx-app && python run.py
```

Expected:
- Chat tab has conversation list sidebar
- Messages are saved automatically
- Can load previous conversations
- Can delete conversations

**Step 4: Commit**

```bash
git add src/unified_mlx_app/ui/app.py
git commit -m "feat: integrate conversation persistence into Chat tab

- Conversations auto-save to SQLite
- Conversation list dropdown in sidebar
- New/Load/Delete conversation controls
- Auto-generated titles from first user message"
```

---

## Task 6: Add Model Hot-Swapping

**Files:**
- Modify: `src/unified_mlx_app/config.py`
- Modify: `src/unified_mlx_app/ui/app.py`
- Modify: `src/unified_mlx_app/models/manager.py`

**Step 1: Add available models to config**

In `src/unified_mlx_app/config.py`, add after line 17:

```python
    # Available model options
    available_text_models: list[str] = [
        "mlx-community/Qwen2.5-7B-Instruct-4bit",
        "mlx-community/Qwen2.5-3B-Instruct-4bit",
        "mlx-community/Qwen2.5-1.5B-Instruct-4bit",
        "mlx-community/Llama-3.2-3B-Instruct-4bit",
    ]
    available_vision_models: list[str] = [
        "mlx-community/Qwen2-VL-2B-Instruct-4bit",
        "mlx-community/Qwen2-VL-7B-Instruct-4bit",
    ]
    available_stt_models: list[str] = [
        "mlx-community/whisper-large-v3-turbo",
        "mlx-community/whisper-large-v3",
        "mlx-community/whisper-small",
    ]
```

**Step 2: Add force_reload parameter to model getters**

In `src/unified_mlx_app/models/manager.py`, modify `get_text_model` (starting at line 55):

```python
    def get_text_model(self, model_path: str | None = None, force_reload: bool = False):
        """Get or load the text generation model."""
        from ..config import settings

        model_path = model_path or settings.text_model

        with self._locks[ModelType.TEXT]:
            if self._models[ModelType.TEXT] is not None and not force_reload:
                loaded = self._models[ModelType.TEXT]
                if loaded.model_path == model_path:
                    loaded.last_used = time.time()
                    return loaded.model, loaded.tokenizer
                # Different model requested, unload first
                self._models[ModelType.TEXT] = None
                import gc
                gc.collect()

            self._loading[ModelType.TEXT] = True
```

Apply similar changes to `get_vision_model` and `get_stt_model`.

**Step 3: Add model selector to Chat settings**

In `src/unified_mlx_app/ui/app.py`, within `create_chat_tab`, add model selector after system_prompt:

```python
                model_selector = gr.Dropdown(
                    choices=settings.available_text_models,
                    value=settings.text_model,
                    label="Model",
                    info="Switch models (will reload)",
                    elem_classes=["model-selector"],
                )
```

And add a handler function:

```python
    def switch_model(model_name: str):
        """Switch to a different model."""
        gr.Info(f"Switching to {model_name.split('/')[-1]}...")
        try:
            model_manager.get_text_model(model_name, force_reload=True)
            gr.Info(f"Model loaded: {model_name.split('/')[-1]}")
        except Exception as e:
            gr.Warning(f"Failed to load model: {e}")
        return model_name
```

And bind the event:

```python
        model_selector.change(
            switch_model,
            model_selector,
            model_selector,
        )
```

**Step 4: Test model hot-swapping**

```bash
cd ~/claude-code/ai-tools/unified-mlx-app && python run.py
```

Expected: Can select different models from dropdown, model reloads.

**Step 5: Commit**

```bash
git add src/unified_mlx_app/config.py src/unified_mlx_app/models/manager.py src/unified_mlx_app/ui/app.py
git commit -m "feat: add model hot-swapping

- Model selector dropdown in Chat settings
- force_reload parameter for model switching
- Configurable list of available models
- Graceful unload before loading new model"
```

---

## Task 7: Enhanced Status Dashboard

**Files:**
- Modify: `src/unified_mlx_app/ui/app.py`

**Step 1: Add memory monitoring function**

In `src/unified_mlx_app/ui/app.py`, add helper function before `create_status_tab`:

```python
def get_memory_stats() -> dict:
    """Get current memory usage statistics."""
    import psutil

    process = psutil.Process()
    mem_info = process.memory_info()

    return {
        "rss_gb": mem_info.rss / (1024 ** 3),
        "vms_gb": mem_info.vms / (1024 ** 3),
        "percent": process.memory_percent(),
    }
```

**Step 2: Update pyproject.toml with psutil**

In `pyproject.toml`, add to dependencies:

```python
    "psutil>=5.9.0",
```

**Step 3: Enhance status dashboard HTML**

In `create_status_tab`, replace `get_status_html` function:

```python
    def get_status_html():
        """Generate HTML for enhanced model status dashboard."""
        status = model_manager.get_status()
        memory = get_memory_stats()

        models_info = {
            "text": {
                "name": "Text Generation",
                "icon": "https://api.iconify.design/fluent-emoji:speech-balloon.svg",
                "model": settings.text_model,
                "size": "~4GB",
            },
            "vision": {
                "name": "Vision Analysis",
                "icon": "https://api.iconify.design/fluent-emoji:eyes.svg",
                "model": settings.vision_model,
                "size": "~1.5GB",
            },
            "speech": {
                "name": "Speech Synthesis",
                "icon": "https://api.iconify.design/fluent-emoji:speaker-high-volume.svg",
                "model": settings.speech_model,
                "size": "~200MB",
            },
            "stt": {
                "name": "Speech-to-Text",
                "icon": "https://api.iconify.design/fluent-emoji:microphone.svg",
                "model": settings.stt_model,
                "size": "~1.5GB",
            },
        }

        # Memory overview card
        memory_html = f"""
        <div class="memory-overview" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
             border-radius: 12px; padding: 20px; margin-bottom: 20px; color: white;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-size: 0.875rem; opacity: 0.9;">Process Memory</div>
                    <div style="font-size: 2rem; font-weight: bold;">{memory['rss_gb']:.2f} GB</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 0.875rem; opacity: 0.9;">System Usage</div>
                    <div style="font-size: 1.5rem; font-weight: bold;">{memory['percent']:.1f}%</div>
                </div>
            </div>
            <div style="margin-top: 12px; height: 8px; background: rgba(255,255,255,0.3); border-radius: 4px;">
                <div style="height: 100%; width: {min(memory['percent'], 100)}%; background: white; border-radius: 4px;"></div>
            </div>
        </div>
        """

        cards_html = ""
        loaded_count = 0
        for model_type, info in status.items():
            model_info = models_info.get(model_type, {})
            name = model_info.get("name", model_type.upper())
            icon = model_info.get("icon", "")
            model_path = model_info.get("model", "")
            size = model_info.get("size", "")

            if info.get("loaded"):
                status_class = "status-loaded"
                status_text = "Loaded"
                loaded_count += 1
                border_color = "#22c55e"
            elif info.get("loading"):
                status_class = "status-loading"
                status_text = "Loading..."
                border_color = "#f59e0b"
            else:
                status_class = "status-unloaded"
                status_text = "Not Loaded"
                border_color = "#94a3b8"

            cards_html += f"""
            <div class="model-card" style="border-left: 4px solid {border_color};">
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
                    <img src="{icon}" width="32" height="32" style="border-radius: 8px;">
                    <div style="flex: 1;">
                        <div class="model-name">{name}</div>
                        <div class="model-status">{model_path.split('/')[-1]}</div>
                    </div>
                    <div style="font-size: 0.75rem; color: #64748b;">{size}</div>
                </div>
                <div class="status-badge {status_class}">
                    <span>{status_text}</span>
                </div>
            </div>
            """

        summary = f"{loaded_count} of {len(status)} models loaded"

        return f"""
        {memory_html}
        <div style="margin-bottom: 12px; font-size: 0.875rem; color: #64748b;">{summary}</div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;">
            {cards_html}
        </div>
        """
```

**Step 4: Test enhanced dashboard**

```bash
cd ~/claude-code/ai-tools/unified-mlx-app && python run.py
```

Expected: Status tab shows memory usage bar, model sizes, improved visual design.

**Step 5: Commit**

```bash
git add src/unified_mlx_app/ui/app.py pyproject.toml
git commit -m "feat: enhanced status dashboard with memory monitoring

- Real-time process memory display
- Memory usage progress bar
- Model size estimates
- Improved visual design with color-coded status"
```

---

## Task 8: Add Response Caching

**Files:**
- Create: `src/unified_mlx_app/cache/__init__.py`
- Create: `src/unified_mlx_app/cache/response_cache.py`
- Modify: `pyproject.toml`

**Step 1: Add diskcache dependency**

In `pyproject.toml`, add to dependencies:

```python
    "diskcache>=5.6.0",
```

**Step 2: Create cache package**

Create `src/unified_mlx_app/cache/__init__.py`:

```python
"""Caching module for response optimization."""

from .response_cache import ResponseCache, response_cache

__all__ = ["ResponseCache", "response_cache"]
```

**Step 3: Create response cache module**

Create `src/unified_mlx_app/cache/response_cache.py`:

```python
"""Response caching for repeated queries."""

import hashlib
import logging
from pathlib import Path
from typing import Any

from diskcache import Cache

logger = logging.getLogger(__name__)


class ResponseCache:
    """Disk-based cache for LLM responses."""

    def __init__(self, cache_dir: str | Path | None = None, ttl_seconds: int = 3600):
        if cache_dir is None:
            cache_dir = Path.home() / ".unified-mlx" / "cache"

        self.cache = Cache(str(cache_dir))
        self.ttl = ttl_seconds
        logger.info(f"Response cache initialized at {cache_dir}")

    def _make_key(self, prompt: str, model: str, **params) -> str:
        """Generate cache key from prompt and parameters."""
        # Include relevant params in key
        key_parts = [prompt, model]
        for k, v in sorted(params.items()):
            if k in ("temperature", "max_tokens", "top_p"):
                key_parts.append(f"{k}:{v}")

        key_str = "|".join(str(p) for p in key_parts)
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]

    def get(self, prompt: str, model: str, **params) -> str | None:
        """Get cached response if available."""
        key = self._make_key(prompt, model, **params)
        result = self.cache.get(key)
        if result is not None:
            logger.debug(f"Cache hit for key {key[:8]}...")
        return result

    def set(self, prompt: str, model: str, response: str, **params) -> None:
        """Cache a response."""
        key = self._make_key(prompt, model, **params)
        self.cache.set(key, response, expire=self.ttl)
        logger.debug(f"Cached response for key {key[:8]}...")

    def clear(self) -> int:
        """Clear all cached responses. Returns count of items cleared."""
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"Cleared {count} cached responses")
        return count

    def stats(self) -> dict:
        """Get cache statistics."""
        return {
            "size": len(self.cache),
            "volume_bytes": self.cache.volume(),
        }


# Global singleton
response_cache = ResponseCache()
```

**Step 4: Integrate cache into API routes**

In `src/unified_mlx_app/api/routes.py`, add cache usage to chat completions:

```python
from ..cache import response_cache

# In chat_completions function, before generation:
# Check cache for non-streaming requests
if not request.stream:
    cache_params = {
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
    }
    cached = response_cache.get(prompt, request.model, **cache_params)
    if cached:
        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=cached),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

# After generation, cache the result:
response_cache.set(prompt, request.model, response_text, **cache_params)
```

**Step 5: Add cache controls to Status tab**

In `create_status_tab`, add cache section:

```python
        gr.Markdown("---")
        gr.Markdown("### Cache", elem_classes=["section-header"])

        cache_stats = gr.Markdown("")

        def get_cache_stats():
            from ..cache import response_cache
            stats = response_cache.stats()
            return f"**{stats['size']}** cached responses ({stats['volume_bytes'] / 1024:.1f} KB)"

        def clear_cache():
            from ..cache import response_cache
            count = response_cache.clear()
            gr.Info(f"Cleared {count} cached responses")
            return get_cache_stats()

        clear_cache_btn = gr.Button("Clear Cache", size="sm")
        clear_cache_btn.click(clear_cache, None, cache_stats)

        # Update stats on tab load
        demo.load(get_cache_stats, None, cache_stats)
```

**Step 6: Test caching**

```bash
cd ~/claude-code/ai-tools/unified-mlx-app && python run.py

# Make same API request twice - second should be instant
curl -X POST "http://localhost:8080/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model": "mlx-community/Qwen2.5-7B-Instruct-4bit", "messages": [{"role": "user", "content": "Hello"}]}'
```

Expected: Second identical request returns instantly from cache.

**Step 7: Commit**

```bash
git add src/unified_mlx_app/cache/ src/unified_mlx_app/api/routes.py src/unified_mlx_app/ui/app.py pyproject.toml
git commit -m "feat: add response caching for repeated queries

- Disk-based cache with configurable TTL
- SHA256 key generation from prompt + params
- Cache controls in Status dashboard
- Non-streaming API requests are cached"
```

---

## Summary

After completing all tasks, the Unified MLX App will have:

1. **Speech-to-Text** - New Transcribe tab + API endpoint using Whisper
2. **Conversation Persistence** - SQLite storage with load/save/delete
3. **Model Hot-Swapping** - Dropdown to switch models without restart
4. **Enhanced Status Dashboard** - Memory monitoring, model sizes, visual improvements
5. **Response Caching** - Disk cache for repeated API queries

**Total estimated tasks:** 8 major tasks, ~40 individual steps

**New dependencies:**
- aiosqlite
- psutil
- diskcache
