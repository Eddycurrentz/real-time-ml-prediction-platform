FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
COPY README.md ./

RUN python -m pip install --upgrade pip && python -m pip install -e .

RUN useradd --create-home --uid 10001 app
USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "rtml.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
