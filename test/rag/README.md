# RAG Test Pipeline

This application provides a testing framework the Coco RAG system.

## Setup and Configuration

### Weights & Biases Integration

The application uses [Weights & Biases (wandb)](https://wandb.ai) for experiment tracking. To initialize wandb:

1. Install wandb: `pip install wandb`
2. Login to wandb: `wandb login`
3. Configuration is handled in `conf/config.yaml`:
   ```yaml
   wandb:
     entity: your-entity
     project: your-project
     name: ${now:%Y-%m-%d_%H-%M-%S} # Automatic timestamp naming
   ```

### Hydra Configuration System

The application uses [Hydra](https://hydra.cc/) for configuration management. The configuration is split into multiple files under the `conf/` directory:

- `config.yaml`: Main configuration file
- `data/*.yaml`: Dataset configurations
- `retrieval/*.yaml`: Retrieval configurations
- `generation/*.yaml`: Generation configurations

To override any config parameter when running:

```bash
python main.py data=your_data retrieval=your_retrieval generation=your_generation
```

### Data Configuration

The data configuration (`conf/data/*.yaml`) specifies dataset parameters and database operations. Example configuration from `germandpr.yaml`:

```yaml
name: germandpr # Dataset name
hf_name: deepset/germandpr # HuggingFace dataset name
language: de # Dataset language
use_train: true # Use training split
use_test: false # Use test split
backup_db: false # Backup database before operations
clear_db: false # Clear database before filling
fill_db:
  skip: true # Skip database filling
  embed_and_store_batch_size: 25 # Batch size for embedding
  embed_and_store_limit_parallel: 10 # Parallel processing limit
```

## Components

### 1. Data

The data component handles dataset loading, preprocessing, and database operations. Configuration in `conf/data/*.yaml`:

Parameters:

- `name`: Dataset identifier used throughout the pipeline
- `hf_name`: HuggingFace dataset source (if applicable)
- `language`: Dataset language code
- `use_train/use_test`: Control which dataset splits to use
- Database operations:
  - `backup_db`: Create database backup before operations
  - `clear_db`: Clear existing database entries
  - `fill_db`: Database population settings
    - `skip`: Skip database filling step
    - `embed_and_store_batch_size`: Number of items to process in each batch
    - `embed_and_store_limit_parallel`: Maximum parallel processing tasks

### 2. Retrieval

The retrieval component evaluates the system's ability to fetch relevant chunks of information. Configuration in `conf/retrieval/primitive.yaml`:

Parameters:

- `get_top_chunks.top_k`: Number of top chunks to retrieve (default: 100)
- `metric_ks`: List of k values for evaluation metrics [1, 5, 10, 20, 50, 100]
- `rank_first_relevant_punishment`: Penalty score when ground truth chunk isn't retrieved (default: 101)

Output files are stored in:

```
${general.data_dir}/retrieval/${data.name}/${retrieval.get_top_chunks.top_k}.json
```

### 3. Generation

The generation component evaluates the quality of generated responses based on retrieved context. Configuration in `conf/generation/primitive.yaml`.

## General Configuration

The application requires several service endpoints configured in `conf/config.yaml`:

```yaml
coco:
  chunking_base: http://127.0.0.1:8001
  embedding_base: http://127.0.0.1:8002
  db_api_base: http://127.0.0.1:8003
  transcription_base: http://127.0.0.1:8000
  ollama_base: http://127.0.0.1:11434
  openai_base: https://openai.example.com
  embedding_api: ollama # Embedding provider
  llm_api: ollama # Generation provider
  api_key: test
```

Data directories:

- Services data: `services_data_dir: ../../services/_data`
- Application data: `data_dir: ./data`

## Configuration Changes

Update your `conf/config.yaml` with LM API selection:

```yaml
coco:
  ollama_base: http://127.0.0.1:11434
  openai_base: https://openai.example.com
  embedding_api: ollama # Embedding provider
  llm_api: ollama # Generation provider
  api_key: test
```

## Key Pipeline Updates

1. **Embedding Integration**

   - Embeddings now generated through LM module
   - Removed separate embedding service dependency

2. **Dual-Model Support**

   ```python
   # Example using different providers for embedding/generation
   client = CocoClient(
       embedding_api="openai",
       llm_api="ollama",
       # ... other params
   )
   ```

3. **Batch Processing**

   - All RAG operations use batched_parallel
   - Improved memory management for large datasets

4. **Model Management**
   ```python
   # Auto-download missing Ollama models
   answers = generation_stage(
       cc, cfg, top_chunks, ds,
       pull_model=True
   )
   ```
