import streamlit as st
import json
from pathlib import Path
import hydra
from omegaconf import DictConfig, OmegaConf
from data import init_dataset
import sys
from hydra.core.hydra_config import HydraConfig
import traceback
import wandb  # NEW: Import wandb to retrieve run links
import re


def normalize_text(txt: str) -> str:
    """Normalize text for robust comparison."""
    txt = txt.strip().lower()
    txt = re.sub(r"\s+", " ", txt)  # Replace multiple spaces with one
    txt = re.sub(r"[^\w\s]", "", txt)  # Remove punctuation
    return txt


@st.cache_data
def load_run_data(run_dir: str):
    """Load retrieved chunks and generated answers for a run."""
    run_path = Path(run_dir)
    retrieved_chunks = json.load((run_path / "retrieved_chunks.json").open())
    answers_ret = json.load((run_path / "generated_answers_ret.json").open())
    answers_gt = json.load((run_path / "generated_answers_gt.json").open())
    return retrieved_chunks, answers_ret, answers_gt


@st.cache_data
def init_cached_dataset(_cfg: DictConfig):
    """Cached version of dataset initialization.
    Leading underscore tells Streamlit not to hash the config argument.
    """
    return init_dataset(_cfg)


def app(cfg: DictConfig):
    """Main Streamlit application logic"""
    # Make the layout use more screen space
    st.set_page_config(layout="wide")
    st.title("RAG Results Viewer")

    # Create two columns - left for config, right for main content
    config_col, main_col = st.columns([1, 4])

    with config_col:
        st.subheader("Experiment Config")
        run_name = st.text_input("Enter run name:", value="")

        if run_name:
            st.markdown("**Model:**")
            st.text(cfg.generation.get_answers.model)
            st.markdown("**Embedding Model:**")
            st.text(cfg.data.fill_db.embedding_model)
            st.markdown("**Retrieved Chunks:**")
            st.text(f"Top-k: {cfg.retrieval.get_top_chunks.top_k}")

            if hasattr(cfg, "wandb") and hasattr(cfg.wandb, "entity"):
                try:
                    api_obj = wandb.Api()
                    # Get all runs for the specified entity/project
                    runs = api_obj.runs(f"{cfg.wandb.entity}/{cfg.wandb.project}")
                    matched_run = None
                    for run in runs:
                        if run.name == run_name:
                            matched_run = run
                            break
                    if matched_run:
                        wandb_url = matched_run.url
                        st.markdown(f"[View W&B Run]({wandb_url})")
                    else:
                        st.info("Could not find a WandB run with the given name.")
                except Exception as e:
                    st.info("Error retrieving WandB run URL from WandB API.")

    with main_col:
        if run_name:
            try:
                # Load data only once and cache in session state
                if "data" not in st.session_state:
                    run_dir = str(Path(cfg.general.data_dir) / "runs" / run_name)
                    if not Path(run_dir).exists():
                        st.error(f"Run directory not found: {run_dir}")
                        return

                    ds = init_cached_dataset(cfg)
                    retrieved_chunks, answers_ret, answers_gt = load_run_data(run_dir)
                    st.session_state.data = {
                        "ds": ds,
                        "retrieved_chunks": retrieved_chunks,
                        "answers_ret": answers_ret,
                        "answers_gt": answers_gt,
                        "n_samples": len(ds),
                    }

                # Initialize sample index if needed
                if "sample_idx" not in st.session_state:
                    st.session_state.sample_idx = 0

                # Unified sample index navigation widget with visual indicator at the top
                sample_idx = st.number_input(
                    "Select Sample:",
                    min_value=0,
                    max_value=st.session_state.data["n_samples"] - 1,
                    step=1,
                    key="sample_idx",
                )
                st.markdown(
                    f"**Showing Sample {sample_idx+1} of {st.session_state.data['n_samples']}**"
                )

                # Get current sample data using the selected sample_idx
                ds = st.session_state.data["ds"]
                sample = ds[sample_idx]
                query = sample["question"]
                gt_answer = sample["answers"][0]
                retrieved_chunks = st.session_state.data["retrieved_chunks"]
                answers_ret = st.session_state.data["answers_ret"]
                answers_gt = st.session_state.data["answers_gt"]

                # Handle ground truth chunks
                gt_chunks = []
                if "positive_ctxs" in sample:
                    if (
                        isinstance(sample["positive_ctxs"], dict)
                        and "text" in sample["positive_ctxs"]
                    ):
                        if isinstance(sample["positive_ctxs"]["text"], list):
                            gt_chunks = sample["positive_ctxs"]["text"]
                        else:
                            gt_chunks = [sample["positive_ctxs"]["text"]]

                # Display content
                st.subheader("Query")
                st.write(query)

                answer_cols = st.columns(3)
                with answer_cols[0]:
                    st.subheader("Ground Truth Answer")
                    st.write(gt_answer)

                with answer_cols[1]:
                    st.subheader("Generated (Retrieved)")
                    if query in answers_ret:
                        st.write(answers_ret[query])
                        if (
                            isinstance(answers_ret[query], dict)
                            and "token_speed" in answers_ret[query]
                        ):
                            st.markdown(
                                f"*Token Speed: {answers_ret[query]['token_speed']:.2f} tokens/s*"
                            )

                with answer_cols[2]:
                    st.subheader("Generated (GT)")
                    if query in answers_gt:
                        st.write(answers_gt[query])
                        if (
                            isinstance(answers_gt[query], dict)
                            and "token_speed" in answers_gt[query]
                        ):
                            st.markdown(
                                f"*Token Speed: {answers_gt[query]['token_speed']:.2f} tokens/s*"
                            )

                st.markdown("---")
                chunk_cols = st.columns(2)
                with chunk_cols[0]:
                    # Check if all GT chunks are present in the full list of retrieved documents
                    ret_docs_full = retrieved_chunks.get(query, {}).get("documents", [])
                    if gt_chunks:
                        all_found = all(
                            any(
                                normalize_text(ret_doc) == normalize_text(gt_chunk)
                                for ret_doc in ret_docs_full
                            )
                            for gt_chunk in gt_chunks
                        )
                    else:
                        all_found = False
                    header_text = "Retrieved Chunks"
                    if gt_chunks:
                        header_text += " ✅" if all_found else " ❌"
                    st.subheader(header_text)
                    # Display only the top 5 retrieved chunks for brevity
                    for i, chunk in enumerate(ret_docs_full[:5]):
                        st.markdown(f"**Chunk {i+1}**")
                        st.write(chunk)
                        st.markdown("---")

                with chunk_cols[1]:
                    st.subheader("Ground Truth Chunks")
                    for i, chunk in enumerate(gt_chunks):
                        st.markdown(f"**Chunk {i+1}**")
                        st.write(chunk)
                        st.markdown("---")

            except Exception as e:
                st.error(f"Error loading data: {str(e)}")
                st.error(f"Traceback:\n```\n{traceback.format_exc()}\n```")


@hydra.main(config_path="conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig) -> None:
    # Initialize Hydra manually to avoid reinitialization issues
    if not HydraConfig.initialized():
        hydra.initialize(version_base="1.3", config_path="conf")
    app(cfg)


if __name__ == "__main__":
    main()
