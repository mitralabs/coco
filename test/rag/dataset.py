import datetime
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Sample:
    """A single sample in a RAG dataset.

    Contains all information necessary to compute retrieval and generation metrics:
    - category: The category of the sample
    - query: The question or query text
    - gt_answer: The expected answer(s)
    - pos_chunks: Relevant contexts that should be retrieved
    - neg_chunks: Irrelevant contexts that should not be retrieved
    - hn_chunks: Deceptively similar but irrelevant contexts
    """

    category: str
    query: str
    gt_answers: List[str]
    pos_chunks: List[str]  # List of text chunks
    neg_chunks: Optional[List[str]] = None  # List of text chunks
    hn_chunks: Optional[List[str]] = None  # List of text chunks

    def all_chunks(self) -> List[str]:
        """Get all chunks (positive, hard negative, and negative) in that order."""
        chunks = self.pos_chunks.copy()
        if self.hn_chunks:
            chunks.extend(self.hn_chunks)
        if self.neg_chunks:
            chunks.extend(self.neg_chunks)
        return chunks


class RAGDataset:
    """A dataset consisting of RAG samples.

    This class serves as a container for Sample objects and provides
    utility methods for working with the dataset.
    """

    def __init__(
        self,
        samples: List[Sample],
        supports_retrieval: bool,
        additional_chunks: Optional[List[str]] = None,
        additional_chunk_datetimes: Optional[List[datetime.datetime]] = None,
    ):
        """Initialize a dataset with a list of samples."""
        self.samples = samples
        self.supports_retrieval = supports_retrieval
        self.additional_chunks = additional_chunks
        self.additional_chunk_datetimes = additional_chunk_datetimes

    def __len__(self) -> int:
        """Return the number of samples in the dataset."""
        return len(self.samples)

    def __getitem__(self, idx):
        """Get a sample by index or slice the dataset.

        Args:
            idx: An integer index or a slice object

        Returns:
            Sample: If idx is an integer, returns the sample at that index
            Dataset: If idx is a slice, returns a new dataset with the sliced samples
        """
        if isinstance(idx, slice):
            return RAGDataset(self.samples[idx])
        return self.samples[idx]

    def __iter__(self):
        """Iterate over samples in the dataset."""
        return iter(self.samples)

    def unique_chunks(self) -> Tuple[List[str], List[datetime.datetime]]:
        """Get all unique chunks from all samples in the dataset.

        Returns:
            Tuple[List[str], List[datetime.datetime]]: List of unique chunks and their datetimes.
        """
        sample_chunk_pairs = [
            (chunk, None) for sample in self.samples for chunk in sample.all_chunks()
        ]
        additional_chunk_pairs = [
            (chunk, datetime)
            for chunk, datetime in zip(
                self.additional_chunks, self.additional_chunk_datetimes
            )
        ]
        unique_chunk_pairs = list(set(sample_chunk_pairs + additional_chunk_pairs))
        chunks = [chunk for chunk, _ in unique_chunk_pairs]
        chunk_datetimes = [datetime for _, datetime in unique_chunk_pairs]
        return chunks, chunk_datetimes

    def queries(self) -> List[str]:
        """Get all queries from all samples in the dataset."""
        return [sample.query for sample in self.samples]

    def unique_categories(self) -> List[str]:
        """Get unique categories from all samples in the dataset."""
        return list(set(sample.category for sample in self.samples))

    @classmethod
    def from_dpr_dataset(cls, dpr_dataset) -> "RAGDataset":
        """Create a Dataset from a Hugging Face DPR-formatted dataset."""
        samples = []

        for dpr_sample in dpr_dataset:
            pos_chunks = dpr_sample["positive_ctxs"]["text"]

            neg_chunks = None
            if (
                "negative_ctxs" in dpr_sample
                and len(dpr_sample["negative_ctxs"]["text"]) > 0
            ):
                neg_chunks = dpr_sample["negative_ctxs"]["text"]

            hn_chunks = None
            if (
                "hard_negative_ctxs" in dpr_sample
                and len(dpr_sample["hard_negative_ctxs"]["text"]) > 0
            ):
                hn_chunks = dpr_sample["hard_negative_ctxs"]["text"]

            sample = Sample(
                category="default",
                query=dpr_sample["question"],
                gt_answers=dpr_sample["answers"],
                pos_chunks=pos_chunks,
                neg_chunks=neg_chunks,
                hn_chunks=hn_chunks,
            )
            samples.append(sample)

        return cls(samples, supports_retrieval=True)

    @classmethod
    def from_custom_datasets(cls, custom_datasets: Dict[str, Any]) -> "RAGDataset":
        """Create a Dataset from a custom dataset."""
        samples = []
        all_chunks = []
        all_chunk_datetimes = []
        for category, dataset in custom_datasets.items():
            for q, a, chunks, chunk_datetimes in zip(
                dataset["question"],
                dataset["answer"],
                dataset["chunks"],
                dataset["chunk_datetimes"],
            ):
                samples.append(
                    Sample(
                        category=category,
                        query=q,
                        gt_answers=[a],
                        pos_chunks=None,
                        neg_chunks=None,
                        hn_chunks=None,
                    )
                )
                all_chunks.extend(chunks)
                all_chunk_datetimes.extend(chunk_datetimes)
        return cls(
            samples,
            supports_retrieval=False,
            additional_chunks=all_chunks,
            additional_chunk_datetimes=all_chunk_datetimes,
        )
