# Base Services
This directory contains all services running on the base station.

## Usage
From **this directory**:
```sh
docker compose up -d --wait
```
This will:
- build the docker images if not present
- spin up all containers
- wait until container health checks pass
(meaning the `/test` endpoints actually return status 200)

(You can omit the `--wait` flag to not wait for the health check, but then containers might return no reply yet.)

If Dockerfiles were changed, force an image rebuild:
```sh
docker compose up -d --wait --build
```