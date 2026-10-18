FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LLM_PROVIDER=mock

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 orvilo \
    && mkdir -p agent/data reasoning/data user/data \
    && chown -R orvilo:orvilo /app
USER orvilo

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:5000/api/market/live || exit 1

CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "5000"]
