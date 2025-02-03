import ollama
from typing import Tuple, List, Dict

from .async_utils import batched_parallel
from .db_api import DbApiClient
from .embeddings import EmbeddingClient


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
        self, ollama_base_url: str, db_api: DbApiClient, embedding: EmbeddingClient
    ):
        self.db_api = db_api
        self.embedding = embedding
        self.ollam_client = ollama.Client(host=ollama_base_url)

    async def _retrieve_chunks(self, query_texts, n_results):
        embeddings = await self.embedding._create_embeddings(query_texts)
        return await self.db_api._get_multiple_closest(embeddings, n_results)

    def retrieve_chunks(
        self,
        query_texts: List[str],
        n_results: int = 5,
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
        return batched_retrieve_chunks(query_texts, n_results)

    def format_prompt(
        self, query: str, context_chunks: List[str], prompt_template: str = None
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

    def generate_answer(
        self,
        query: str,
        context_chunks: List[str],
        prompt: str,
        ollama_model: str = "llama3.2:1b",
    ) -> str:
        formatted_prompt = self.format_prompt(
            query, context_chunks=context_chunks, prompt_template=prompt
        )
        response = self.ollam_client.generate(
            model=ollama_model, prompt=formatted_prompt, stream=True
        )
        answer = ""
        eval_count = 0
        eval_duration = 0
        for chunk in response:
            if "response" in chunk:
                token = chunk.response
                answer += token
                eval_count += chunk.eval_count if chunk.eval_count else 0
                eval_duration += chunk.eval_duration if chunk.eval_duration else 0
        tok_s = eval_count / eval_duration * 10**9
        return answer, tok_s
