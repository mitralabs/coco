FROM python:3.9-slim

RUN apt-get update && apt-get install -y curl

COPY db_api/requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]