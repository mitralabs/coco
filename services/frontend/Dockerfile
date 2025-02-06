FROM python:3.10-slim

# Install curl for health checks
RUN apt-get update && apt-get install -y curl

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /app

RUN chmod +x /app/start.sh

ENTRYPOINT ["/app/start.sh"]
CMD ["python", "main.py"]