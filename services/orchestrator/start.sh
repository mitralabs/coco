#!/bin/sh

# upgrade pip
pip install --upgrade pip

# Installiere benötigte Pakete
cd ./python_sdk && pip install -e . 

cd ../app

# Start the uvicorn server
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level debug