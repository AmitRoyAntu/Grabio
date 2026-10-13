FROM python:3.11-slim

# Install system dependencies including ffmpeg and nodejs (for yt-dlp JS challenges)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set default environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=5000
ENV HOST=0.0.0.0

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-5000}/health || exit 1

CMD ["python", "app.py"]
