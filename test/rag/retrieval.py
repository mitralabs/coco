from datasets import Dataset
from omegaconf import DictConfig
import json
from pathlib import Path
import logging
from tqdm import tqdm
from coco import CocoClient


logger = logging.getLogger(__name__)


def get_top_chunks(cc: CocoClient, cfg: DictConfig, ds: Dataset):
    # load from file if present
    if Path(cfg.retrieval.get_top_chunks.file_name).exists():
        with open(cfg.retrieval.get_top_chunks.file_name, "r") as f:
            top_chunks = json.load(f)
        logger.info(
            f"Loaded retrieved chunks from {cfg.retrieval.get_top_chunks.file_name}"
        )
        if (
            not len(top_chunks[top_chunks.keys()[0]]["ids"])
            == cfg.retrieval.get_top_chunks.top_k
        ):
            logger.warning(
                f"Retrieved chunks from {cfg.retrieval.get_top_chunks.file_name} do not match top_k"
            )
        return top_chunks

    # obtain from db
    top_chunks = {}
    for sample in tqdm(ds, desc="Retrieving top chunks", total=len(ds)):
        query = sample["question"]
        ids, documents, metadatas, distances = cc.db_api.query_database(
            query_text=query, n_results=cfg.retrieval.get_top_chunks.top_k
        )
        top_chunks[query] = {
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
            "distances": distances,
        }

    # save to file
    Path(cfg.retrieval.get_top_chunks.file_name).parent.mkdir(
        parents=True, exist_ok=True
    )
    with open(cfg.retrieval.get_top_chunks.file_name, "w") as f:
        json.dump(top_chunks, f)
    logger.info(f"Saved retrieved chunks to {cfg.retrieval.get_top_chunks.file_name}")

    return top_chunks


def handle_retrieval(cc: CocoClient, cfg: DictConfig, ds: Dataset):
    top_chunks = get_top_chunks(cc, cfg, ds)
