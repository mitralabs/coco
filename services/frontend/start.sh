#!/bin/sh

# upgrade pip
pip install --upgrade pip

# Installiere benötigte Pakete
cd ./python_sdk && pip install -e . 

cd ../app

# Start the uvicorn server
exec "$@"