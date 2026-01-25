# Project 4: Voice AI Assistant

## Overview
A real-time voice assistant using Pipecat for audio streaming, MLX Whisper for local STT, and DeepSeek R1 for reasoning. Supports both local and cloud LLMs with sub-200ms response latency.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Voice AI Assistant                           │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                         Pipecat Pipeline                            │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  │  Audio   │──▶│   VAD    │──▶│   STT    │──▶│   LLM    │        │
│  │  Input   │   │ (Silero) │   │(Whisper) │   │(DeepSeek)│        │
│  └──────────┘   └──────────┘   └──────────┘   └────┬─────┘        │
│                                                     │              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐       │              │
│  │  Audio   │◀──│   TTS    │◀──│ Response │◀──────┘              │
│  │  Output  │   │(CosyVoice│   │ Stream   │                       │
│  └──────────┘   └──────────┘   └──────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   Ollama     │       │   Claude     │       │  Knowledge   │
│ (DeepSeek)   │       │     API      │       │   Engine     │
│   Local      │       │    Cloud     │       │  (RAG/MCP)   │
└──────────────┘       └──────────────┘       └──────────────┘
```

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Audio Pipeline** | Pipecat | Production-grade, <200ms latency |
| **VAD** | Silero VAD | Best open-source, runs on CPU |
| **STT** | MLX Whisper | Apple Silicon optimized, local |
| **LLM (Local)** | DeepSeek R1 14B | Best reasoning at size |
| **LLM (Cloud)** | Claude 3.5 Sonnet | Fallback for complex tasks |
| **TTS** | CosyVoice / Edge TTS | Natural sounding, low latency |
| **Menu Bar** | rumps | Native macOS integration |

## Project Structure

```
voice-assistant/
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── pipeline.py          # Pipecat pipeline configuration
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── stt.py           # MLX Whisper processor
│   │   ├── llm.py           # LLM processor (local/cloud)
│   │   ├── tts.py           # TTS processor
│   │   └── vad.py           # Voice activity detection
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ollama.py        # Ollama client
│   │   ├── claude.py        # Claude API client
│   │   └── knowledge.py     # Knowledge Engine MCP client
│   ├── ui/
│   │   ├── __init__.py
│   │   └── menubar.py       # rumps menu bar app
│   └── config.py            # Configuration
├── tests/
│   ├── test_pipeline.py
│   ├── test_stt.py
│   └── test_llm.py
├── pyproject.toml
└── README.md
```

## Implementation

### Phase 1: Core Pipeline (Week 1)

#### Basic Pipecat Pipeline
```python
# src/pipeline.py
from pipecat.pipeline import Pipeline
from pipecat.transports.local import LocalAudioTransport
from pipecat.vad.silero import SileroVADAnalyzer
from pipecat.processors.frame_processor import FrameProcessor

from processors.stt import MLXWhisperProcessor
from processors.llm import OllamaProcessor
from processors.tts import CosyVoiceProcessor

class VoiceAssistantPipeline:
    def __init__(self, config: dict):
        self.config = config
        self.pipeline = None

    async def create_pipeline(self) -> Pipeline:
        # Audio transport
        transport = LocalAudioTransport(
            sample_rate=16000,
            channels=1
        )

        # VAD for speech detection
        vad = SileroVADAnalyzer(
            sample_rate=16000,
            min_speech_duration_ms=250,
            min_silence_duration_ms=300
        )

        # STT processor
        stt = MLXWhisperProcessor(
            model="mlx-community/whisper-large-v3-mlx",
            language="en"
        )

        # LLM processor
        llm = OllamaProcessor(
            model="deepseek-r1:14b",
            system_prompt=self.config.get("system_prompt", "You are a helpful assistant.")
        )

        # TTS processor
        tts = CosyVoiceProcessor(
            voice="en-US-AriaNeural"
        )

        # Build pipeline
        self.pipeline = Pipeline([
            transport.input(),
            vad,
            stt,
            llm,
            tts,
            transport.output()
        ])

        return self.pipeline

    async def run(self):
        pipeline = await self.create_pipeline()
        await pipeline.run()
```

#### MLX Whisper Processor
```python
# src/processors/stt.py
import mlx_whisper
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames import AudioFrame, TextFrame

class MLXWhisperProcessor(FrameProcessor):
    def __init__(self, model: str = "mlx-community/whisper-large-v3-mlx", language: str = "en"):
        super().__init__()
        self.model = model
        self.language = language
        self._audio_buffer = []

    async def process_frame(self, frame):
        if isinstance(frame, AudioFrame):
            self._audio_buffer.append(frame.audio)

            # Process when we have enough audio
            if len(self._audio_buffer) >= 16:  # ~1 second
                audio_data = b"".join(self._audio_buffer)
                self._audio_buffer = []

                # Transcribe with MLX Whisper
                result = mlx_whisper.transcribe(
                    audio_data,
                    path_or_hf_repo=self.model,
                    language=self.language
                )

                if result["text"].strip():
                    await self.push_frame(TextFrame(text=result["text"]))
        else:
            await self.push_frame(frame)
```

### Phase 2: LLM Integration (Week 2)

#### Ollama Processor with Streaming
```python
# src/processors/llm.py
import httpx
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames import TextFrame, LLMResponseFrame

class OllamaProcessor(FrameProcessor):
    def __init__(
        self,
        model: str = "deepseek-r1:14b",
        system_prompt: str = "You are a helpful voice assistant.",
        base_url: str = "http://localhost:11434"
    ):
        super().__init__()
        self.model = model
        self.system_prompt = system_prompt
        self.base_url = base_url
        self.conversation_history = []

    async def process_frame(self, frame):
        if isinstance(frame, TextFrame):
            user_message = frame.text

            # Add to history
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })

            # Build messages
            messages = [
                {"role": "system", "content": self.system_prompt}
            ] + self.conversation_history[-10:]  # Keep last 10 turns

            # Stream response from Ollama
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": True
                    }
                ) as response:
                    full_response = ""
                    async for line in response.aiter_lines():
                        if line:
                            import json
                            data = json.loads(line)
                            if "message" in data:
                                chunk = data["message"].get("content", "")
                                full_response += chunk
                                # Stream chunks for low latency TTS
                                if chunk.endswith((".", "!", "?", ",")):
                                    await self.push_frame(
                                        LLMResponseFrame(text=full_response)
                                    )
                                    full_response = ""

                    # Push remaining text
                    if full_response:
                        await self.push_frame(LLMResponseFrame(text=full_response))

            # Add assistant response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": full_response
            })
        else:
            await self.push_frame(frame)
```

#### Claude Fallback Processor
```python
# src/processors/llm_claude.py
import anthropic
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames import TextFrame, LLMResponseFrame

class ClaudeProcessor(FrameProcessor):
    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        system_prompt: str = "You are a helpful voice assistant."
    ):
        super().__init__()
        self.client = anthropic.Anthropic()
        self.model = model
        self.system_prompt = system_prompt
        self.conversation_history = []

    async def process_frame(self, frame):
        if isinstance(frame, TextFrame):
            self.conversation_history.append({
                "role": "user",
                "content": frame.text
            })

            # Stream response
            with self.client.messages.stream(
                model=self.model,
                max_tokens=1024,
                system=self.system_prompt,
                messages=self.conversation_history[-10:]
            ) as stream:
                full_response = ""
                buffer = ""
                for text in stream.text_stream:
                    buffer += text
                    # Send at sentence boundaries
                    if text.endswith((".", "!", "?", ",")):
                        await self.push_frame(LLMResponseFrame(text=buffer))
                        full_response += buffer
                        buffer = ""

                if buffer:
                    await self.push_frame(LLMResponseFrame(text=buffer))
                    full_response += buffer

            self.conversation_history.append({
                "role": "assistant",
                "content": full_response
            })
        else:
            await self.push_frame(frame)
```

### Phase 3: TTS Integration (Week 2)

#### CosyVoice / Edge TTS Processor
```python
# src/processors/tts.py
import edge_tts
import io
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.frames import LLMResponseFrame, AudioFrame

class EdgeTTSProcessor(FrameProcessor):
    def __init__(self, voice: str = "en-US-AriaNeural"):
        super().__init__()
        self.voice = voice

    async def process_frame(self, frame):
        if isinstance(frame, LLMResponseFrame):
            text = frame.text
            if text.strip():
                # Generate speech
                communicate = edge_tts.Communicate(text, self.voice)
                audio_buffer = io.BytesIO()

                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_buffer.write(chunk["data"])

                audio_data = audio_buffer.getvalue()
                if audio_data:
                    await self.push_frame(AudioFrame(audio=audio_data))
        else:
            await self.push_frame(frame)
```

### Phase 4: Menu Bar App (Week 3)

#### rumps Menu Bar Integration
```python
# src/ui/menubar.py
import rumps
import asyncio
import threading
from pipeline import VoiceAssistantPipeline

class VoiceAssistantApp(rumps.App):
    def __init__(self):
        super().__init__(
            "Voice Assistant",
            icon="🎤",
            quit_button=None
        )
        self.pipeline = None
        self.is_listening = False
        self.loop = None
        self.thread = None

        # Menu items
        self.menu = [
            rumps.MenuItem("Start Listening", callback=self.toggle_listening),
            rumps.MenuItem("Settings", callback=self.open_settings),
            None,  # Separator
            rumps.MenuItem("Use Local LLM", callback=self.toggle_local),
            rumps.MenuItem("Use Claude", callback=self.toggle_cloud),
            None,
            rumps.MenuItem("Quit", callback=self.quit_app)
        ]

        self.config = {
            "use_local": True,
            "model": "deepseek-r1:14b",
            "system_prompt": "You are a helpful voice assistant. Keep responses concise."
        }

    def toggle_listening(self, sender):
        if self.is_listening:
            self.stop_listening()
            sender.title = "Start Listening"
            self.icon = "🎤"
        else:
            self.start_listening()
            sender.title = "Stop Listening"
            self.icon = "🔴"

    def start_listening(self):
        self.is_listening = True

        def run_pipeline():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            self.pipeline = VoiceAssistantPipeline(self.config)
            self.loop.run_until_complete(self.pipeline.run())

        self.thread = threading.Thread(target=run_pipeline, daemon=True)
        self.thread.start()

        rumps.notification(
            "Voice Assistant",
            "Listening started",
            "Say something to begin..."
        )

    def stop_listening(self):
        self.is_listening = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)

        rumps.notification(
            "Voice Assistant",
            "Listening stopped",
            ""
        )

    def toggle_local(self, sender):
        self.config["use_local"] = True
        rumps.notification("Voice Assistant", "Switched to Local LLM", "Using DeepSeek R1")

    def toggle_cloud(self, sender):
        self.config["use_local"] = False
        rumps.notification("Voice Assistant", "Switched to Claude", "Using Claude 3.5 Sonnet")

    def open_settings(self, sender):
        # Open settings window or preferences
        pass

    def quit_app(self, sender):
        self.stop_listening()
        rumps.quit_application()

if __name__ == "__main__":
    VoiceAssistantApp().run()
```

### Phase 5: Knowledge Integration (Week 3)

#### MCP Knowledge Client
```python
# src/services/knowledge.py
import httpx
from typing import Optional

class KnowledgeService:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    async def search(self, query: str, top_k: int = 3) -> list[dict]:
        """Search knowledge base for relevant context."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/search",
                params={"q": query, "top_k": top_k}
            )
            return response.json()

    async def get_context(self, query: str) -> str:
        """Get formatted context for LLM."""
        results = await self.search(query)
        if not results:
            return ""

        context_parts = []
        for result in results:
            context_parts.append(f"- {result['content'][:500]}")

        return "\n".join(context_parts)
```

#### Enhanced LLM with RAG
```python
# src/processors/llm_rag.py
from processors.llm import OllamaProcessor
from services.knowledge import KnowledgeService

class RAGOllamaProcessor(OllamaProcessor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.knowledge = KnowledgeService()

    async def process_frame(self, frame):
        if isinstance(frame, TextFrame):
            user_message = frame.text

            # Get relevant context from knowledge base
            context = await self.knowledge.get_context(user_message)

            # Enhance system prompt with context
            enhanced_prompt = self.system_prompt
            if context:
                enhanced_prompt += f"\n\nRelevant context:\n{context}"

            # Store original and swap
            original_prompt = self.system_prompt
            self.system_prompt = enhanced_prompt

            # Process with parent
            await super().process_frame(frame)

            # Restore
            self.system_prompt = original_prompt
        else:
            await self.push_frame(frame)
```

---

## Configuration

```python
# src/config.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class VoiceConfig:
    # Audio
    sample_rate: int = 16000
    channels: int = 1

    # STT
    whisper_model: str = "mlx-community/whisper-large-v3-mlx"
    language: str = "en"

    # LLM
    use_local: bool = True
    local_model: str = "deepseek-r1:14b"
    cloud_model: str = "claude-3-5-sonnet-20241022"

    # TTS
    tts_voice: str = "en-US-AriaNeural"

    # Knowledge
    knowledge_url: Optional[str] = "http://localhost:8000"
    use_rag: bool = True

    # System
    system_prompt: str = """You are a helpful voice assistant running locally on a Mac.
Keep responses concise and conversational.
If you need to provide code or detailed information, suggest opening a text interface instead."""
```

---

## Testing

```python
# tests/test_pipeline.py
import pytest
from unittest.mock import AsyncMock, patch
from processors.stt import MLXWhisperProcessor
from processors.llm import OllamaProcessor

@pytest.mark.asyncio
async def test_whisper_processor():
    processor = MLXWhisperProcessor()
    # Mock audio frame
    # Test transcription

@pytest.mark.asyncio
async def test_ollama_processor():
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.stream.return_value = AsyncMock()

        processor = OllamaProcessor()
        # Test streaming response

@pytest.mark.asyncio
async def test_full_pipeline():
    # Integration test with mocked components
    pass
```

---

## Timeline

| Week | Task |
|------|------|
| Week 1 | Pipecat pipeline + MLX Whisper STT |
| Week 2 | Ollama/Claude LLM + Edge TTS integration |
| Week 3 | Menu bar app + Knowledge RAG |

**Total: 3 weeks**

---

## Usage

### Start the Voice Assistant
```bash
# Run as menu bar app
python -m voice_assistant.ui.menubar

# Or run directly
python -m voice_assistant.main
```

### Configuration
```bash
# Set environment variables
export ANTHROPIC_API_KEY="your-key"  # For Claude fallback
export OLLAMA_HOST="http://localhost:11434"
```
