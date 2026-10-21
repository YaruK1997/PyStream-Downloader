# Stage 1: Base image with FFmpeg and Python
FROM python:3.15-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies: FFmpeg, curl, ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create application working directory
WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY src/ ./src/
COPY main.py .

# Create downloads volume directory and set up non-root user
RUN mkdir -p /app/downloads && \
    useradd -u 1000 -m appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Healthcheck to verify Python runtime, dependencies (including curl_cffi for impersonation), and FFmpeg binary
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import yt_dlp, psutil, curl_cffi, shutil; assert shutil.which('ffmpeg')" || exit 1

# Default volume mount point
VOLUME ["/app/downloads"]

# Default command
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
