import datetime
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Literal
from pathlib import Path

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
    pos_chunks: List[str]
    neg_chunks: List[str] = field(default_factory=list)
    hn_chunks: List[str] = field(default_factory=list)

    def all_chunks(self) -> List[str]:
        """Get all chunks (positive, hard negative, and negative) in that order."""
        chunks = self.pos_chunks.copy()
        chunks.extend(self.hn_chunks)
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
        additional_chunks: Optional[List[str]] = [],
        additional_chunk_datetimes: Optional[List[datetime.datetime]] = [],
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
            return RAGDataset(
                self.samples[idx],
                self.supports_retrieval,
                self.additional_chunks,
                self.additional_chunk_datetimes,
            )
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
            sample = Sample(
                category="default",
                query=dpr_sample["question"],
                gt_answers=dpr_sample["answers"],
                pos_chunks=dpr_sample["positive_ctxs"]["text"],
                neg_chunks=dpr_sample["negative_ctxs"]["text"],
                hn_chunks=dpr_sample["hard_negative_ctxs"]["text"],
            )
            samples.append(sample)

        return cls(samples, supports_retrieval=True)

    @classmethod
    def from_custom_datasets(
        cls, custom_datasets: Dict[str, Any], split: Literal["train", "test", "full"]
    ) -> "RAGDataset":
        """Create a Dataset from a custom dataset."""
        assert split in ["train", "test", "full"], "split must be train, test, or full"
        samples = []
        all_chunks = []
        all_chunk_datetimes = []
        for category, dataset in custom_datasets.items():
            split_idx = int(len(dataset["question"]) * 0.8)
            if split == "full":
                split_slice = slice(0, len(dataset["question"]))
            elif split == "train":
                split_slice = slice(0, split_idx)
            else:
                split_slice = slice(split_idx, len(dataset["question"]))
            for q, a, chunks, chunk_datetimes in zip(
                dataset["question"][split_slice],
                dataset["answer"][split_slice],
                dataset["chunks"][split_slice],
                dataset["chunk_datetimes"][split_slice],
            ):
                samples.append(
                    Sample(
                        category=category,
                        query=q,
                        gt_answers=[a],
                        pos_chunks=[],
                        neg_chunks=[],
                        hn_chunks=[],
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

    @classmethod
    def from_new_json_format(
        cls, path: str, split: Literal["train", "test", "full"]
    ) -> "RAGDataset":
        """Create a Dataset from the new JSON format (list of dicts with query, gt_answer, chunk_ids)."""
        with Path(path).open("r") as f:
            data = json.load(f)

        # chunks
        chunks, chunk_datetimes = [], []
        for c in data["chunks"]:
            chunks.append(c["text"])
            chunk_datetimes.append(
                datetime.datetime.strptime(c["datetime"], "%Y-%m-%d %H:%M")
            )
        assert len(chunks) == len(chunk_datetimes) == 500, "chunkbase size not 500"

        # samples
        samples = []
        for sample_cat in data["samples"]:
            assert len(sample_cat["samples"]) == 20, "sample_cat size not 20"
            split_idx = int(len(sample_cat["samples"]) * 0.8)
            if split == "full":
                split_slice = slice(0, len(sample_cat["samples"]))
            elif split == "train":
                split_slice = slice(0, split_idx)
            else:
                split_slice = slice(split_idx, len(sample_cat["samples"]))
            for sample in sample_cat["samples"][split_slice]:
                samples.append(
                    Sample(
                        category=sample_cat["category"],
                        query=sample["query"],
                        gt_answers=[sample["gt_answer"]],
                        pos_chunks=[],
                        neg_chunks=[],
                        hn_chunks=[],
                    )
                )

        return cls(
            samples,
            supports_retrieval=False,
            additional_chunks=chunks,
            additional_chunk_datetimes=chunk_datetimes,
        )
