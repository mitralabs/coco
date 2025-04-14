import gradio as gr
import os
import datetime
from datetime import date
from coco import CocoClient

# Can be removed, only until functions are in SDK
from ollama import AsyncClient
from openai import AsyncOpenAI

# Environment variables configuration
CHUNKING_BASE = os.getenv("COCO_CHUNK_URL_BASE")
DB_API_BASE = os.getenv("COCO_DB_API_URL_BASE")
TRANSCRIPTION_BASE = os.getenv("COCO_TRANSCRIPTION_URL_BASE")
OLLAMA_BASE = os.getenv("COCO_OLLAMA_URL_BASE")
OPENAI_BASE = os.getenv("COCO_OPENAI_URL_BASE")
EMBEDDING_API = os.getenv("COCO_EMBEDDING_API")
LLM_API = os.getenv("COCO_LLM_API")
API_KEY = os.getenv("COCO_API_KEY")
# Default models
EMBEDDING_MODEL = os.getenv("COCO_EMBEDDING_MODEL", "nomic-embed-text")
DEFAULT_LLM_MODEL = os.getenv(
    "COCO_DEFAULT_LLM_MODEL", "meta-llama/Llama-3.3-70B-Instruct"
)

# Initialize clients
openai = AsyncOpenAI(base_url="https://openai.inference.de-txl.ionos.com/v1")
ollama = AsyncClient(host="http://host.docker.internal:11434")

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
        available_models = [DEFAULT_LLM_MODEL]

    if cc.lm.llm_api == "openai":
        try:
            available_models = [
                (model.split("/")[-1], model) for model in available_models
            ]
        except:
            pass

    return available_models


def update_available_models(llmapi):
    cc.lm.llm_api = llmapi
    available_models = get_available_models()
    return gr.Dropdown(choices=available_models, interactive=True)


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
