# Use lightweight Python 3.11
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU PyTorch first
RUN pip install --no-cache-dir torch==2.0.1+cpu torchvision==0.15.2+cpu --extra-index-url https://download.pytorch.org/whl/cpu

# Install requirements from wardrobe
COPY wardrobe/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Copy the wardrobe backend code to /app
COPY wardrobe/ .

# Hugging Face Spaces standard port is 7860
EXPOSE 7860

# Launch Uvicorn on 0.0.0.0:7860
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
