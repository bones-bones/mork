# Minimal image for running the Mork Discord bot (e.g. Cloud Run, GKE, Compute Engine).
# Mount or inject secrets at runtime — do not bake discord_token or client_secrets into the image.

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "Mork.py"]
