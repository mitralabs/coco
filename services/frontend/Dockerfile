FROM python:3.10-slim

RUN apt-get update
RUN apt-get install -y curl

# Install dependencies
RUN pip install --upgrade pip
COPY frontend/requirements.txt .
RUN pip install -r requirements.txt


COPY python_sdk_entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /app

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["gradio", "main.py"]