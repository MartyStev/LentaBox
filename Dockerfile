FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.lock .
RUN pip install --require-hashes -r requirements.lock

COPY bot.py config.py ./
COPY core core
COPY db db
COPY handlers handlers

# The Telethon session is the only thing the bot writes; it lives in a volume, never in the image.
RUN useradd --system --uid 10001 --home-dir /data stenabot \
    && mkdir -p /data && chown stenabot /data
USER stenabot
ENV SESSION_NAME=/data/stenabot
VOLUME ["/data"]

CMD ["python", "bot.py"]
