import gradio as gr
import os
import datetime
from datetime import date
from coco import CocoClient

# Environment variables configuration
API_KEY = os.getenv("API_KEY", "")
CHUNKING_BASE = os.getenv("COCO_CHUNK_URL_BASE")
DB_API_BASE = os.getenv("COCO_DB_API_URL_BASE")
TRANSCRIPTION_BASE = os.getenv("COCO_TRANSCRIPTION_URL_BASE")
EMBEDDING_MODEL = os.getenv("COCO_EMBEDDING_MODEL")

if not all([API_KEY, CHUNKING_BASE, DB_API_BASE, TRANSCRIPTION_BASE, EMBEDDING_MODEL]):
    raise ValueError(
        "API_KEY, CHUNKING_BASE, DB_API_BASE, TRANSCRIPTION_BASE, and EMBEDDING_MODEL must all be set"
    )

# With Defaults
OPENAI_BASE = os.getenv("COCO_OPENAI_URL_BASE", "")
OLLAMA_BASE = os.getenv("COCO_OLLAMA_URL_BASE", "http://host.docker.internal:11434")
EMBEDDING_API = os.getenv("COCO_EMBEDDING_API", "ollama")
LLM_API = os.getenv("COCO_LLM_API", "ollama")


# Shared theme
theme = gr.themes.Ocean(
    primary_hue="sky",
    neutral_hue="neutral",
    spacing_size="sm",
)

# Initialize CocoClient
cc = CocoClient(
    chunking_base=CHUNKING_BASE,
    db_api_base=DB_API_BASE,
    transcription_base=TRANSCRIPTION_BASE,
    ollama_base=OLLAMA_BASE,
    openai_base=OPENAI_BASE,
    embedding_api=EMBEDDING_API,
    llm_api=LLM_API,
    api_key=API_KEY,
)

# Default system message
system_message_default = "Du bist coco.\n\nDu hilfst dem User bestmöglich.\n\nDu antwortest präzise und kommunizierst auf Deutsch."

# Context formatting
CONTEXT_FORMAT = """
    Der nachfolgende Inhalt könnte hilfreich sein, um die Frage zu beantworten:
    
    -----
    {context}
    -----
"""


# Utility functions
def get_available_models():
    try:
        available_models = cc.lm.list_llm_models()
        embedding_models_ollama = [
            "nomic-embed-text:latest",
            "mxbai-embed-large:latest",
            "snowflake-arctic-embed:latest",
            "bge-m3:latest",
            "all-minilm:latest",
            "bge-large:latest",
            "snowflake-arctic-embed2:latest",
            "paraphrase-multilingual:latest",
            "granite-embedding:latest",
        ]
        non_llms_ionos = [
            "meta-llama/CodeLlama-13b-Instruct-hf",
            "black-forest-labs/FLUX.1-schnell",
            "BAAI/bge-large-en-v1.5",
            "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            "BAAI/bge-m3",
            "stabilityai/stable-diffusion-xl-base-1.0",
        ]

        blacklisted_models = embedding_models_ollama + non_llms_ionos
        available_models = [
            model for model in available_models if model not in blacklisted_models
        ]

        if not available_models:
            return [], "No compatible LLM models found. Using default model."

        if cc.lm.llm_api == "openai":
            try:
                available_models = [
                    (model.split("/")[-1], model) for model in available_models
                ]
            except:
                pass

        return available_models, None
    except Exception as e:
        # Return empty list and error message
        error_msg = (
            f"Failed to load models: {str(e)}. Check your connection and API key."
        )
        return [], error_msg


# Remove the update_available_models function as it's no longer needed
def update_available_models(llmapi):
    cc.lm.llm_api = llmapi
    models, error_msg = get_available_models()
    return gr.Dropdown(choices=models, interactive=True), error_msg


def parse_datetime(date_value):
    """Convert various date formats to datetime objects"""
    if date_value is None:
        return None

    if isinstance(date_value, datetime.datetime):
        return date_value
    elif isinstance(date_value, date):
        return datetime.datetime.combine(date_value, datetime.time.min)
    elif isinstance(date_value, str) and date_value.strip():
        try:
            return datetime.datetime.fromisoformat(date_value)
        except ValueError:
            print(f"Invalid date format: {date_value}")
            return None
    return None
