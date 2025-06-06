import numpy as np
from sentence_transformers import SentenceTransformer
import wandb
from omegaconf import DictConfig
from coco import CocoClient
from typing import Dict, List, Any, Callable, Optional
from pathlib import Path
import json
import logging
from evaluate import load
from tqdm import tqdm
from langchain_openai import ChatOpenAI
from ragas.dataset_schema import SingleTurnSample
from ragas.metrics import Faithfulness
from ragas.llms import LangchainLLMWrapper
import random
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from retrieval import get_top_chunks
from dataset import RAGDataset

logger = logging.getLogger(__name__)


def mock_top_chunks(ds: RAGDataset, cfg: DictConfig) -> Dict[str, Dict[str, List]]:
    """Mock top chunks using gt data and hard negatives.
    Since only the documents are used, metadata etc. is left as None.
    Distances are set to 0.0 for gt documents, 0.2 for hard negatives,
    and 0.5 for random documents.

    Args:
        ds (Dataset): Dataset to mock top chunks for
        cfg (DictConfig): Configuration

    Returns:
        Dict[str, Dict[str, List]]: Mocked top chunks
    """
    top_k = cfg.generation.get_answers.rag_top_k
    top_chunks = {}

    all_chunks, _ = ds.unique_chunks()

    for sample in ds:
        documents = sample.pos_chunks + sample.hn_chunks
        distances = ([0.0] * len(sample.pos_chunks)) + ([0.2] * len(sample.hn_chunks))

        # if gt and hard negatives are not enough, add random documents
        delta_to_top_k = top_k - len(documents)
        if delta_to_top_k > 0:
            documents += random.sample(population=all_chunks, k=delta_to_top_k)
            distances += [0.5] * delta_to_top_k

        # if gt and hard negatives are too many, remove some hard negatives
        if delta_to_top_k < 0:
            documents = documents[:top_k]
            distances = distances[:top_k]

        top_chunks[sample.query] = {
            "ids": [None] * len(documents),
            "documents": documents,
            "metadatas": [None] * len(documents),
            "distances": distances,
        }
    return top_chunks


def get_answers(
    top_chunks: Dict[str, Dict[str, List]],
    cc: CocoClient,
    cfg: DictConfig,
    wandb_prefix: str,
    load_from_file: bool,
    load_file_name: str,
    output_file_name: str,
    output_file_name_agent: str,
) -> Dict[str, Dict[str, Any]]:
    if load_from_file:
        # load from file if specified
        answers_file = Path(load_file_name)
        with answers_file.open("r") as f:
            answers = json.load(f)
        logger.info(f"Loaded answers from {answers_file}")
    else:
        # generate using lm
        if cfg.generation.get_answers.mode == "rag":
            queries, context_chunks = [], []
            for query, chunks in top_chunks.items():
                queries.append(query)
                context_chunks.append(
                    chunks["documents"][: cfg.generation.get_answers.rag_top_k]
                )

            generated_answers, tok_ss = cc.rag.answer_multiple(
                queries=queries,
                context_chunks=context_chunks,
                prompt_template=cfg.generation.get_answers.rag_prompt_template,
                model=cfg.generation.llm_model[0],
                temperature=0.0,
                pull_model=False,
                batch_size=cfg.generation.get_answers.rag_generate_answers_batch_size,
                limit_parallel=cfg.generation.get_answers.rag_generate_answers_limit_parallel,
                show_progress=True,
            )
            m_tok_s = np.nanmean(np.array(tok_ss))
            answers = {q: a for q, a in zip(queries, generated_answers)}
            wandb.log({f"{wandb_prefix}/m_tok_s": m_tok_s})
            logger.info(f"Generated answers with mean tok_s {m_tok_s}")
        else:
            queries = list(top_chunks.keys())
            results = cc.agent.chat_multiple(
                queries=queries,
                system_prompt=cfg.generation.get_answers.agent_system_prompt,
                model=cfg.generation.llm_model[0],
                max_tool_calls=cfg.generation.get_answers.agent_max_tool_calls,
                max_iterations=cfg.generation.get_answers.agent_max_iterations,
                temperature=0.0,
                pull_model=False,
                batch_size=cfg.generation.get_answers.agent_generate_answers_batch_size,
                limit_parallel=cfg.generation.get_answers.agent_generate_answers_limit_parallel,
                show_progress=True,
                return_just_answers=False,
            )
            answers = {q: r["content"] for q, r in zip(queries, results)}
            wandb.log(
                {
                    f"{wandb_prefix}/m_n_toolcalls": np.nanmean(
                        np.array([len(r["tool_calls"]) for r in results])
                    )
                }
            )
            logger.info(f"Generated answers with agent")

            # dump full history for all agentic answers
            dumpable_results = [r.copy() for r in results]
            for r in dumpable_results:
                r["tool_calls"] = [t.to_dict() for t in r["tool_calls"]]
            agent_conversations = {q: r for q, r in zip(queries, dumpable_results)}
            agent_conversations_file = Path(output_file_name_agent)
            agent_conversations_file.parent.mkdir(parents=True, exist_ok=True)
            with agent_conversations_file.open("w") as f:
                json.dump(agent_conversations, f)
            logger.info(f"Saved agent conversations to {agent_conversations_file}")
    # save to file
    output_file = Path(output_file_name)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w") as f:
        json.dump(answers, f)
    logger.info(f"Saved answers to {output_file}")

    return answers


class SemScore:
    def __init__(
        self,
        aggr_references: Callable = np.max,
        aggr_predictions: Callable = np.mean,
    ):
        """SemScore according to https://github.com/UKPLab/sentence-transformers/issues/1105

        Args:
            aggr_references (Callable, optional): _description_. Defaults to np.max.
            aggr_predictions (Callable, optional): _description_. Defaults to np.mean.
        """
        model_name_paper = "sentence-transformers/all-mpnet-base-v2"
        model_name_multilingual = (
            "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
        )
        self.model_paper = SentenceTransformer(model_name_paper)
        self.model_multilingual = SentenceTransformer(model_name_multilingual)
        self.aggr_references = aggr_references
        self.aggr_predictions = aggr_predictions

    def _score(
        self, predictions: List[str], references: List[str], model: SentenceTransformer
    ) -> float:
        pred_embeddings = model.encode(predictions, show_progress_bar=False)  # (n, dim)
        pred_embeddings = pred_embeddings / np.linalg.norm(
            pred_embeddings, ord=2, axis=1, keepdims=True
        )
        ref_embeddings = model.encode(references, show_progress_bar=False)  # (n, dim)
        ref_embeddings = ref_embeddings / np.linalg.norm(
            ref_embeddings, ord=2, axis=1, keepdims=True
        )
        all_scores = pred_embeddings @ ref_embeddings.T
        pred_scores = self.aggr_references(all_scores, axis=1)
        score = self.aggr_predictions(pred_scores)
        return score

    def __call__(self, predictions: List[str], references: List[str]) -> float:
        score_paper = self._score(predictions, references, self.model_paper)
        score_multilingual = self._score(
            predictions, references, self.model_multilingual
        )
        return {
            "paper": score_paper,
            "multilingual": score_multilingual,
        }


def groundedness(
    ds: RAGDataset,
    answers: Dict[str, Dict[str, Any]],
    top_chunks: Dict[str, Dict[str, List]],
    cfg: DictConfig,
    wandb_prefix: str,
):
    if not cfg.generation.ragas.skip:
        ragas_llm = LangchainLLMWrapper(
            ChatOpenAI(
                model=cfg.generation.ragas.openai_llm_model,
                temperature=0,
                base_url=cfg.generation.ragas.openai_base_url,
            )
        )
        ragas_faithfulness_metric = Faithfulness(llm=ragas_llm)

    category_sample_metrics = {
        cat: {"faithfulnesses": []} for cat in ds.unique_categories()
    }
    category_sample_metrics["full"] = {"faithfulnesses": []}

    for sample in tqdm(ds, desc="Computing groundedness metrics"):
        generated_answer = answers[sample.query]
        retrieved_chunks = top_chunks[sample.query]["documents"][
            : cfg.generation.get_answers.rag_top_k
        ]
        if not cfg.generation.ragas.skip:
            ragas_sample = SingleTurnSample(
                user_input=sample.query,
                response=generated_answer,
                retrieved_contexts=retrieved_chunks,
            )
            category_sample_metrics[sample.category]["faithfulnesses"].append(
                ragas_faithfulness_metric.single_turn_score(ragas_sample)
            )

    # aggregate metrics across categories
    for cat, sample_metrics in category_sample_metrics.items():
        if cat == "full":
            continue
        category_sample_metrics["full"]["faithfulnesses"].extend(
            sample_metrics["faithfulnesses"]
        )

    for cat, sample_metrics in category_sample_metrics.items():
        metrics = {}
        if not cfg.generation.ragas.skip:
            metrics["ragas_faithfulness"] = np.mean(sample_metrics["faithfulnesses"])
        wandb.log(
            {f"{wandb_prefix}/{cat}/groundedness/{k}": v for k, v in metrics.items()}
        )


def relevance(ds: RAGDataset, answers: Dict[str, Dict[str, Any]]):
    pass


def correctness(
    ds: RAGDataset,
    answers: Dict[str, Dict[str, Any]],
    wandb_prefix: str,
    cfg: DictConfig,
):
    bertscore_metric = load("bertscore")
    rouge_metric = load("rouge")
    sacrebleu_metric = load("sacrebleu")
    semscore_metric = SemScore()
    if not cfg.generation.geval.skip:
        GT = LLMTestCaseParams.EXPECTED_OUTPUT.value
        PRED = LLMTestCaseParams.ACTUAL_OUTPUT.value
        Q = LLMTestCaseParams.INPUT.value
        geval_correctness_metric = GEval(
            name="correctness",
            evaluation_steps=[
                f"List all statements made by {PRED}.",
                f"List all statements made by {GT}.",
                f"Make sure statements of {PRED} answer the question or fulfill the request posed by {Q}. (IMPORTANT: Only pay attention to semantic meanings, NOT sentence structure, grammar, word choice, etc.)",
                f"Make sure all statements of {PRED} are present in {GT}. (IMPORTANT: Only pay attention to semantic meanings, NOT sentence structure, grammar, word choice, etc.)",
                f"Make sure {PRED} contains no statements not present in {GT}. (IMPORTANT: Only pay attention to semantic meanings, NOT sentence structure, grammar, word choice, etc.)",
                f"Make sure you do not let differences in sentence structure, grammar, word choice, etc. affect your score.",
            ],
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT,
            ],
        )

    category_sample_metrics = {
        cat: {
            "bertscore_precisions": [],
            "bertscore_recalls": [],
            "bertscore_f1s": [],
            "rouge1s": [],
            "rouge2s": [],
            "rougeLs": [],
            "rougeLsums": [],
            "semscores_paper": [],
            "semscores_multilingual": [],
            "sacrebleu_scores": [],
            "sacrebleu_1gram_precisions": [],
            "sacrebleu_2gram_precisions": [],
            "sacrebleu_3gram_precisions": [],
            "sacrebleu_4gram_precisions": [],
            "sacrebleu_bp": [],
            "geval_correctness": [],
        }
        for cat in ds.unique_categories()
    }
    category_sample_metrics["full"] = {
        "bertscore_precisions": [],
        "bertscore_recalls": [],
        "bertscore_f1s": [],
        "rouge1s": [],
        "rouge2s": [],
        "rougeLs": [],
        "rougeLsums": [],
        "semscores_paper": [],
        "semscores_multilingual": [],
        "sacrebleu_scores": [],
        "sacrebleu_1gram_precisions": [],
        "sacrebleu_2gram_precisions": [],
        "sacrebleu_3gram_precisions": [],
        "sacrebleu_4gram_precisions": [],
        "sacrebleu_bp": [],
        "geval_correctness": [],
    }

    # load agent conversations json file if exists to add metrics
    agent_conversations = None
    if cfg.generation.get_answers.output_file_name_agent is not None:
        agent_conversations_file = Path(
            cfg.generation.get_answers.output_file_name_agent
        )
        if agent_conversations_file.exists():
            with agent_conversations_file.open("r") as f:
                agent_conversations = json.load(f)

    for sample in tqdm(ds, desc="Computing answer correctness metrics"):
        assert len(sample.gt_answers) == 1
        gt_answer = sample.gt_answers[0]
        generated_answer = answers[sample.query]

        bertscore = bertscore_metric.compute(
            predictions=[generated_answer],
            references=[gt_answer],
            lang="de",
        )
        category_sample_metrics[sample.category]["bertscore_precisions"].append(
            bertscore["precision"][0]
        )
        category_sample_metrics[sample.category]["bertscore_recalls"].append(
            bertscore["recall"][0]
        )
        category_sample_metrics[sample.category]["bertscore_f1s"].append(
            bertscore["f1"][0]
        )
        rouge = rouge_metric.compute(
            predictions=[generated_answer],
            references=[gt_answer],
        )
        category_sample_metrics[sample.category]["rouge1s"].append(rouge["rouge1"])
        category_sample_metrics[sample.category]["rouge2s"].append(rouge["rouge2"])
        category_sample_metrics[sample.category]["rougeLs"].append(rouge["rougeL"])
        category_sample_metrics[sample.category]["rougeLsums"].append(
            rouge["rougeLsum"]
        )
        sacrebleu = sacrebleu_metric.compute(
            predictions=[generated_answer],
            references=[gt_answer],
        )
        category_sample_metrics[sample.category]["sacrebleu_scores"].append(
            sacrebleu["score"]
        )
        category_sample_metrics[sample.category]["sacrebleu_1gram_precisions"].append(
            sacrebleu["precisions"][0]
        )
        category_sample_metrics[sample.category]["sacrebleu_2gram_precisions"].append(
            sacrebleu["precisions"][1]
        )
        category_sample_metrics[sample.category]["sacrebleu_3gram_precisions"].append(
            sacrebleu["precisions"][3]
        )
        category_sample_metrics[sample.category]["sacrebleu_bp"].append(sacrebleu["bp"])
        semscore_scores = semscore_metric(
            predictions=[generated_answer], references=[gt_answer]
        )
        category_sample_metrics[sample.category]["semscores_paper"].append(
            semscore_scores["paper"]
        )
        category_sample_metrics[sample.category]["semscores_multilingual"].append(
            semscore_scores["multilingual"]
        )
        if not cfg.generation.geval.skip:
            geval_correctness_metric.measure(
                LLMTestCase(
                    input=sample.query,
                    actual_output=generated_answer,
                    expected_output=gt_answer,
                )
            )
            category_sample_metrics[sample.category]["geval_correctness"].append(
                geval_correctness_metric.score
            )

        if agent_conversations is not None:
            agent_conversations[sample.query]["metrics"] = {
                "bertscore_precision": float(bertscore["precision"][0]),
                "bertscore_recall": float(bertscore["recall"][0]),
                "bertscore_f1": float(bertscore["f1"][0]),
                "rouge1": float(rouge["rouge1"]),
                "rouge2": float(rouge["rouge2"]),
                "rougeL": float(rouge["rougeL"]),
                "rougeLsum": float(rouge["rougeLsum"]),
                "sacrebleu_score": float(sacrebleu["score"]),
                "sacrebleu_precision1": float(sacrebleu["precisions"][0]),
                "sacrebleu_precision2": float(sacrebleu["precisions"][1]),
                "sacrebleu_precision3": float(sacrebleu["precisions"][3]),
                "sacrebleu_bp": float(sacrebleu["bp"]),
                "semscore_paper": float(semscore_scores["paper"]),
                "semscore_multilingual": float(semscore_scores["multilingual"]),
            }
            if not cfg.generation.geval.skip:
                agent_conversations[sample.query]["metrics"]["geval_correctness"] = (
                    float(geval_correctness_metric.score)
                )

    # save agent conversations json file if exists
    if agent_conversations is not None:
        with agent_conversations_file.open("w") as f:
            json.dump(agent_conversations, f)
        logger.info(f"Saved agent conversations to {agent_conversations_file}")

    # aggregate metrics across categories
    for cat, sample_metrics in category_sample_metrics.items():
        if cat == "full":
            continue
        category_sample_metrics["full"]["bertscore_precisions"].extend(
            sample_metrics["bertscore_precisions"]
        )
        category_sample_metrics["full"]["bertscore_recalls"].extend(
            sample_metrics["bertscore_recalls"]
        )
        category_sample_metrics["full"]["bertscore_f1s"].extend(
            sample_metrics["bertscore_f1s"]
        )
        category_sample_metrics["full"]["rouge1s"].extend(sample_metrics["rouge1s"])
        category_sample_metrics["full"]["rouge2s"].extend(sample_metrics["rouge2s"])
        category_sample_metrics["full"]["rougeLs"].extend(sample_metrics["rougeLs"])
        category_sample_metrics["full"]["rougeLsums"].extend(
            sample_metrics["rougeLsums"]
        )
        category_sample_metrics["full"]["sacrebleu_scores"].extend(
            sample_metrics["sacrebleu_scores"]
        )
        category_sample_metrics["full"]["sacrebleu_1gram_precisions"].extend(
            sample_metrics["sacrebleu_1gram_precisions"]
        )
        category_sample_metrics["full"]["sacrebleu_2gram_precisions"].extend(
            sample_metrics["sacrebleu_2gram_precisions"]
        )
        category_sample_metrics["full"]["sacrebleu_3gram_precisions"].extend(
            sample_metrics["sacrebleu_3gram_precisions"]
        )
        category_sample_metrics["full"]["sacrebleu_4gram_precisions"].extend(
            sample_metrics["sacrebleu_4gram_precisions"]
        )
        category_sample_metrics["full"]["sacrebleu_bp"].extend(
            sample_metrics["sacrebleu_bp"]
        )
        category_sample_metrics["full"]["semscores_paper"].extend(
            sample_metrics["semscores_paper"]
        )
        category_sample_metrics["full"]["semscores_multilingual"].extend(
            sample_metrics["semscores_multilingual"]
        )
        category_sample_metrics["full"]["geval_correctness"].extend(
            sample_metrics["geval_correctness"]
        )

    full_metrics = None
    for cat, sample_metrics in category_sample_metrics.items():
        metrics = {
            "bertscore_precision": np.mean(sample_metrics["bertscore_precisions"]),
            "bertscore_recall": np.mean(sample_metrics["bertscore_recalls"]),
            "bertscore_f1": np.mean(sample_metrics["bertscore_f1s"]),
            "rouge1": np.nanmean(np.array(sample_metrics["rouge1s"])),
            "rouge2": np.nanmean(np.array(sample_metrics["rouge2s"])),
            "rougeL": np.nanmean(np.array(sample_metrics["rougeLs"])),
            "rougeLsum": np.nanmean(np.array(sample_metrics["rougeLsums"])),
            "sacrebleu": np.nanmean(np.array(sample_metrics["sacrebleu_scores"])),
            "sacrebleu_precision1": np.nanmean(
                np.array(sample_metrics["sacrebleu_1gram_precisions"])
            ),
            "sacrebleu_precision2": np.nanmean(
                np.array(sample_metrics["sacrebleu_2gram_precisions"])
            ),
            "sacrebleu_precision3": np.nanmean(
                np.array(sample_metrics["sacrebleu_3gram_precisions"])
            ),
            "sacrebleu_precision4": np.nanmean(
                np.array(sample_metrics["sacrebleu_4gram_precisions"])
            ),
            "sacrebleu_brevity_penalty": np.nanmean(
                np.array(sample_metrics["sacrebleu_bp"])
            ),
            "semscore": np.mean(sample_metrics["semscores_paper"]),
            "semscore_multilingual": np.mean(sample_metrics["semscores_multilingual"]),
        }
        if not cfg.generation.geval.skip:
            metrics["geval_correctness"] = np.mean(sample_metrics["geval_correctness"])
        if cat == "full":
            full_metrics = metrics
        wandb.log(
            {
                f"{wandb_prefix}/{cat}/answer_correctness/{k}": v
                for k, v in metrics.items()
            }
        )
    assert full_metrics is not None, "Full metrics not found"
    return full_metrics


def generation_stage(
    cc: CocoClient,
    cfg: DictConfig,
    ds: RAGDataset,
    top_chunks: Optional[Dict[str, Dict[str, List]]] = None,
) -> None:
    if cfg.generation.skip:
        logger.info("Generation stage skipped")
        return

    if top_chunks is None:
        logger.info(
            "Top chunks not available because retrieval stage was skipped. Obtaining now."
        )
        top_chunks = get_top_chunks(cc, cfg, ds)

    logger.info("Starting generation stage for retrieved chunks")
    answers_ret = get_answers(
        top_chunks=top_chunks,
        cc=cc,
        cfg=cfg,
        wandb_prefix="generation",
        load_from_file=cfg.generation.get_answers.load_from_file,
        load_file_name=cfg.generation.get_answers.load_file_name_ret,
        output_file_name=cfg.generation.get_answers.output_file_name_ret,
        output_file_name_agent=cfg.generation.get_answers.output_file_name_agent,
    )
    groundedness(
        ds=ds,
        answers=answers_ret,
        top_chunks=top_chunks,
        cfg=cfg,
        wandb_prefix="generation",
    )
    relevance(ds=ds, answers=answers_ret)
    ret_corr_metrics = correctness(
        ds=ds,
        answers=answers_ret,
        wandb_prefix="generation",
        cfg=cfg,
    )
    logger.info("Generation stage for retrieved chunks completed")

    # optimization target for wandb sweeps
    optimization_target = (
        0.2 * ret_corr_metrics["geval_correctness"]
        + 0.2 * ret_corr_metrics["bertscore_f1"]
        + 0.2 * ret_corr_metrics["semscore"]
        + 0.2 * ret_corr_metrics["rougeLsum"]
        + 0.2 * (ret_corr_metrics["sacrebleu"] / 100)
    )
    wandb.log({"optimization_target": optimization_target})

    if not cfg.data.type == "custom":  # our dataset does not have gt chunks
        logger.info("Starting generation stage for ground truth chunks")
        mocked_top_chunks = mock_top_chunks(ds=ds, cfg=cfg)
        answers_gt = get_answers(
            top_chunks=mocked_top_chunks,
            cc=cc,
            cfg=cfg,
            wandb_prefix="generation_gt",
            load_from_file=cfg.generation.get_answers.load_from_file,
            load_file_name=cfg.generation.get_answers.load_file_name_gt,
            output_file_name=cfg.generation.get_answers.output_file_name_gt,
            output_file_name_agent=cfg.generation.get_answers.output_file_name_agent,
        )
        groundedness(
            ds=ds,
            answers=answers_gt,
            top_chunks=mocked_top_chunks,
            cfg=cfg,
            wandb_prefix="generation_gt",
        )
        relevance(ds=ds, answers=answers_gt)
        correctness(
            ds=ds,
            answers=answers_gt,
            wandb_prefix="generation_gt",
            cfg=cfg,
        )
        logger.info("Generation stage for ground truth chunks completed")
