FROM python:3.10-slim

# Install curl for health checks
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . /app

WORKDIR /app

# Mache das Skript ausführbar
RUN chmod +x ./start.sh

# Definiere das Startskript als ENTRYPOINT
ENTRYPOINT ["./start.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]