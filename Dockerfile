FROM python:3.12-slim

# Dedicated non-root user — the app never needs root at runtime.
RUN useradd --create-home --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY requirements.txt .
# --only-binary :all: forbids sdists, so no setup.py ever executes in the image.
RUN pip install --no-cache-dir --only-binary :all: -r requirements.txt

COPY src ./src

ENV PYTHONPATH=/app/src
WORKDIR /app/src
USER appuser

EXPOSE 8080
# 0.0.0.0 is deliberate here: inside the container only mapped ports are reachable.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
