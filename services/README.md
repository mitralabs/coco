## Info:

- **Transcription**: A FastAPI-based service that transcribes audio files into text using the Whisper model.
- **Chunking**: Provides text chunking functionality using LangChain.
- **Database**: Offers vector database functionality using Postgres for storing embeddings and metadata.
- **Orchestrator**: Is the bridge between the coco hardware device and the backend.
- **Frontend**: A Gradio-based web interface that provides an Interactive chat interface and a view of the database **(deprecated, currently not in use. feel free to use it as a dataviewer though.)**

#### Notes on the Database:
- The service automatically pads embeddings that are smaller than the maximum dimension
- Documents with identical text content will be skipped during insertion
- The API uses cosine similarity for finding semantically similar documents
- Please refer to the [migrations-doc](db_api/migrations.md) of the service for Database Migrations.


## Usage
1. Duplicate the `.env.template`file and rename it to `.env`
2. Choose a [whisper model](https://github.com/ggml-org/whisper.cpp/blob/master/models/README.md).
3. Choose if you want to stay local with Ollama or Fallback to OpenAI or an OpenAI like service. If the latter is the case, set your OpenAI_API_KEY. *Note: This might be confusing with regard to the mentioning of Claude Desktop before, but even if you go with Anthropic, and omit Ollama, there is a need to calculate Embeddings. And this repo currently only supports OpenAI like Endpoints as alternative.**
4. Make sure to download an embedding model (case ollama) and/or set the COCO_EMBEDDING_MODEL env.
5. Run `./backend_start.sh` in your terminal. It will do the following:
  - Download the whisper.cpp repository, and remove it's git connection.
  - Compile whisper for your machine.
  - Download the whisper model of your choice
  - Create a virtual environment for the packages needed for the transcription service.
  - Start a FastAPI App in the Background as Transcription Service.
  - Kick off the Build/Compose Process for all other services as Docker Containers.
6. Enjoy.*Note: run `./backend_stop.sh`to stop all services.*

### Setting up the Chatinterface / MCP Client
#### LibreChat:
1. Set up [LibreChat](https://www.librechat.ai/docs/quick_start/local_setup) on your hardware.
2. Set up [Ollama](https://www.librechat.ai/docs/configuration/librechat_yaml/ai_endpoints/ollama). Skip this step if you plan on using a different provider.
3. Configure the [MCP Settings](https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/mcp_servers). You need to add the latter to the `librechat.yaml``
```yaml
  coco-mcp-server:
    # type: sse # type can optionally be omitted
    url: http://host.docker.internal:8004/sse
```
4. Create an [agent](https://www.librechat.ai/docs/features/agents) and add the `pg_vector_tool`to query the database.

#### Claude Desktop:
1. [Follow this tutorial](https://modelcontextprotocol.io/quickstart/user). To add the latter to your `claude_desktop_config.json`
```json
"coco-db-mcp-server": {
    "command": "bash",
    "args": [
      "-c",
      "docker attach coco_mcp_server"
      ]
  }
```


## Spinning up individual Docker Containers:

You can start individual services as needed:

```bash
# From the services directory
docker compose up chunking
docker compose up db-api
docker compose up db
docker compose up frontend
docker compose up orchestrator

# To rebuild a specific container
docker compose up --build <service-name>
```

### Service Ports:
- Chunking: http://localhost:8001 (FastAPI)
- DB-API: http://localhost:8003 (FastAPI)
- Database: localhost:5432 (PostgreSQL)
- Frontend: http://localhost:8002 (Gradio UI) **deprecated, not in use**
- Orchestrator: http://localhost:3030 (FastAPI)

API documentation for FastAPI services is available at `http://localhost:<port>/docs` (Swagger UI).

## Additional Notes:
- It is currently not implemented, that transcription is not done locally. But it's definitely possible to change that, since our approach follows the openai transcription standard.
- If you want to see if the transcription process is running in the background use the command `ps aux | grep uvicorn`, which will show the uvicorn processes on your machine. If you further want to kill a process, use `kill <PID>` where <PID> is the Process ID.


**The compose.yaml requires the following:**

| Environment Variable | Description | Required | Example |
|---------------------|-------------|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Yes | `postgresql://user:pass@host:5432/dbname` |
| `COCO_EMBEDDING_API` | Which embedding API to use (`ollama` or `openai`) | Yes | `openai` |
| `COCO_LLM_API` | Which LLM API to use (`ollama` or `openai`) | Yes | `openai` |
| `COCO_OLLAMA_URL_BASE` | Base URL for Ollama API | Only if using Ollama | `http://host.docker.internal:11434` |
| `COCO_OPENAI_URL_BASE` | Base URL for OpenAI API | Only if using OpenAI | `https://api.openai.com/v1` |
| `OPENAI_API_KEY` | API key for OpenAI | Only if using OpenAI | `sk-...` |
| `COCO_EMBEDDING_MODEL` | Model to use for embeddings | Recommended | `BAAI/bge-m3` |
| `COCO_API_KEY` | API key for Coco services | Optional | |