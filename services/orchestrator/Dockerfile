FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg

COPY orchestrator/requirements.txt .
RUN pip install -r requirements.txt

COPY python_sdk_entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /app

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]