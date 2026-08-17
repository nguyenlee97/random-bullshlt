FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
RUN python -m playwright install --with-deps chromium

COPY . .

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s \
  CMD python -c "import httpx; httpx.get('http://localhost:8080/ready').raise_for_status()"

# GreenNode AgentBase Runtime Contract: must listen on 0.0.0.0:8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
