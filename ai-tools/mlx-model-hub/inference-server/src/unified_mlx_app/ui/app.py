"""Modern Gradio UI for Unified MLX App."""

import logging
import tempfile
import wave
from typing import Generator

import gradio as gr
import numpy as np

from ..config import settings
from ..models import ModelType, model_manager
from ..storage import conversation_db, Conversation, Message
from .theme import CUSTOM_CSS, theme

logger = logging.getLogger(__name__)


# =============================================================================
# CHAT TAB
# =============================================================================
def create_chat_tab():
    """Create a modern chat interface with conversation persistence."""

    def chat_stream(
        message: str,
        history: list[dict],
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        selected_model: str,
        current_conv: Conversation | None,
    ) -> Generator[tuple[list[dict], Conversation | None], None, None]:
        """Stream chat responses with persistence."""
        if not message.strip():
            yield history, current_conv
            return

        from mlx_lm import stream_generate
        from mlx_lm.generate import make_sampler

        try:
            model, tokenizer = model_manager.get_text_model(selected_model)
        except Exception as e:
            history.append({"role": "assistant", "content": f"Error loading model: {e}"})
            yield history, current_conv
            return

        # Create sampler with temperature
        sampler = make_sampler(temp=temperature)

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
            for response in stream_generate(
                model, tokenizer, prompt=prompt, max_tokens=max_tokens, sampler=sampler
            ):
                assistant_content += response.text
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

        choices = [
            (f"{c['title'][:40]}..." if len(c["title"]) > 40 else c["title"], c["id"])
            for c in convos
        ]
        return gr.update(choices=choices, value=None)

    def load_selected_conversation(conv_id: int | None):
        """Load a conversation from the database."""
        if conv_id is None:
            return [], None

        conv = conversation_db.get_conversation(conv_id)
        if conv is None:
            return [], None

        history = [{"role": m.role, "content": m.content} for m in conv.messages]
        return history, conv

    def new_conversation():
        """Start a new conversation."""
        return [], None, gr.update(value=None)

    def delete_current_conversation(current_conv: Conversation | None):
        """Delete the current conversation."""
        if current_conv and current_conv.id:
            conversation_db.delete_conversation(current_conv.id)
            gr.Info("Conversation deleted")
        return [], None, load_conversation_list()

    def switch_model(model_name: str):
        """Switch to a different model."""
        gr.Info(f"Switching to {model_name.split('/')[-1]}...")
        try:
            model_manager.get_text_model(model_name, force_reload=True)
            gr.Info(f"Model loaded: {model_name.split('/')[-1]}")
        except Exception as e:
            gr.Warning(f"Failed to load model: {e}")
        return model_name

    with gr.Tab("Chat", elem_id="chat-tab"):
        # State for current conversation
        current_conv_state = gr.State(None)

        with gr.Row():
            with gr.Column(scale=4):
                chatbot = gr.Chatbot(
                    value=[],
                    height=480,
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

                model_selector = gr.Dropdown(
                    choices=settings.available_text_models,
                    value=settings.text_model,
                    label="Model",
                    info="Switch models (will reload)",
                    elem_classes=["model-selector"],
                )

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
            [msg, chatbot, system_prompt, temperature, max_tokens, model_selector, current_conv_state],
            [chatbot, current_conv_state],
        ).then(lambda: "", None, msg)

        send_btn.click(
            chat_stream,
            [msg, chatbot, system_prompt, temperature, max_tokens, model_selector, current_conv_state],
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
            [chatbot, current_conv_state],
        )

        delete_conv_btn.click(
            delete_current_conversation,
            current_conv_state,
            [chatbot, current_conv_state, conversation_list],
        )

        model_selector.change(
            switch_model,
            model_selector,
            model_selector,
        )


# =============================================================================
# VISION TAB
# =============================================================================
def create_vision_tab():
    """Create a modern vision analysis interface."""

    def analyze_image(
        image,
        prompt: str,
        history: list[dict],
        max_tokens: int,
    ) -> tuple[list[dict], str]:
        """Analyze image with vision model."""
        if image is None:
            gr.Warning("Please upload an image first")
            return history, prompt

        if not prompt.strip():
            prompt = "Describe this image in detail."

        try:
            model, processor = model_manager.get_vision_model()
        except Exception as e:
            history.append({"role": "assistant", "content": f"Error loading model: {e}"})
            return history, ""

        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template
        from mlx_vlm.utils import load_config
        import tempfile
        import os
        from ..config import settings

        try:
            # Add user message with image indicator
            history.append({"role": "user", "content": f"[Image uploaded] {prompt}"})

            # Save PIL image to temp file (mlx_vlm expects file path, not PIL object)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                image.save(tmp.name)
                temp_path = tmp.name

            try:
                # Load config and format prompt with chat template
                config = load_config(settings.vision_model)
                image_list = [temp_path]
                formatted_prompt = apply_chat_template(
                    processor, config, prompt, num_images=len(image_list)
                )

                # Generate with image as positional argument (required by mlx_vlm)
                result = generate(
                    model,
                    processor,
                    formatted_prompt,
                    image_list,
                    max_tokens=max_tokens,
                    verbose=False,
                )

                # Extract text from GenerationResult
                response_text = result.text if hasattr(result, 'text') else str(result)
                history.append({"role": "assistant", "content": response_text})
                return history, ""
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            history.append({"role": "assistant", "content": f"Analysis error: {e}"})
            return history, prompt

    with gr.Tab("Vision", elem_id="vision-tab"):
        with gr.Row(equal_height=True):
            with gr.Column(scale=2):
                gr.Markdown("### Upload Image", elem_classes=["section-header"])
                image_input = gr.Image(
                    label="",
                    type="pil",
                    height=350,
                    sources=["upload", "clipboard"],
                    elem_classes=["image-upload"],
                )

                with gr.Group():
                    vision_prompt = gr.Textbox(
                        value="Describe this image in detail.",
                        label="Prompt",
                        placeholder="What would you like to know about this image?",
                        lines=2,
                    )
                    with gr.Row():
                        vision_max_tokens = gr.Slider(
                            64, 2048, value=512, step=64, label="Max Tokens", scale=2
                        )
                        analyze_btn = gr.Button(
                            "Analyze",
                            variant="primary",
                            scale=1,
                            min_width=120,
                        )

            with gr.Column(scale=3):
                gr.Markdown("### Analysis", elem_classes=["section-header"])
                vision_chatbot = gr.Chatbot(
                    value=[],
                    height=480,
                    avatar_images=(None, "https://api.iconify.design/fluent-emoji:eyes.svg"),
                )
                clear_vision_btn = gr.Button("Clear", variant="secondary", size="sm")

        # Event handlers
        analyze_btn.click(
            analyze_image,
            [image_input, vision_prompt, vision_chatbot, vision_max_tokens],
            [vision_chatbot, vision_prompt],
        )

        vision_prompt.submit(
            analyze_image,
            [image_input, vision_prompt, vision_chatbot, vision_max_tokens],
            [vision_chatbot, vision_prompt],
        )

        clear_vision_btn.click(
            lambda: ([], None, "Describe this image in detail."),
            None,
            [vision_chatbot, image_input, vision_prompt],
        )


# =============================================================================
# SPEECH TAB
# =============================================================================
def create_speech_tab():
    """Create a modern text-to-speech interface."""

    def generate_speech(
        text: str, voice: str, speed: float
    ) -> tuple[str | None, str]:
        """Generate speech from text."""
        if not text.strip():
            gr.Warning("Please enter some text to convert")
            return None, ""

        try:
            model = model_manager.get_speech_model()
        except Exception as e:
            gr.Warning(f"Error loading model: {e}")
            return None, f"Error: {e}"

        try:
            gr.Info("Generating speech...")
            # Use model's generate method directly
            results = model.generate(
                text=text,
                lang_code=voice,
                speed=speed,
                verbose=False,
            )

            # Collect audio from results generator
            audio_segments = []
            for result in results:
                audio_segments.append(np.array(result.audio))

            if not audio_segments:
                return None, "No audio generated"

            # Concatenate all segments
            audio_array = np.concatenate(audio_segments) if len(audio_segments) > 1 else audio_segments[0]

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            sample_rate = getattr(model, 'sample_rate', 24000)
            with wave.open(temp_file.name, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                audio_int16 = (audio_array * 32767).astype(np.int16)
                wav_file.writeframes(audio_int16.tobytes())

            char_count = len(text)
            word_count = len(text.split())
            status = f"Generated {word_count} words ({char_count} characters)"

            return temp_file.name, status

        except Exception as e:
            gr.Warning(f"TTS error: {e}")
            return None, f"Error: {e}"

    with gr.Tab("Speech", elem_id="speech-tab"):
        with gr.Row(equal_height=True):
            with gr.Column(scale=3):
                gr.Markdown("### Text Input", elem_classes=["section-header"])

                speech_text = gr.Textbox(
                    placeholder="Enter the text you want to convert to speech...\n\nTip: Use punctuation for natural pauses.",
                    label="",
                    lines=8,
                    max_lines=15,
                    elem_classes=["speech-input"],
                )

                with gr.Row():
                    char_count = gr.Markdown("0 characters")

                speech_text.change(
                    lambda t: f"{len(t)} characters, ~{len(t.split())} words",
                    speech_text,
                    char_count,
                )

            with gr.Column(scale=2):
                gr.Markdown("### Voice Settings", elem_classes=["section-header"])

                voice_select = gr.Radio(
                    choices=[
                        ("American English", "a"),
                        ("British English", "b"),
                    ],
                    value="a",
                    label="Voice",
                    elem_classes=["voice-select"],
                )

                speed_slider = gr.Slider(
                    0.5,
                    2.0,
                    value=1.0,
                    step=0.1,
                    label="Speed",
                    info="0.5x (slow) to 2x (fast)",
                )

                generate_btn = gr.Button(
                    "Generate Speech",
                    variant="primary",
                    size="lg",
                    elem_classes=["generate-btn"],
                )

                gr.Markdown("---")

                gr.Markdown("### Output", elem_classes=["section-header"])

                audio_output = gr.Audio(
                    label="",
                    type="filepath",
                    elem_classes=["audio-output"],
                )

                status_text = gr.Markdown("")

        # Event handlers
        generate_btn.click(
            generate_speech,
            [speech_text, voice_select, speed_slider],
            [audio_output, status_text],
        )


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
                    elem_classes=["transcription-output"],
                )

                status_text = gr.Markdown("")

        # Event handlers
        transcribe_btn.click(
            transcribe_audio,
            [audio_input],
            [transcription_output, status_text],
        )


# =============================================================================
# IMAGE GENERATION TAB (Placeholder)
# =============================================================================
def create_image_tab():
    """Create a placeholder image generation interface for future models."""

    with gr.Tab("Image", elem_id="image-tab"):
        gr.Markdown("### Image Generation", elem_classes=["section-header"])

        # Coming Soon notice
        gr.HTML(
            """
            <div style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 16px;
                padding: 40px;
                text-align: center;
                color: white;
                margin: 20px 0;
            ">
                <div style="font-size: 3rem; margin-bottom: 16px;">🎨</div>
                <h2 style="margin: 0 0 12px 0; font-size: 1.5rem;">Coming Soon</h2>
                <p style="margin: 0; opacity: 0.9; max-width: 500px; margin: 0 auto;">
                    Image generation support is being prepared for future MLX models.
                    This tab will support FLUX, Stable Diffusion, and other image models
                    optimized for Apple Silicon.
                </p>
            </div>
            """
        )

        gr.Markdown("---")

        # Planned features section
        gr.Markdown("### Planned Features")

        with gr.Row():
            with gr.Column():
                gr.Markdown(
                    """
                    **Text-to-Image**
                    - FLUX.1 (schnell, dev)
                    - Z-Image-Turbo (fast, 9 steps)
                    - Stable Diffusion 3.5
                    """
                )

            with gr.Column():
                gr.Markdown(
                    """
                    **Image Editing**
                    - FLUX Kontext (in-context editing)
                    - Inpainting & outpainting
                    - Style transfer
                    """
                )

            with gr.Column():
                gr.Markdown(
                    """
                    **Optimizations**
                    - 4-bit & 8-bit quantization
                    - LoRA support
                    - Batch generation
                    """
                )

        gr.Markdown("---")

        # Interface preview (disabled)
        gr.Markdown("### Interface Preview")

        with gr.Row():
            with gr.Column(scale=2):
                prompt_preview = gr.Textbox(
                    label="Prompt",
                    placeholder="A serene mountain landscape at sunset, digital art style...",
                    lines=3,
                    interactive=False,
                )

                with gr.Row():
                    gr.Slider(
                        1, 50, value=20, step=1, label="Steps", interactive=False
                    )
                    gr.Slider(
                        1, 20, value=7.5, step=0.5, label="CFG Scale", interactive=False
                    )

                with gr.Row():
                    gr.Dropdown(
                        choices=["512x512", "768x768", "1024x1024"],
                        value="1024x1024",
                        label="Size",
                        interactive=False,
                    )
                    gr.Button(
                        "Generate",
                        variant="primary",
                        interactive=False,
                    )

            with gr.Column(scale=2):
                gr.Image(
                    label="Output",
                    height=300,
                    interactive=False,
                    show_label=True,
                )

        gr.Markdown(
            """
            <div style="text-align: center; color: #64748b; margin-top: 20px;">
                <em>This interface is a preview. Enable by installing mflux when ready.</em>
            </div>
            """,
            elem_classes=["preview-note"],
        )


# =============================================================================
# PIPELINE TAB
# =============================================================================
def create_pipeline_tab():
    """Create a modern multi-modal pipeline interface."""

    def describe_and_speak(
        image,
        prompt: str,
        voice: str,
        speed: float,
        progress=gr.Progress(),
    ) -> tuple[str, str | None, str]:
        """Analyze image and convert description to speech."""
        if image is None:
            return "Please upload an image first.", None, ""

        # Step 1: Vision Analysis
        progress(0.1, desc="Loading vision model...")
        try:
            model, processor = model_manager.get_vision_model()
        except Exception as e:
            return f"Error loading vision model: {e}", None, ""

        progress(0.3, desc="Analyzing image...")
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template
        from mlx_vlm.utils import load_config
        import tempfile
        import os
        from ..config import settings

        try:
            # Save PIL image to temp file (mlx_vlm expects file path, not PIL object)
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                image.save(tmp.name)
                temp_path = tmp.name

            try:
                # Load config and format prompt with chat template
                config = load_config(settings.vision_model)
                image_list = [temp_path]
                formatted_prompt = apply_chat_template(
                    processor, config, prompt, num_images=len(image_list)
                )

                # Generate with image as positional argument (required by mlx_vlm)
                result = generate(
                    model,
                    processor,
                    formatted_prompt,
                    image_list,
                    max_tokens=256,
                    verbose=False,
                )
                # Extract text from GenerationResult
                description = result.text if hasattr(result, 'text') else str(result)
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        except Exception as e:
            return f"Vision error: {e}", None, ""

        # Step 2: Speech Synthesis
        progress(0.6, desc="Loading speech model...")
        try:
            speech_model = model_manager.get_speech_model()
        except Exception as e:
            return description, None, "Vision complete, but TTS failed to load"

        progress(0.8, desc="Generating speech...")
        try:
            # Use model's generate method directly
            results = speech_model.generate(
                text=description,
                lang_code=voice,
                speed=speed,
                verbose=False,
            )

            # Collect audio from results generator
            audio_segments = []
            for result in results:
                audio_segments.append(np.array(result.audio))

            if not audio_segments:
                return description, None, "No audio generated"

            audio_array = np.concatenate(audio_segments) if len(audio_segments) > 1 else audio_segments[0]

            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            sample_rate = getattr(speech_model, 'sample_rate', 24000)
            with wave.open(temp_file.name, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)
                audio_int16 = (audio_array * 32767).astype(np.int16)
                wav_file.writeframes(audio_int16.tobytes())

            progress(1.0, desc="Complete!")
            return description, temp_file.name, "Pipeline complete!"

        except Exception as e:
            return description, None, f"TTS error: {e}"

    with gr.Tab("Pipeline", elem_id="pipeline-tab"):
        gr.Markdown(
            """
            ### Describe & Speak Pipeline
            Upload an image and get an AI-generated description read aloud.
            """,
            elem_classes=["section-header"],
        )

        # Pipeline visualization
        with gr.Row(elem_classes=["pipeline-steps"]):
            with gr.Column(scale=1, min_width=150):
                gr.Markdown(
                    """
                    <div class="pipeline-step">
                        <div class="step-number">1</div>
                        <div>Upload Image</div>
                    </div>
                    """,
                    elem_classes=["step-card"],
                )
            with gr.Column(scale=1, min_width=150):
                gr.Markdown(
                    """
                    <div class="pipeline-step">
                        <div class="step-number">2</div>
                        <div>AI Analysis</div>
                    </div>
                    """,
                    elem_classes=["step-card"],
                )
            with gr.Column(scale=1, min_width=150):
                gr.Markdown(
                    """
                    <div class="pipeline-step">
                        <div class="step-number">3</div>
                        <div>Generate Speech</div>
                    </div>
                    """,
                    elem_classes=["step-card"],
                )

        gr.Markdown("---")

        with gr.Row(equal_height=True):
            with gr.Column(scale=2):
                pipeline_image = gr.Image(
                    label="Input Image",
                    type="pil",
                    height=300,
                    sources=["upload", "clipboard"],
                )

                pipeline_prompt = gr.Textbox(
                    value="Describe this image in 2-3 sentences, focusing on the main subject and mood.",
                    label="Description Prompt",
                    lines=2,
                )

            with gr.Column(scale=1):
                gr.Markdown("#### Voice Settings")

                pipeline_voice = gr.Radio(
                    choices=[
                        ("American", "a"),
                        ("British", "b"),
                    ],
                    value="a",
                    label="Accent",
                )

                pipeline_speed = gr.Slider(
                    0.5, 2.0, value=1.0, step=0.1, label="Speed"
                )

                run_pipeline_btn = gr.Button(
                    "Run Pipeline",
                    variant="primary",
                    size="lg",
                )

        gr.Markdown("---")

        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("#### Generated Description")
                pipeline_description = gr.Textbox(
                    label="",
                    lines=4,
                    interactive=False,
                    elem_classes=["description-output"],
                )

            with gr.Column(scale=1):
                gr.Markdown("#### Audio Output")
                pipeline_audio = gr.Audio(
                    label="",
                    type="filepath",
                )
                pipeline_status = gr.Markdown("")

        # Event handlers
        run_pipeline_btn.click(
            describe_and_speak,
            [pipeline_image, pipeline_prompt, pipeline_voice, pipeline_speed],
            [pipeline_description, pipeline_audio, pipeline_status],
        )


# =============================================================================
# STATUS TAB
# =============================================================================
def get_memory_stats() -> dict:
    """Get current memory usage statistics."""
    import psutil

    process = psutil.Process()
    mem_info = process.memory_info()

    return {
        "rss_gb": mem_info.rss / (1024**3),
        "vms_gb": mem_info.vms / (1024**3),
        "percent": process.memory_percent(),
    }


def create_status_tab():
    """Create an enhanced model status dashboard with memory monitoring."""

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
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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

    def refresh_status():
        return get_status_html()

    def unload_model_action(model_type: str):
        type_map = {
            "text": ModelType.TEXT,
            "vision": ModelType.VISION,
            "speech": ModelType.SPEECH,
            "stt": ModelType.STT,
        }
        if model_type in type_map:
            success = model_manager.unload_model(type_map[model_type])
            if success:
                gr.Info(f"{model_type.upper()} model unloaded")
            else:
                gr.Warning(f"{model_type.upper()} model was not loaded")
        return get_status_html()

    with gr.Tab("Status", elem_id="status-tab"):
        gr.Markdown("### Model Status", elem_classes=["section-header"])

        status_display = gr.HTML(get_status_html())

        with gr.Row():
            refresh_btn = gr.Button(
                "Refresh Status",
                variant="secondary",
                size="sm",
            )

        gr.Markdown("---")

        gr.Markdown("### Memory Management", elem_classes=["section-header"])
        gr.Markdown(
            "Unload models to free up memory when not in use. Models will reload automatically when needed."
        )

        with gr.Row():
            unload_text_btn = gr.Button("Unload Text", size="sm")
            unload_vision_btn = gr.Button("Unload Vision", size="sm")
            unload_speech_btn = gr.Button("Unload Speech", size="sm")
            unload_stt_btn = gr.Button("Unload STT", size="sm")

        gr.Markdown("---")

        gr.Markdown("### API Information", elem_classes=["section-header"])

        with gr.Row():
            with gr.Column():
                gr.Markdown(
                    f"""
                    **OpenAI-Compatible API**

                    ```
                    Base URL: http://localhost:{settings.api_port}/v1
                    ```

                    **Endpoints:**
                    - `POST /v1/chat/completions` - Text generation
                    - `POST /v1/audio/speech` - Text-to-speech
                    - `POST /v1/audio/transcriptions` - Speech-to-text
                    - `GET /v1/models` - List models
                    - `GET /health` - Health check
                    """
                )

            with gr.Column():
                gr.Markdown(
                    f"""
                    **Configuration**

                    | Setting | Value |
                    |---------|-------|
                    | UI Port | `{settings.ui_port}` |
                    | API Port | `{settings.api_port}` |
                    | Lazy Load | `{settings.lazy_load}` |
                    """
                )

        # Event handlers
        refresh_btn.click(refresh_status, None, status_display)
        unload_text_btn.click(lambda: unload_model_action("text"), None, status_display)
        unload_vision_btn.click(lambda: unload_model_action("vision"), None, status_display)
        unload_speech_btn.click(lambda: unload_model_action("speech"), None, status_display)
        unload_stt_btn.click(lambda: unload_model_action("stt"), None, status_display)


# =============================================================================
# MAIN UI
# =============================================================================
def create_ui() -> gr.Blocks:
    """Create the complete modern Gradio UI."""
    with gr.Blocks(
        title="Unified MLX AI",
        elem_id="main-app",
    ) as demo:
        # Header
        gr.HTML(
            """
            <div class="app-header">
                <h1>Unified MLX AI</h1>
                <p>Local AI inference for text, vision, speech & more - powered by Apple Silicon</p>
                <div style="display: flex; gap: 12px; justify-content: center; flex-wrap: wrap;">
                    <div class="api-badge">
                        API: http://localhost:8080/v1
                    </div>
                    <div class="api-badge" style="background: rgba(118, 75, 162, 0.2);">
                        MCP: http://localhost:8080/mcp
                    </div>
                </div>
            </div>
            """
        )

        # Tabs
        with gr.Tabs(elem_classes=["main-tabs"]):
            create_chat_tab()
            create_vision_tab()
            create_image_tab()
            create_speech_tab()
            create_transcribe_tab()
            create_pipeline_tab()
            create_status_tab()

        # Footer
        gr.HTML(
            """
            <div style="text-align: center; padding: 1.5rem; color: #64748b; font-size: 0.875rem;">
                Built with MLX, Gradio, and FastAPI
            </div>
            """
        )

    return demo
