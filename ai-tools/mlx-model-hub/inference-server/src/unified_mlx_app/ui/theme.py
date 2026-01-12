"""Custom theme for Unified MLX App."""

from gradio.themes.base import Base
from gradio.themes.utils import colors, fonts, sizes


class UnifiedMLXTheme(Base):
    """Modern, sleek theme for the Unified MLX App."""

    def __init__(
        self,
        *,
        primary_hue: colors.Color | str = colors.indigo,
        secondary_hue: colors.Color | str = colors.purple,
        neutral_hue: colors.Color | str = colors.slate,
        spacing_size: sizes.Size | str = sizes.spacing_md,
        radius_size: sizes.Size | str = sizes.radius_lg,
        text_size: sizes.Size | str = sizes.text_md,
    ):
        super().__init__(
            primary_hue=primary_hue,
            secondary_hue=secondary_hue,
            neutral_hue=neutral_hue,
            spacing_size=spacing_size,
            radius_size=radius_size,
            text_size=text_size,
            font=(
                fonts.GoogleFont("Inter"),
                "ui-sans-serif",
                "system-ui",
                "sans-serif",
            ),
            font_mono=(
                fonts.GoogleFont("JetBrains Mono"),
                "ui-monospace",
                "monospace",
            ),
        )

        # Light mode - using only supported properties
        self.set(
            # Body
            body_background_fill="linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)",
            body_text_color="#1e293b",

            # Blocks
            block_background_fill="white",
            block_border_width="1px",
            block_border_color="#e2e8f0",
            block_shadow="0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05)",
            block_title_text_weight="600",
            block_title_text_color="#334155",
            block_label_text_color="#64748b",
            block_label_text_weight="500",
            block_label_background_fill="transparent",

            # Inputs
            input_background_fill="#f8fafc",
            input_border_color="#e2e8f0",
            input_border_width="1px",
            input_shadow="inset 0 1px 2px rgba(0, 0, 0, 0.05)",
            input_placeholder_color="#94a3b8",

            # Buttons
            button_primary_background_fill="linear-gradient(135deg, *primary_500, *secondary_500)",
            button_primary_background_fill_hover="linear-gradient(135deg, *primary_600, *secondary_600)",
            button_primary_text_color="white",
            button_primary_shadow="0 4px 14px -3px rgba(99, 102, 241, 0.4)",
            button_primary_shadow_hover="0 6px 20px -3px rgba(99, 102, 241, 0.5)",
            button_primary_border_color="transparent",

            button_secondary_background_fill="white",
            button_secondary_background_fill_hover="#f8fafc",
            button_secondary_text_color="*primary_600",
            button_secondary_border_color="*primary_200",

            button_cancel_background_fill="#fef2f2",
            button_cancel_background_fill_hover="#fee2e2",
            button_cancel_text_color="#dc2626",
            button_cancel_border_color="#fecaca",

            button_large_radius="*radius_lg",
            button_large_padding="*spacing_lg",
            button_small_radius="*radius_md",
            button_small_padding="*spacing_sm",

            # Slider
            slider_color="*primary_500",

            # Checkbox/Radio
            checkbox_background_color="white",
            checkbox_background_color_selected="*primary_500",
            checkbox_border_color="*neutral_300",

            # Table
            table_border_color="#e2e8f0",
            table_even_background_fill="#f8fafc",
            table_odd_background_fill="white",

            # Shadow
            shadow_drop="0 4px 6px -1px rgba(0, 0, 0, 0.07)",
            shadow_drop_lg="0 10px 15px -3px rgba(0, 0, 0, 0.08)",
            shadow_inset="inset 0 2px 4px rgba(0, 0, 0, 0.05)",
        )


# Custom CSS for additional polish
CUSTOM_CSS = """
/* Global styles */
.gradio-container {
    max-width: 1400px !important;
    margin: 0 auto !important;
}

/* Header styling */
.app-header {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
    padding: 2rem 2.5rem;
    border-radius: 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 10px 40px -10px rgba(99, 102, 241, 0.4);
}

.app-header h1 {
    color: white !important;
    font-size: 2rem !important;
    font-weight: 700 !important;
    margin: 0 !important;
    letter-spacing: -0.025em;
}

.app-header p {
    color: rgba(255, 255, 255, 0.9) !important;
    font-size: 1rem !important;
    margin: 0.5rem 0 0 0 !important;
}

.app-header .api-badge {
    display: inline-block;
    background: rgba(255, 255, 255, 0.2);
    backdrop-filter: blur(10px);
    padding: 0.5rem 1rem;
    border-radius: 0.75rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.875rem;
    color: white;
    margin-top: 1rem;
    border: 1px solid rgba(255, 255, 255, 0.2);
}

/* Tab styling */
.tabs {
    margin-top: 0 !important;
}

.tab-nav {
    background: white !important;
    border-radius: 1rem !important;
    padding: 0.5rem !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
    margin-bottom: 1.5rem !important;
    gap: 0.25rem !important;
}

.tab-nav button {
    border-radius: 0.75rem !important;
    padding: 0.75rem 1.5rem !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}

.tab-nav button.selected {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
    color: white !important;
    box-shadow: 0 4px 14px -3px rgba(99, 102, 241, 0.4) !important;
}

.tab-nav button:not(.selected):hover {
    background: #f1f5f9 !important;
}

/* Chatbot styling */
.chatbot-container {
    border-radius: 1rem !important;
    border: 1px solid #e2e8f0 !important;
}

.message {
    padding: 1rem 1.25rem !important;
    border-radius: 1rem !important;
    margin: 0.5rem 0 !important;
}

.user-message {
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
    color: white !important;
    margin-left: 2rem !important;
}

.bot-message {
    background: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    margin-right: 2rem !important;
}

/* Input styling */
.input-container textarea,
.input-container input {
    border-radius: 0.75rem !important;
    border: 2px solid #e2e8f0 !important;
    transition: all 0.2s ease !important;
}

.input-container textarea:focus,
.input-container input:focus {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1) !important;
}

/* Button animations */
button {
    transition: all 0.2s ease !important;
}

button:active {
    transform: scale(0.98) !important;
}

/* Card styling */
.card {
    background: white;
    border-radius: 1rem;
    padding: 1.5rem;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

/* Status indicators */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    border-radius: 9999px;
    font-size: 0.875rem;
    font-weight: 500;
}

.status-loaded {
    background: #dcfce7;
    color: #166534;
}

.status-loading {
    background: #fef3c7;
    color: #92400e;
}

.status-unloaded {
    background: #f1f5f9;
    color: #64748b;
}

/* Image upload area */
.image-upload {
    border: 2px dashed #e2e8f0 !important;
    border-radius: 1rem !important;
    background: #f8fafc !important;
    transition: all 0.2s ease !important;
}

.image-upload:hover {
    border-color: #6366f1 !important;
    background: #f1f5f9 !important;
}

/* Audio player */
audio {
    border-radius: 0.75rem !important;
    width: 100% !important;
}

/* Accordion styling */
.accordion {
    border-radius: 1rem !important;
    border: 1px solid #e2e8f0 !important;
    overflow: hidden !important;
}

.accordion > .label-wrap {
    padding: 1rem 1.25rem !important;
    background: #f8fafc !important;
}

/* Slider styling */
input[type="range"] {
    height: 6px !important;
    border-radius: 9999px !important;
}

/* Dropdown styling */
.dropdown {
    border-radius: 0.75rem !important;
}

/* Section headers */
.section-header {
    font-size: 1.125rem;
    font-weight: 600;
    color: #334155;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.section-header::before {
    content: '';
    display: inline-block;
    width: 4px;
    height: 1.25rem;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    border-radius: 2px;
}

/* Pipeline step indicators */
.pipeline-step {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    background: #f8fafc;
    border-radius: 0.75rem;
    margin: 0.5rem 0;
}

.step-number {
    width: 2rem;
    height: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    color: white;
    border-radius: 9999px;
    font-weight: 600;
    font-size: 0.875rem;
}

/* Model cards */
.model-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 1rem;
    padding: 1.25rem;
    transition: all 0.2s ease;
}

.model-card:hover {
    border-color: #6366f1;
    box-shadow: 0 4px 14px -3px rgba(99, 102, 241, 0.15);
}

.model-name {
    font-weight: 600;
    color: #1e293b;
    font-size: 1rem;
}

.model-status {
    font-size: 0.875rem;
    color: #64748b;
}

/* Responsive adjustments */
@media (max-width: 768px) {
    .app-header {
        padding: 1.5rem;
    }

    .app-header h1 {
        font-size: 1.5rem !important;
    }

    .tab-nav button {
        padding: 0.5rem 1rem !important;
    }
}

/* Dark mode overrides */
@media (prefers-color-scheme: dark) {
    .app-header {
        box-shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.5);
    }

    .tab-nav {
        background: #1e293b !important;
    }

    .card, .model-card {
        background: #1e293b;
        border-color: #334155;
    }
}

/* Loading animation */
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.loading {
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

/* Smooth scrollbar */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: #f1f5f9;
    border-radius: 4px;
}

::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: #94a3b8;
}
"""


# Create theme instance
theme = UnifiedMLXTheme()
