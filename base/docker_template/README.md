# Docker Template Container

This is a FastAPI-based boilerplate container for creating new services. The service is containerized with Docker for easy deployment and serves as a starting point for building other containers.

1. **Build the Docker image:**
   ```bash
   docker build -t docker-template .
   ```

2. **Run the Docker container:**
   ```bash
   docker run -d -p 8000:8000 -v $(pwd)/app:/app -v $(pwd)/../_data:/data docker-template
   ```

## Usage

Once the service is running, you can test the API by sending a GET request to the `/test` endpoint.

### Example using `curl`:

```bash
curl -X GET -H "X-API-Key: your_api_key_here" http://localhost:8000/test
```

Replace `X-API-Key: your_api_key_here` with your API key.

## Endpoints

- **GET /test**: A basic test endpoint to verify that the service is running and the API key authentication is working.

## Notes

- This template is designed to be a starting point for new FastAPI services. You can extend it by adding more endpoints and functionality as needed.

- Ensure that the `API_KEY` environment variable is set before running the container to enable API key authentication.
