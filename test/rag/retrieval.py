import numpy as np
import wandb
from collections import defaultdict
from omegaconf import DictConfig
import json
from pathlib import Path
import logging
from coco import CocoClient
from typing import Dict, Any, List
from tqdm import tqdm

from dataset import RAGDataset

logger = logging.getLogger(__name__)


def get_top_chunks(
    cc: CocoClient, cfg: DictConfig, ds: RAGDataset
) -> Dict[str, Dict[str, Any]]:
    if cfg.retrieval.get_top_chunks.load_from_file:
        # load from file if specified
        chunks_file = Path(cfg.retrieval.get_top_chunks.load_file_name)
        with chunks_file.open("r") as f:
            top_chunks = json.load(f)
        logger.info(f"Loaded retrieved chunks from {chunks_file}")
        if (
            not len(top_chunks[next(iter(top_chunks))]["ids"])
            == cfg.retrieval.get_top_chunks.top_k
        ):
            logger.warning(f"Retrieved chunks from {chunks_file} do not match top_k")
    else:
        # obtain from db
        top_chunks = {}
        queries = ds.queries()
        results = cc.rag.retrieve_multiple(
            query_texts=queries,
            n_results=cfg.retrieval.get_top_chunks.top_k,
            model=cfg.retrieval.embedding_model[0],
            show_progress=True,
        )
        for query, (ids, documents, metadatas, distances) in zip(queries, results):
            top_chunks[query] = {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
                "distances": distances,
            }
        logger.info(f"Retrieved chunks from database")

    # save to file
    output_file = Path(cfg.retrieval.get_top_chunks.output_file_name)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w") as f:
        json.dump(top_chunks, f)
    logger.info(f"Saved retrieved chunks to {output_file}")

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
    inv = 1 / np.array(ranks)
    inv[np.isnan(inv)] = 0
    return np.mean(inv)


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


def relevance(top_chunks: Dict[str, Dict[str, Any]], cfg: DictConfig, ds: RAGDataset):
    """Compute context relevance metrics and log to wandb.

    Args:
        top_chunks (Dict[str, Dict[str, Any]]): top chunks for each query
        cfg (DictConfig): config
        ds (RAGDataset): dataset
    """
    category_sample_metrics = {
        cat: {
            "precs": defaultdict(list),
            "recs": defaultdict(list),
            "f1s": defaultdict(list),
            "ranks": [],
            "aps": [],
        }
        for cat in ds.unique_categories()
    }
    category_sample_metrics["full"] = {
        "precs": defaultdict(list),
        "recs": defaultdict(list),
        "f1s": defaultdict(list),
        "ranks": [],
        "aps": [],
    }

    # sample wise metrics
    for sample in tqdm(ds, desc="Computing context relevance metrics"):
        retrieved_chunks = top_chunks[sample.query]["documents"]

        # order independent metrics
        for k in cfg.retrieval.metric_ks:
            prec = precision_at_k(retrieved_chunks, sample.pos_chunks, k)
            rec = recall_at_k(retrieved_chunks, sample.pos_chunks, k)
            f1 = f1_score(prec, rec)
            category_sample_metrics[sample.category]["precs"][k].append(prec)
            category_sample_metrics[sample.category]["recs"][k].append(rec)
            category_sample_metrics[sample.category]["f1s"][k].append(f1)

        # order aware metrics
        category_sample_metrics[sample.category]["ranks"].append(
            rank_first_relevant(retrieved_chunks, sample.pos_chunks, cfg)
        )
        category_sample_metrics[sample.category]["aps"].append(
            average_precision(retrieved_chunks, sample.pos_chunks)
        )

    # aggregate metrics across categories
    for cat, sample_metrics in category_sample_metrics.items():
        if cat == "full":
            continue
        for k in cfg.retrieval.metric_ks:
            category_sample_metrics["full"]["precs"][k].extend(
                sample_metrics["precs"][k]
            )
            category_sample_metrics["full"]["recs"][k].extend(sample_metrics["recs"][k])
            category_sample_metrics["full"]["f1s"][k].extend(sample_metrics["f1s"][k])
        category_sample_metrics["full"]["ranks"].extend(sample_metrics["ranks"])
        category_sample_metrics["full"]["aps"].extend(sample_metrics["aps"])

    for cat, sample_metrics in category_sample_metrics.items():
        # dataset wise order independent metrics
        macro_avg_prec, macro_avg_rec, macro_avg_f1 = {}, {}, {}
        for k in cfg.retrieval.metric_ks:
            macro_avg_prec[k] = np.nanmean(np.array(sample_metrics["precs"][k]))
            macro_avg_rec[k] = np.nanmean(np.array(sample_metrics["recs"][k]))
            macro_avg_f1[k] = np.nanmean(np.array(sample_metrics["f1s"][k]))

        # dataset wise order aware metrics
        m_r = np.nanmean(np.array(sample_metrics["ranks"]))
        m_rr = mean_reciprocal_rank(sample_metrics["ranks"])
        m_ap = mean_average_precision(sample_metrics["aps"])

        metrics = {
            "mr": m_r,
            "mrr": m_rr,
            "map": m_ap,
        }
        for k in cfg.retrieval.metric_ks:
            metrics[f"precision@{str(k).zfill(4)}"] = np.nanmean(
                np.array(sample_metrics["precs"][k])
            )
            metrics[f"recall@{str(k).zfill(4)}"] = np.nanmean(
                np.array(sample_metrics["recs"][k])
            )
            metrics[f"f1@{str(k).zfill(4)}"] = np.nanmean(
                np.array(sample_metrics["f1s"][k])
            )
        wandb.log(
            {f"retrieval/{cat}/context_relevance/{k}": v for k, v in metrics.items()}
        )


def retrieval_stage(cc: CocoClient, cfg: DictConfig, ds: RAGDataset):
    if cfg.retrieval.skip:
        logger.info("Retrieval stage skipped")
        return None
    if not ds.supports_retrieval:
        logger.warning(
            "Retrieval stage skipped even though it was configured to run because dataset does not support retrieval"
        )
        return None
    logger.info("Starting retrieval stage")
    top_chunks = get_top_chunks(cc, cfg, ds)
    relevance(top_chunks, cfg, ds)
    logger.info("Retrieval stage completed")
    return top_chunks
