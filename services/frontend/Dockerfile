FROM python:3.10-slim

# Install curl for health checks
RUN apt-get update && apt-get install -y curl

# Install dependencies
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY start.sh .

# Make the script runnable
RUN chmod +x ./start.sh

ENTRYPOINT ["./start.sh"]
CMD ["gradio", "main.py"]