from typing import Tuple, List, Dict, Any
import logging

from .async_utils import batched_parallel
from .db_api import DbApiClient
from .lm import LanguageModelClient


logger = logging.getLogger(__name__)

PROMPT = """
    Du bist ein zweites Gehirn für mich, ein Erinnerungsexperte, und deine Aufgabe ist es, basierend auf dem gegebenen Kontext den du aus meinen Erinnerungen in Form von Textausschnitten innerhalb der XML tags die dann folgende Frage so akkurat wie möglich beantwortest. Achte dabei darauf das deine Knowledge Base nur auf dem gegebenen Kontext basiert und du dich streng an das gegebene Format hälst:

    <Kontext> 
    {context}
    </Kontext>

    <Format>
    Ein Satz mit maximal 50 Tokens. Deine Antwort ist klar und beantwortet die Frage indem es sich direkt auf den Kontext stützt. Gebe bei der Antwort KEINE XML tags oder sonstigen Werte an. Beantworte die Frage ausschließlich auf Deutsch.
    </Format>

    Du hast jetzt den Kontext in den <Kontext> XML Tags verstanden hast und das Format übernommen. Beantworte nun die nachfolgende Frage innerhalb der <Frage> XML Tags basierend auf dem gegebenen Kontext in den XML tags. Achte dabei darauf die streng an das Format aus den XML Tags zu halten.

    <Frage>
    {query}
    </Frage>
"""


class RagClient:
    def __init__(
        self,
        db_api: DbApiClient,
        lm: LanguageModelClient,
    ):
        self.db_api = db_api
        self.lm = lm

    async def _retrieve_chunks(self, query_texts, n_results, model="nomic-embed-text"):
        embeddings = await self.lm._embed(query_texts, model)
        return await self.db_api._get_multiple_closest(embeddings, n_results)

    def retrieve_chunks(
        self,
        query_texts: List[str],
        n_results: int = 5,
        model: str = "nomic-embed-text",
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = True,
    ) -> List[Tuple[List[str], List[str], List[Dict], List[float]]]:
        """Retrieve chunks from the database.

        Args:
            query_texts (List[str]): The query texts to retrieve chunks for.
            n_results (int, optional): The number of results to retrieve. Defaults to 5.
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to True.

        Returns:
            List[Tuple[List[str], List[str], List[Dict], List[float]]]: The retrieved chunks.
        """
        batched_retrieve_chunks = batched_parallel(
            function=self._retrieve_chunks,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Retrieving chunks",
        )
        return batched_retrieve_chunks(query_texts, n_results, model)

    async def async_retrieve_chunks(
        self,
        query_texts: List[str],
        n_results: int = 5,
        model: str = "nomic-embed-text",
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = True,
    ) -> List[Tuple[List[str], List[str], List[Dict], List[float]]]:
        """Retrieve chunks from the database.

        Args:
            query_texts (List[str]): The query texts to retrieve chunks for.
            n_results (int, optional): The number of results to retrieve. Defaults to 5.
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to True.

        Returns:
            List[Tuple[List[str], List[str], List[Dict], List[float]]]: The retrieved chunks.
        """
        batched_retrieve_chunks = batched_parallel(
            function=self._retrieve_chunks,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Retrieving chunks",
            return_async_wrapper=True,
        )
        return await batched_retrieve_chunks(query_texts, n_results, model)

    def format_prompt(
        self, query: str, context_chunks: List[str], prompt_template: str | None = None
    ) -> str:
        """Format a prompt from context and query.

        Args:
            query (str): The question.
            context_chunks (List[str]): The context chunks.
            prompt_template (str): The prompt template.

        Returns:
            str: _description_
        """
        if prompt_template is None:
            prompt_template = PROMPT
        return prompt_template.format(
            context="\n-----\n".join(context_chunks), query=query
        )

    async def _generate_answers(
        self,
        queries: List[str],
        context_chunks: List[List[str]],
        prompt_template: str | None = None,
        model: str | None = "llama3.2:1b",
    ) -> Dict[str, Dict[str, Any]]:
        prompts = [
            self.format_prompt(q, c, prompt_template)
            for q, c in zip(queries, context_chunks)
        ]
        return await self.lm._generate(prompts, model=model)

    def generate_answers(
        self,
        queries: List[str],
        context_chunks: List[List[str]],
        prompt_template: str | None = None,
        model: str = "llama3.2:1b",
        pull_model: bool = False,
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = True,
    ) -> Dict[str, Dict[str, Any]]:
        """Generate answers for a list of queries.

        Args:
            queries (List[str]): The queries to generate answers for.
            context_chunks (List[List[str]]): The context chunks to use for the generation.
            prompt_template (str | None, optional): The prompt template to use for the generation. Defaults to None.
            ollama_model (_type_, optional): The ollama model to use for the generation. Defaults to "llama3.2:1b".
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
            function=self._generate_answers,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Generating answers",
        )
        return batched_generate_answers(
            queries=queries,
            context_chunks=context_chunks,
            prompt_template=prompt_template,
            model=model,
        )
