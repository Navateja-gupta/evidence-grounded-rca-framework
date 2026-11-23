FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY rca ./rca
COPY config ./config

RUN useradd --create-home --uid 1000 rca
USER rca

EXPOSE 8000

CMD ["uvicorn", "rca.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
