import numpy as np
import wandb
from datasets import Dataset
from collections import defaultdict
from omegaconf import DictConfig
import json
from pathlib import Path
import logging
from coco import CocoClient
from typing import Dict, Any, List
from tqdm import tqdm

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
            not len(top_chunks[next(iter(top_chunks))]["ids"])
            == cfg.retrieval.get_top_chunks.top_k
        ):
            logger.warning(
                f"Retrieved chunks from {cfg.retrieval.get_top_chunks.file_name} do not match top_k"
            )
        return top_chunks

    # obtain from db
    top_chunks = {}
    queries = [sample["question"] for sample in ds]
    results = cc.rag.retrieve_chunks(
        query_texts=queries,
        n_results=cfg.retrieval.get_top_chunks.top_k,
        model=cfg.data.fill_db.embedding_model,
        show_progress=True,
    )
    for query, (ids, documents, metadatas, distances) in zip(queries, results):
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


def precision_at_k(retrieved_chunks: List[str], gt_chunks: List[str], k: int):
    if k > len(retrieved_chunks):
        return float("nan")
    retrieved_chunks_k = retrieved_chunks[:k]
    n_correct = len(set(gt_chunks) & set(retrieved_chunks_k))
    return n_correct / k


def recall_at_k(retrieved_chunks: List[str], gt_chunks: List[str], k: int):
    if k > len(retrieved_chunks):
        return float("nan")
    retrieved_chunks_k = retrieved_chunks[:k]
    n_correct = len(set(gt_chunks) & set(retrieved_chunks_k))
    return n_correct / len(gt_chunks)


def f1_score(precision: float, recall: float):
    if precision == float("nan") or recall == float("nan"):
        return float("nan")
    if precision == 0 or recall == 0:
        return 0
    return 2 * (precision * recall) / (precision + recall)


def rank_first_relevant(
    retrieved_chunks: List[str], gt_chunks: List[str], cfg: DictConfig
):
    for i, retrieved_chunk in enumerate(retrieved_chunks):
        if retrieved_chunk in gt_chunks:
            return i + 1
    return cfg.retrieval.rank_first_relevant_punishment


def mean_reciprocal_rank(ranks: List[int]):
    return np.nanmean(1 / np.array(ranks))


def average_precision(retrieved_chunks: List[str], gt_chunks: List[str]):
    weighted_precision = 0
    for gt_chunk in gt_chunks:
        try:
            idx = retrieved_chunks.index(gt_chunk)
        except ValueError:  # not present
            continue
        weighted_precision += precision_at_k(retrieved_chunks, gt_chunks, idx + 1)
    return weighted_precision / len(gt_chunks)


def mean_average_precision(aps: List[float]):
    return np.nanmean(np.array(aps))


def relevance(top_chunks: Dict[str, Dict[str, Any]], cfg: DictConfig, ds: Dataset):
    """Compute context relevance metrics and log to wandb.

    Args:
        top_chunks (Dict[str, Dict[str, Any]]): top chunks for each query
        cfg (DictConfig): config
        ds (Dataset): dataset
    """
    precs, recs, f1s = (
        defaultdict(list),
        defaultdict(list),
        defaultdict(list),
    )
    ranks, aps = [], []

    # sample wise metrics
    for sample in tqdm(ds, desc="Computing context relevance metrics"):
        query = sample["question"]
        gt_chunks = sample["positive_ctxs"]["text"]
        retrieved_chunks = top_chunks[query]["documents"]

        # order independent metrics
        for k in cfg.retrieval.metric_ks:
            prec = precision_at_k(retrieved_chunks, gt_chunks, k)
            rec = recall_at_k(retrieved_chunks, gt_chunks, k)
            f1 = f1_score(prec, rec)
            precs[k].append(prec)
            recs[k].append(rec)
            f1s[k].append(f1)

        # order aware metrics
        ranks.append(rank_first_relevant(retrieved_chunks, gt_chunks, cfg))
        aps.append(average_precision(retrieved_chunks, gt_chunks))

    # dataset wise order independent metrics
    macro_avg_prec, macro_avg_rec, macro_avg_f1 = {}, {}, {}
    for k in cfg.retrieval.metric_ks:
        macro_avg_prec[k] = np.nanmean(np.array(precs[k]))
        macro_avg_rec[k] = np.nanmean(np.array(recs[k]))
        macro_avg_f1[k] = np.nanmean(np.array(f1s[k]))

    # dataset wise order aware metrics
    m_r = np.nanmean(np.array(ranks))
    m_rr = mean_reciprocal_rank(ranks)
    m_ap = mean_average_precision(aps)

    metrics = {
        "mr": m_r,
        "mrr": m_rr,
        "map": m_ap,
    }
    for k in cfg.retrieval.metric_ks:
        metrics[f"precision@{str(k).zfill(4)}"] = np.nanmean(np.array(precs[k]))
        metrics[f"recall@{str(k).zfill(4)}"] = np.nanmean(np.array(recs[k]))
        metrics[f"f1@{str(k).zfill(4)}"] = np.nanmean(np.array(f1s[k]))
    wandb.log({f"retrieval/context_relevance/{k}": v for k, v in metrics.items()})


def retrieval_stage(cc: CocoClient, cfg: DictConfig, ds: Dataset):
    top_chunks = get_top_chunks(cc, cfg, ds)
    relevance(top_chunks, cfg, ds)
    return top_chunks
