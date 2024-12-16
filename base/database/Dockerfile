FROM python:3.9-slim

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY .env .
COPY ./app /app

WORKDIR /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]