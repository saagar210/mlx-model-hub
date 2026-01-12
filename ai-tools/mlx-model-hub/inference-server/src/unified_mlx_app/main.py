"""Main entry point for Unified MLX App."""

import argparse
import logging
import threading

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .api.admin_routes import admin_router
from .cache import init_prompt_cache_service
from .config import settings
from .mcp.routes import router as mcp_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create FastAPI application with CORS enabled."""
    app = FastAPI(
        title="Unified MLX AI API",
        description="OpenAI-compatible API for MLX models",
        version="0.1.0",
    )

    # Add CORS middleware for frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",  # unified-mlx-app Next.js frontend
            "http://127.0.0.1:3000",
            "http://localhost:3005",  # mlx-model-hub frontend
            "http://127.0.0.1:3005",
            "http://localhost:7860",  # Gradio (legacy)
            "http://127.0.0.1:7860",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize prompt cache service for KV caching
    if settings.prompt_cache_enabled:
        init_prompt_cache_service(
            cache_dir=settings.prompt_cache_dir,
            max_memory_entries=settings.prompt_cache_max_entries,
            persist_to_disk=settings.prompt_cache_persist,
        )
        logger.info(
            f"Prompt cache initialized: max_entries={settings.prompt_cache_max_entries}, "
            f"persist={settings.prompt_cache_persist}"
        )

    app.include_router(router)
    app.include_router(mcp_router)
    app.include_router(admin_router)
    return app


def run_api_server(app: FastAPI):
    """Run the FastAPI server."""
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.api_port,
        log_level="info",
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Unified MLX AI")
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Run API server only (for use with React frontend)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=settings.api_port,
        help=f"API server port (default: {settings.api_port})",
    )
    args = parser.parse_args()

    logger.info("Starting Unified MLX AI...")
    logger.info(f"API server will be available at http://{settings.host}:{args.port}")

    # Create FastAPI app
    api_app = create_app()

    if args.api_only:
        # Run API server only (blocking)
        logger.info("Running in API-only mode (use React frontend at http://localhost:3000)")
        uvicorn.run(
            api_app,
            host=settings.host,
            port=args.port,
            log_level="info",
        )
    else:
        # Legacy mode: Run with Gradio UI
        logger.info(f"Web UI will be available at http://{settings.host}:{settings.ui_port}")

        # Start API server in background thread
        api_thread = threading.Thread(target=run_api_server, args=(api_app,), daemon=True)
        api_thread.start()
        logger.info("API server started")

        # Create and launch Gradio UI (blocking)
        from .ui import create_ui
        from .ui.app import CUSTOM_CSS, theme

        ui = create_ui()
        logger.info("Launching Gradio UI...")

        ui.launch(
            server_name=settings.host,
            server_port=settings.ui_port,
            share=False,
            show_error=True,
            theme=theme,
            css=CUSTOM_CSS,
        )


if __name__ == "__main__":
    main()
