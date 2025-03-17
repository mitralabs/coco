from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import json

from .async_utils import batched_parallel
from .db_api import DbApiClient
from .lm import LanguageModelClient


logger = logging.getLogger(__name__)

PROMPT = """
Du bist mein zweites Gehirn und ein Erinnerungsexperte. Deine Aufgabe ist es, die folgende Frage ausschließlich auf Basis des gegebenen Kontextes zu beantworten. Ignoriere jegliches externes Wissen.  

### Kontext  
<Kontext>  
{context}  
</Kontext>  

### Antwortformat  
- Maximal 50 Tokens.
- Klar und präzise.  
- Direkt auf den Kontext gestützt.  
- Keine XML-Tags oder zusätzliche Informationen.  
- Antwort ausschließlich auf Deutsch. 

### Frage  
<Frage>  
{query}  
</Frage>  

Gib nun deine Antwort gemäß den oben definierten Regeln aus.  
"""


class RagClient:
    """Client for retrieval-augmented generation (RAG)."""

    def __init__(self, lm: LanguageModelClient, db_api: DbApiClient):
        """Initialize the RAG client.

        Args:
            lm (LanguageModelClient): The language model client.
            db_api (DbApiClient): The database API client.
        """
        self.lm = lm
        self.db_api = db_api

    async def _retrieve_multiple(
        self,
        query_texts: List[str],
        n_results: int = 5,
        model: str = "nomic-embed-text",
        start_date_time: Optional[datetime] = None,
        end_date_time: Optional[datetime] = None,
    ):
        """Internal async method to retrieve documents for multiple queries.

        Args:
            query_texts: List of query texts
            n_results: Number of results to return per query
            model: Model to use for embeddings
            start_date_time: Start date for filtering documents
            end_date_time: End date for filtering documents

        Returns:
            List of tuples (ids, documents, metadatas, distances) for each query
        """
        embeddings = await self.lm._embed_multiple(query_texts, model)
        return await self.db_api._get_closest_multiple(
            embeddings, n_results, start_date_time, end_date_time
        )

    def retrieve_multiple(
        self,
        query_texts: List[str],
        n_results: int = 5,
        model: str = "nomic-embed-text",
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = True,
        start_date_time: Optional[datetime] = None,
        end_date_time: Optional[datetime] = None,
    ):
        """Retrieve documents for multiple queries.

        Args:
            query_texts (List[str]): The query texts.
            n_results (int, optional): The number of results to return per query. Defaults to 5.
            model (str, optional): The model to use for embeddings. Defaults to "nomic-embed-text".
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to True.
            start_date_time (datetime, optional): Start date for filtering documents. Defaults to None.
            end_date_time (datetime, optional): End date for filtering documents. Defaults to None.

        Returns:
            List[Tuple[List[str], List[str], List[Dict], List[float]]]: The retrieved documents for each query.
        """
        batched_retrieve_multiple = batched_parallel(
            function=self._retrieve_multiple,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Retrieving documents",
        )
        return batched_retrieve_multiple(
            query_texts, n_results, model, start_date_time, end_date_time
        )

    async def async_retrieve_multiple(
        self,
        query_texts: List[str],
        n_results: int = 5,
        model: str = "nomic-embed-text",
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = True,
        start_date_time: Optional[datetime] = None,
        end_date_time: Optional[datetime] = None,
    ):
        """Async version of retrieve_multiple.

        Args:
            query_texts (List[str]): The query texts.
            n_results (int, optional): The number of results to return per query. Defaults to 5.
            model (str, optional): The model to use for embeddings. Defaults to "nomic-embed-text".
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to True.
            start_date_time (datetime, optional): Start date for filtering documents. Defaults to None.
            end_date_time (datetime, optional): End date for filtering documents. Defaults to None.

        Returns:
            Coroutine: A coroutine that returns the retrieved documents for each query.
        """
        async_batched_retrieve_multiple = batched_parallel(
            function=self._retrieve_multiple,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Retrieving documents",
            return_async_wrapper=True,
        )
        return await async_batched_retrieve_multiple(
            query_texts, n_results, model, start_date_time, end_date_time
        )

    def format_prompt(
        self,
        query: str,
        context_chunks: List[str],
        context_metadata: List[Dict[str, Any]] = None,
        prompt_template: str | None = None,
    ) -> str:
        """Format a prompt from context and query.

        Args:
            query (str): The question.
            context_chunks (List[str]): The context chunks.
            context_metadata (List[Dict[str, Any]]): The context metadata.
            prompt_template (str): The prompt template.

        Returns:
            str: _description_
        """
        if prompt_template is None:
            prompt_template = PROMPT

        if context_metadata is None:
            context_metadata = [None] * len(context_chunks)

        context_str = ""
        for i, (chunk, metadata) in enumerate(zip(context_chunks, context_metadata)):
            context_str += f"#### Text:\n{chunk}\n\n"
            if metadata is not None:
                context_str += f"#### Metadata:\n{json.dumps(metadata, indent=2)}\n\n"
            if i < len(context_chunks) - 1:
                context_str += "-----\n\n"

        return prompt_template.format(context=context_str, query=query)

    async def _answer_multiple(
        self,
        queries: List[str],
        context_chunks: List[List[str]],
        context_metadata: List[List[Dict[str, Any]]] = None,
        prompt_template: str | None = None,
        model: str | None = "llama3.2:1b",
        temperature: float = 0.0,
    ) -> Dict[str, Dict[str, Any]]:
        if not context_metadata:
            context_metadata = [None] * len(context_chunks)
        prompts = [
            self.format_prompt(q, c, m, prompt_template)
            for q, c, m in zip(queries, context_chunks, context_metadata)
        ]
        return await self.lm._generate_multiple(
            prompts, model=model, temperature=temperature
        )

    def answer_multiple(
        self,
        queries: List[str],
        context_chunks: List[List[str]],
        context_metadata: List[List[Dict[str, Any]]] = None,
        prompt_template: str | None = None,
        model: str = "llama3.2:1b",
        temperature: float = 0.0,
        pull_model: bool = False,
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = True,
    ) -> Dict[str, Dict[str, Any]]:
        """Generate answers for a list of queries.

        Args:
            queries (List[str]): The queries to generate answers for.
            context_chunks (List[List[str]]): The context chunks to use for the generation.
            context_metadata (List[List[Dict[str, Any]]], optional): The context metadata to use for the generation. Defaults to None.
            prompt_template (str | None, optional): The prompt template to use for the generation. Defaults to None.
            model (str, optional): The model to use for the generation. Defaults to "llama3.2:1b".
            pull_model (bool, optional): Whether to pull the ollama model. Defaults to False.
            batch_size (int, optional): The batch size to use for the generation. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to True.

        Returns:
            Tuple[List[str], List[float]]: The generated answers and the token speeds.
        """
        if pull_model:
            models = self.lm.list_ollama_models()
            if model not in models:
                logger.info(f"Pulling model {model} because it is not available")
                self.lm.pull_ollama_model(model)
                logger.info(f"Pulled model {model}")

        batched_generate_answers = batched_parallel(
            function=self._answer_multiple,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Generating answers",
        )
        return batched_generate_answers(
            queries=queries,
            context_chunks=context_chunks,
            context_metadata=context_metadata,
            prompt_template=prompt_template,
            model=model,
            temperature=temperature,
        )
