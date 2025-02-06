import numpy as np
import wandb
from omegaconf import DictConfig
from coco import CocoClient
from typing import Dict, List, Any
from pathlib import Path
import json
import logging
from datasets import Dataset
from evaluate import load
from tqdm import tqdm

logger = logging.getLogger(__name__)


def get_answers(
    top_chunks: Dict[str, Dict[str, List]], cc: CocoClient, cfg: DictConfig
) -> Dict[str, Dict[str, Any]]:
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
        model=cfg.generation.get_answers.model,
        pull_model=False,
        batch_size=cfg.generation.get_answers.generate_answers_batch_size,
        limit_parallel=cfg.generation.get_answers.generate_answers_limit_parallel,
        show_progress=True,
    )
    wandb.log({"generation/m_tok_s": np.nanmean(np.array(tok_ss))})
    logger.info(
        f"Generated {len(generated_answers)} answers with mean tok_s {np.nanmean(np.array(tok_ss))}"
    )

    # save to file
    Path(cfg.generation.get_answers.file_name).parent.mkdir(parents=True, exist_ok=True)
    answers = {q: a for q, a in zip(queries, generated_answers)}
    with open(cfg.generation.get_answers.file_name, "w") as f:
        json.dump(answers, f)
    logger.info(f"Saved answers to {cfg.generation.get_answers.file_name}")

    return answers


# generated answer vs context (also called groundedness)
# ragas faithfulness, deepeval hallucination, raga context utilization
def groundedness(
    ds: Dataset,
    answers: Dict[str, Dict[str, Any]],
    top_chunks: Dict[str, Dict[str, List]],
):
    pass


# generated answer vs. query
# raga relevancy, cleanlab tlm (not os, might cost)
def relevance(ds: Dataset, answers: Dict[str, Dict[str, Any]]):
    pass


# generated answer vs. gt answer
# bertscore, rouge, (sacre)bleu, semscore
def correctness(ds: Dataset, answers: Dict[str, Dict[str, Any]], wandb_prefix: str):
    bertscore_metric = load("bertscore")
    rouge_metric = load("rouge")
    sacrebleu_metric = load("sacrebleu")
    bertscore_precisions, bertscore_recalls, bertscore_f1s = [], [], []
    rouge1s, rouge2s, rougeLs, rougeLsums = [], [], [], []
    (
        sacrebleu_scores,
        sacrebleu_1gram_precisions,
        sacrebleu_2gram_precisions,
        sacrebleu_3gram_precisions,
        sacrebleu_4gram_precisions,
        sacrebleu_bp,
    ) = ([], [], [], [], [], [])
    for sample in tqdm(ds, desc="Computing answer correctness metrics"):
        gt_answer = sample["answers"]
        assert len(gt_answer) == 1
        generated_answer = [answers[sample["question"]]]
        bertscore = bertscore_metric.compute(
            predictions=generated_answer,
            references=gt_answer,
            lang="de",
        )
        bertscore_precisions.append(bertscore["precision"])
        bertscore_recalls.append(bertscore["recall"])
        bertscore_f1s.append(bertscore["f1"])
        rouge = rouge_metric.compute(
            predictions=generated_answer,
            references=gt_answer,
        )
        rouge1s.append(rouge["rouge1"])
        rouge2s.append(rouge["rouge2"])
        rougeLs.append(rouge["rougeL"])
        rougeLsums.append(rouge["rougeLsum"])
        sacrebleu = sacrebleu_metric.compute(
            predictions=generated_answer,
            references=gt_answer,
        )
        sacrebleu_scores.append(sacrebleu["score"])
        sacrebleu_1gram_precisions.append(sacrebleu["precisions"][0])
        sacrebleu_2gram_precisions.append(sacrebleu["precisions"][1])
        sacrebleu_3gram_precisions.append(sacrebleu["precisions"][2])
        sacrebleu_4gram_precisions.append(sacrebleu["precisions"][3])
        sacrebleu_bp.append(sacrebleu["bp"])
    metrics = {
        "bertscore_precision": np.mean(bertscore_precisions),
        "bertscore_recall": np.mean(bertscore_recalls),
        "bertscore_f1": np.mean(bertscore_f1s),
        "rouge1": np.mean(rouge1s),
        "rouge2": np.mean(rouge2s),
        "rougeL": np.mean(rougeLs),
        "rougeLsum": np.mean(rougeLsums),
        "sacrebleu": np.mean(sacrebleu_scores),
        "sacrebleu_1gram_precision": np.mean(sacrebleu_1gram_precisions),
        "sacrebleu_2gram_precision": np.mean(sacrebleu_2gram_precisions),
        "sacrebleu_3gram_precision": np.mean(sacrebleu_3gram_precisions),
        "sacrebleu_4gram_precision": np.mean(sacrebleu_4gram_precisions),
        "sacrebleu_brevity_penalty": np.mean(sacrebleu_bp),
    }
    wandb.log({f"{wandb_prefix}/answer_correctness/{k}": v for k, v in metrics.items()})


def generation_stage(
    cc: CocoClient, cfg: DictConfig, top_chunks: Dict[str, Dict[str, List]], ds: Dataset
) -> None:
    answers = get_answers(top_chunks, cc, cfg)
    # eval_llm = OllamaLLM(model="llama3.1:8b", base_url=cfg.generation.ollama_base)
    # k = next(iter(answers.keys()))
    # print(k, answers[k])
    groundedness(ds, answers, top_chunks)
    relevance(ds, answers)
    correctness(ds, answers, "generation_ret")
