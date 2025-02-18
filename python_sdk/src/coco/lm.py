from typing import List, Literal, Tuple
import json
import time
import logging
import ollama
import openai
import httpx
import os

from .async_utils import batched_parallel

logger = logging.getLogger(__name__)


class LanguageModelClient:
    def __init__(
        self,
        ollama_base_url: str,
        openai_base_url: str,
        embedding_api: Literal["ollama", "openai"],
        llm_api: Literal["ollama", "openai"],
    ):
        self.ollama_base_url = ollama_base_url
        self.openai_base_url = openai_base_url
        self.embedding_api = embedding_api
        self.llm_api = llm_api

        assert (
            self.ollama_base_url or self.openai_base_url
        ), "Neither ollama or openai base URLs are set"

        if self.embedding_api == "ollama" or self.llm_api == "ollama":
            self.async_ollama = ollama.AsyncClient(host=ollama_base_url)
            self.ollama = ollama.Client(host=ollama_base_url)
        if self.embedding_api == "openai" or self.llm_api == "openai":
            self.async_openai = openai.AsyncOpenAI(
                base_url=openai_base_url, api_key=os.environ.get("OPENAI_API_KEY")
            )
            self.openai = openai.OpenAI(
                base_url=openai_base_url, api_key=os.environ.get("OPENAI_API_KEY")
            )

    def get_embedding_dim(self, model: str) -> int:
        """Get the dimension of the embedding for a given model.

        Args:
            model (str): The model to get the embedding dimension for.

        Raises:
            ValueError: If the embedding dimension is not found in the modelinfo.

        Returns:
            int: The dimension of the embedding for the given model.
        """
        if self.embedding_api == "ollama":
            show_response = self.ollama.show(model)
            length_key = None
            for k in show_response.modelinfo:
                if "embedding_length" in k:
                    length_key = k
                    break
            if length_key is None:
                raise ValueError("embedding_length key not found in modelinfo")
            return show_response.modelinfo[length_key]
        elif self.embedding_api == "openai":
            res = self.openai.embeddings.create(model=model, input=["Some mock text."])
            dim = len(res.data[0].embedding)
            return dim

    async def _embed(
        self, chunks: List[str], model: str = "nomic-embed-text"
    ) -> List[List[float]]:
        if self.embedding_api == "ollama":
            # response = await self.async_ollama.embed(model=model, input=chunks)
            # return response.embeddings
            headers = {"Content-Type": "application/json"}
            embedding_api_data = {"model": model, "input": chunks}
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.ollama_base_url}/api/embed",
                    json=embedding_api_data,
                    headers=headers,
                )
                response.raise_for_status()
                response_json = response.json()
                if "embeddings" not in response_json:
                    raise RuntimeError(
                        f"Ollama did not return embeddings. Response: {response_json}"
                    )
                embeddings = response_json["embeddings"]
                return embeddings
        elif self.embedding_api == "openai":
            embed_response = await self.async_openai.embeddings.create(
                model=model, input=chunks
            )
            return [d.embedding for d in embed_response.data]

    def embed(
        self,
        chunks: List[str],
        model: str = "nomic-embed-text",
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = False,
    ) -> List[List[float]]:
        """Create embeddings for a list of chunks.

        Args:
            chunks (List[str]): The chunks to embed.
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to False.

        Returns:
            List[List[float]]: The embeddings of the chunks.
        """
        batched_create_embeddings = batched_parallel(
            function=self._embed,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Creating embeddings",
        )
        return batched_create_embeddings(chunks, model=model)

    async def _generate(
        self, prompts: List[str], model: str = "llama3.2:1b", temperature: float = 0.0
    ) -> str:
        if self.llm_api == "ollama":
            texts, tok_ss = [], []
            for prompt in prompts:
                response = await self.async_ollama.generate(
                    model=model, prompt=prompt, options={"temperature": temperature}
                )
                texts.append(response.response)
                tok_ss.append(response.eval_count / response.eval_duration * 10**9)
        elif self.llm_api == "openai":
            texts, tok_ss = [], []
            for prompt in prompts:
                for attempt in range(3):
                    try:
                        start = time.time()
                        response = await self.async_openai.chat.completions.create(
                            model=model,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=temperature,
                        )
                        tok_ss.append(
                            response.usage.completion_tokens / (time.time() - start)
                        )
                        texts.append(response.choices[0].message.content)
                        break
                    except openai.NotFoundError as e:
                        if attempt == 2:  # Last attempt failed
                            raise e
                        logger.warning(
                            f"OpenAI api gave not found error. Retrying ({attempt + 1}/3)"
                        )
                        continue
                    except openai.RateLimitError as e:
                        if attempt == 2:
                            raise e
                        logger.warning(
                            f"OpenAI api gave rate limit error. Retrying in 60 seconds ({attempt + 1}/3)"
                        )
                        time.sleep(61)  # ionos api wants 60 seconds before retry
                        continue
                    except json.JSONDecodeError as e:
                        if attempt == 2:
                            raise e
                        logger.warning(
                            f"OpenAI api gave json decode error. Retrying ({attempt + 1}/3)"
                        )
                        continue
        return texts, tok_ss

    def generate(
        self,
        prompts: List[str],
        model: str = "llama3.2:1b",
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = False,
    ) -> Tuple[List[str], List[float]]:
        """Generate text from a list of prompts.

        Args:
            prompts (List[str]): The prompts to generate text from.
            model (str, optional): The model to use for generation. Defaults to "llama3.2:1b".
            batch_size (int, optional): The size of each batch. Defaults to 20.
            limit_parallel (int, optional): The maximum number of parallel tasks / batches. Defaults to 10.
            show_progress (bool, optional): Whether to show a progress bar on stdout. Defaults to False.

        Returns:
            Tuple[List[str], List[float]]: The generated text and the token speeds.
        """
        batched_generate = batched_parallel(
            function=self._generate,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
        )

        return batched_generate(prompts, model=model)

    def list_llm_models(self) -> List[str]:
        """List available LLM models. For now just list all models.

        Returns:
            List[str]: List of model names
        """
        if self.llm_api == "ollama":
            return self._list_ollama_models()
        elif self.llm_api == "openai":
            return self._list_openai_models()

    def list_embedding_models(self) -> List[str]:
        """List available embedding models. For now just list all models.

        Returns:
            List[str]: List of model names
        """
        if self.embedding_api == "ollama":
            return self._list_ollama_models()
        elif self.embedding_api == "openai":
            return self._list_openai_models()

    def _list_ollama_models(self) -> List[str]:
        list_response = self.ollama.list()
        return [i["model"] for i in list_response.models]

    def _list_openai_models(self) -> List[str]:
        list_response = self.openai.models.list()
        return [i.id for i in list_response.data]

    def pull_ollama_model(self, model: str):
        assert (
            self.embedding_api == "ollama" or self.llm_api == "ollama"
        ), "Pull model is only supported for ollama"
        self.ollama.pull(model)

    async def _chat(
        self, messages_list: List[List[dict]], model: str = "llama3.2:1b"
    ) -> Tuple[List[str], List[float]]:
        if self.llm_api == "ollama":
            # TODO handle messages larger than ollama max context window
            texts, tok_ss = [], []
            for messages in messages_list:
                response = await self.async_ollama.chat(model=model, messages=messages)
                texts.append(response["message"]["content"])
                tok_ss.append(
                    response["eval_count"] / response["eval_duration"] * 10**9
                )
        elif self.llm_api == "openai":
            texts, tok_ss = [], []
            for messages in messages_list:
                start = time.time()
                response = await self.async_openai.chat.completions.create(
                    model=model, messages=messages
                )
                tok_ss.append(response.usage.completion_tokens / (time.time() - start))
                texts.append(response.choices[0].message.content)
        return texts, tok_ss

    def chat(
        self,
        messages_list: List[List[dict]],
        model: str = "llama3.2:1b",
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = False,
    ) -> Tuple[List[str], List[float]]:
        """Generate text from a list of message dictionaries.

        Args:
            messages_list (List[List[dict]]): List of message sequences to generate from
            model (str, optional): The model to use. Defaults to "llama3.2:1b".
            batch_size (int, optional): Size of each batch. Defaults to 20.
            limit_parallel (int, optional): Max parallel batches. Defaults to 10.
            show_progress (bool, optional): Show progress bar. Defaults to False.

        Returns:
            Tuple[List[str], List[float]]: Generated texts and token speeds
        """
        batched_chat = batched_parallel(
            function=self._chat,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
        )

        return batched_chat(messages_list, model=model)

    async def async_chat(
        self,
        messages_list: List[List[dict]],
        model: str = "llama3.2:1b",
        batch_size: int = 20,
        limit_parallel: int = 10,
        show_progress: bool = False,
    ) -> Tuple[List[str], List[float]]:
        """Generate text from a list of message dictionaries.

        Args:
            messages_list (List[List[dict]]): List of message sequences to generate from
            model (str, optional): The model to use. Defaults to "llama3.2:1b".
            batch_size (int, optional): Size of each batch. Defaults to 20.
            limit_parallel (int, optional): Max parallel batches. Defaults to 10.
            show_progress (bool, optional): Show progress bar. Defaults to False.

        Returns:
            Tuple[List[str], List[float]]: Generated texts and token speeds
        """
        batched_chat = batched_parallel(
            function=self._chat,
            batch_size=batch_size,
            limit_parallel=limit_parallel,
            show_progress=show_progress,
            description="Generating chat text",
            return_async_wrapper=True,
        )

        return await batched_chat(messages_list, model=model)
