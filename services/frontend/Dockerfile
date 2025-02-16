FROM python:3.10-slim

RUN apt-get update
RUN apt-get install -y curl

# Install dependencies
RUN pip install --upgrade pip
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY python_sdk_entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Make the script runnable
RUN chmod +x ./start.sh

ENTRYPOINT ["./start.sh"]
CMD ["gradio", "main.py"]