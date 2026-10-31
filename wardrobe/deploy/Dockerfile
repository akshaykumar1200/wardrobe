FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/user/.cache/huggingface

# HF_HOME is the model library cache used to load the vision models on any host.

WORKDIR /app

RUN useradd --create-home --uid 1000 user \
    && mkdir -p /home/user/.cache/huggingface \
    && chown -R user:user /home/user

# deploy/requirements.txt, not the repo root one: that has selenium and no psycopg.
COPY deploy/requirements.txt /app/requirements.txt

# Use CPU-only PyTorch wheels; the free Space tier does not provide a GPU.
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
        torch==2.0.1+cpu torchvision==0.15.2+cpu \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY backend/ /app/backend/
COPY frontend/dist/ /app/frontend/dist/
COPY deploy/prefetch_models.py /app/deploy/prefetch_models.py

RUN chown -R user:user /app /home/user/.cache/huggingface

USER user

# Bake both model repositories into the image so startup does not download them.
RUN python /app/deploy/prefetch_models.py

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
