# Universal Context Engine Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy source code
COPY src/ src/
COPY migrations/ migrations/
COPY config/ config/
COPY scripts/ scripts/

# Create non-root user
RUN useradd -m -u 1000 uce && chown -R uce:uce /app
USER uce

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UCE_API_HOST=0.0.0.0
ENV UCE_API_PORT=8100

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8100/health || exit 1

# Expose port
EXPOSE 8100

# Run the application
CMD ["python", "-m", "uvicorn", "uce.main:app", "--host", "0.0.0.0", "--port", "8100"]
