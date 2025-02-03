import numpy as np
import wandb
from omegaconf import DictConfig
from coco import CocoClient
from typing import Dict, List, Any
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


def get_answers(
    top_chunks: Dict[str, Dict[str, List]], cc: CocoClient, cfg: DictConfig
) -> Dict[str, Dict[str, Any]]:
    top_chunks = {k: v for k, v in list(top_chunks.items())[:100]}  # ! tmp
    # load from file if present
    if Path(cfg.generation.get_answers.file_name).exists():
        with open(cfg.generation.get_answers.file_name, "r") as f:
            answers = json.load(f)
        logger.info(f"Loaded answers from {cfg.generation.get_answers.file_name}")
        return answers

    # obtain from db
    queries, context_chunks = [], []
    for query, chunks in top_chunks.items():
        queries.append(query)
        context_chunks.append(chunks["documents"][: cfg.generation.get_answers.top_k])

    generated_answers, tok_ss = cc.rag.generate_answers(
        queries=queries,
        context_chunks=context_chunks,
        prompt_template=cfg.generation.get_answers.prompt_template,
        ollama_model=cfg.generation.get_answers.ollama_model,
        pull_model=True,
        batch_size=cfg.generation.get_answers.generate_answers_batch_size,
        limit_parallel=cfg.generation.get_answers.generate_answers_limit_parallel,
        show_progress=True,
    )
    wandb.log({"generation/m_tok_s": np.mean(tok_ss)})
    logger.info(
        f"Generated {len(generated_answers)} answers with mean tok_s {np.mean(tok_ss)}"
    )

    # save to file
    Path(cfg.generation.get_answers.file_name).parent.mkdir(parents=True, exist_ok=True)
    answers = {q: a for q, a in zip(queries, generated_answers)}
    with open(cfg.generation.get_answers.file_name, "w") as f:
        json.dump(answers, f)
    logger.info(f"Saved answers to {cfg.generation.get_answers.file_name}")

    return answers


def generation_stage(
    cc: CocoClient, cfg: DictConfig, top_chunks: Dict[str, Dict[str, List]]
) -> None:
    answers = get_answers(top_chunks, cc, cfg)
