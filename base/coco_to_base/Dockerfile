FROM python:3.9-slim

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY .env .

WORKDIR /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]