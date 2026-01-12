"""MCP Tool definitions for Unified MLX App.

These tools allow Claude Desktop/Code to use local MLX models.
"""

from typing import Any

# Tool definitions following MCP spec
TOOLS = [
    {
        "name": "generate_text",
        "description": "Generate text using local MLX language model (Qwen2.5). Use for chat, writing, coding, analysis.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt or question to send to the model",
                },
                "system_prompt": {
                    "type": "string",
                    "description": "Optional system prompt to set context/behavior",
                    "default": "You are a helpful assistant.",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum tokens to generate",
                    "default": 1024,
                },
                "temperature": {
                    "type": "number",
                    "description": "Sampling temperature (0.0-2.0). Higher = more creative.",
                    "default": 0.7,
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "analyze_image",
        "description": "Analyze an image using local MLX vision model (Qwen2-VL). Describe contents, extract text, answer questions about images.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Absolute path to the image file (PNG, JPG, etc.)",
                },
                "prompt": {
                    "type": "string",
                    "description": "Question or instruction about the image",
                    "default": "Describe this image in detail.",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum tokens to generate",
                    "default": 512,
                },
            },
            "required": ["image_path"],
        },
    },
    {
        "name": "speak_text",
        "description": "Convert text to speech using local MLX TTS model (Kokoro). Returns path to generated audio file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to convert to speech",
                },
                "voice": {
                    "type": "string",
                    "description": "Voice to use: 'a' for American English, 'b' for British English",
                    "default": "a",
                    "enum": ["a", "b"],
                },
                "speed": {
                    "type": "number",
                    "description": "Speech speed (0.5-2.0). 1.0 is normal.",
                    "default": 1.0,
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional output path for audio file. If not provided, saves to temp directory.",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "transcribe_audio",
        "description": "Transcribe audio to text using local MLX Whisper model. Supports WAV, MP3, M4A, etc.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "audio_path": {
                    "type": "string",
                    "description": "Absolute path to the audio file",
                },
            },
            "required": ["audio_path"],
        },
    },
    {
        "name": "get_model_status",
        "description": "Get status of loaded MLX models and memory usage.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def get_tool_by_name(name: str) -> dict[str, Any] | None:
    """Get a tool definition by name."""
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None
