FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Disable tokenizers parallelism to avoid warnings
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

# Install system dependencies
# libpq-dev is needed for psycopg2 (PostgreSQL)
# git is often needed for installing dependencies
# ffmpeg is needed for Discord voice/audio streaming
# libsodium-dev is needed for PyNaCl (voice encryption)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    git \
    curl \
    tzdata \
    ffmpeg \
    libsodium-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project definition files
COPY pyproject.toml requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Set FastEmbed cache path to a persistent location in the image
ENV FASTEMBED_CACHE_PATH=/cache/fastembed
RUN mkdir -p $FASTEMBED_CACHE_PATH

# Copy download script and pre-download models
COPY scripts/download_models.py /app/scripts/
RUN python /app/scripts/download_models.py

# Copy the rest of the application
COPY . .

# Entrypoint
# We use CMD instead of ENTRYPOINT to allow easier overriding, 
# and we don't pass a default argument so it uses the DISCORD_BOT_NAME env var.
CMD ["python", "run_v2.py"]
