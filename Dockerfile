FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
 libatspi2.0-0 libwayland-client0 libxshmfence1 libglib2.0-0 \
 wget gnupg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium
RUN playwright install-deps chromium || true

COPY . .

RUN mkdir -p /data

ENV GRADIO_SERVER_NAME="0.0.0.0"
ENV GRADIO_SERVER_PORT="7860"
ENV PYTHONUNBUFFERED="1"

EXPOSE 7860

CMD ["python", "app.py"]
