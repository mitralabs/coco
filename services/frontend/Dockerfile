FROM python:3.10-slim

# Install curl for health checks
RUN apt-get update && apt-get install -y curl

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . /app

WORKDIR /app

RUN chmod +x ./start.sh

ENTRYPOINT ["./start.sh"]
CMD ["python", "main.py"]