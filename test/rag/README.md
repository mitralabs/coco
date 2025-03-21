# RAG Test Pipeline

This application provides a testing framework the Coco RAG system.

## Setup and Configuration

### Transformers and Sentence-Transformers

Some metrics use HF transformers and sentence-transformers. When installing
dependencies, make sure to install a version with gpu support if possible.

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

### Running individual tests

Setup the all hydra config values as you want and start the script. Make sure to set a wandb run name:

```bash
python main.py wandb.name=<my name>
```

(You can overwrite arbitrary config values similarly to wandb.name from the commandline!)

## Sweeps (Parameter Searches)

This pipeline supports hyperparameter sweeps via Weights & Biases to automatically find pipeline settings that optimize some metric.
To run a sweep:

1. **Configure the Sweep:**  
   Edit a sweep configuration file or create a new one. For instance `./sweeps/primitive_embedding_lm.yaml` includes a config that runs a grid search (just trying all combinations of parameters) with two different embedding models and two different LLMs. Just **make sure the sweep paramter names match the hydra names**. Also make sure the wandb entity and project match the one set in the hydra config.

2. **Start the Sweep:**  
   Run the following command from the terminal (replace config name):

   ```
   wandb sweep sweeps/primitive_embedding_lm.yaml
   ```

   This command will output a sweep ID.

3. **Launch Sweep Agents:**  
   With the obtained sweep ID, run one or more agents to start the experiments:

   ```
   wandb agent <sweep-id>
   ```

   Multiple agents can be launched in parallel to expedite the sweep.

### Common Pitfalls

1. Make sure the db-api service runs with an embedding dimensionality >= the highest required by all embedding models.

2. Make sure ollama has all used models pulled.

3. You very likely want the data stage to clear and refill the database when experimenting with different embedding models.

4. Make sure you only load cached retrieval results or generation results if you are sure they are valid for all runs of the sweep.

## Viewer

The RAG test pipeline includes a viewer to inspect and analyze your experiment results.

### Running the Viewer

To launch the viewer, run:

```bash
python viewer.py
```

### Viewing Modes

The viewer supports two modes:

1. **Single Run Mode**: View results from a single experiment run. This allows you to see:

   - The model's retrieved chunks
   - Generated answers based on retrieved contexts
   - Ground truth answers
   - Retrieved vs. ground truth chunks comparison

2. **Compare Runs Mode**: Compare results between two different experiment runs. This allows you to:
   - See answers from both runs side-by-side
   - Compare retrieved chunks between runs
   - Analyze differences in retrieval and generation quality
   - Identify which run performed better for specific queries

To use the comparison mode, select "Compare Runs" in the view mode selector, then enter the names of two runs to compare.

### Tips for Effective Comparison

- Use runs with different retrieval methods to compare their effectiveness
- Compare different LLM models with the same retrieval approach
- Compare different parameter settings for the same model setup
- Look for patterns in which types of queries each approach handles better
