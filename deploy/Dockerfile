FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY packages/ packages/
COPY services/ services/

ENV PYTHONPATH="/app/packages/validator/src:/app/packages/engine/src:/app/packages/adapters/bhashini/src:/app"

EXPOSE 8000

CMD ["uvicorn", "services.api.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
