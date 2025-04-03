import streamlit as st
import json
from pathlib import Path
import hydra
from omegaconf import DictConfig, OmegaConf
from data import get_hf_dpr_dataset
import sys
from hydra.core.hydra_config import HydraConfig
import traceback
import wandb  # NEW: Import wandb to retrieve run links
import re

sys.path.append("../dataset")
import parse  # type: ignore
from dataset import RAGDataset


def normalize_text(txt: str) -> str:
    """Normalize text for robust comparison."""
    txt = txt.strip().lower()
    txt = re.sub(r"\s+", " ", txt)  # Replace multiple spaces with one
    txt = re.sub(r"[^\w\s]", "", txt)  # Remove punctuation
    return txt


def load_run_data(run_dir: str):
    """Load retrieved chunks and generated answers for a run."""
    run_path = Path(run_dir)

    # Initialize with empty dictionaries
    retrieved_chunks = {}
    answers_ret = {}
    answers_gt = {}

    # Load files if they exist
    if (run_path / "retrieved_chunks.json").exists():
        retrieved_chunks = json.load((run_path / "retrieved_chunks.json").open())
    else:
        st.warning(f"File not found: {run_path}/retrieved_chunks.json")

    if (run_path / "generated_answers_ret.json").exists():
        answers_ret = json.load((run_path / "generated_answers_ret.json").open())
    else:
        st.warning(f"File not found: {run_path}/generated_answers_ret.json")

    if (run_path / "generated_answers_gt.json").exists():
        answers_gt = json.load((run_path / "generated_answers_gt.json").open())
    else:
        st.warning(f"File not found: {run_path}/generated_answers_gt.json")

    return retrieved_chunks, answers_ret, answers_gt


def get_wandb_run_url(cfg: DictConfig, run_name: str):
    """Get the WandB URL for a given run name."""
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
                return matched_run.url
            else:
                return None
        except Exception as e:
            return None
    return None


def load_dataset(cfg: DictConfig):
    """Load the dataset without caching."""
    if cfg.data.type == "hf_dpr":
        hf_dpr_dataset = get_hf_dpr_dataset(cfg)
        return RAGDataset.from_dpr_dataset(hf_dpr_dataset)
    elif cfg.data.type == "custom":
        custom_datasets = parse.get_datasets(samples_path=cfg.data.custom_samples_root)
        return RAGDataset.from_custom_datasets(custom_datasets)
    elif cfg.data.type == "custom_new":
        # Assume the path is in custom_samples_root for now
        # Load the 'full' split for the viewer
        return RAGDataset.from_new_json_format(
            path=cfg.data.custom_samples_root, split="full"
        )
    else:
        st.error(f"Invalid dataset type: {cfg.data.type}")
        return None


def display_single_run(cfg: DictConfig, dataset):
    """Display details for a single run."""
    # Store run data in session_state to persist between reruns
    if "single_run_name" not in st.session_state:
        st.session_state.single_run_name = ""
        st.session_state.single_run_data = None

    run_name = st.text_input("Enter run name:", value=st.session_state.single_run_name)

    # Check if run name changed
    if run_name != st.session_state.single_run_name:
        st.session_state.single_run_name = run_name
        st.session_state.single_run_data = None  # Reset data when run name changes

    if run_name:
        st.markdown("**Model:**")
        st.text(cfg.generation.llm_model[0])
        st.markdown("**Embedding Model:**")
        st.text(cfg.retrieval.embedding_model[0])
        st.markdown("**Retrieved Chunks:**")
        st.text(f"Top-k: {cfg.retrieval.get_top_chunks.top_k}")

        wandb_url = get_wandb_run_url(cfg, run_name)
        if wandb_url:
            st.markdown(f"[View W&B Run]({wandb_url})")

        # Initialize data for this run
        run_dir = str(Path(cfg.general.data_dir) / "runs" / run_name)
        if not Path(run_dir).exists():
            st.error(f"Run directory not found: {run_dir}")
            return False

        # Debug sample structure
        if len(dataset) > 0:
            st.session_state.sample_debug = {
                "type": str(type(dataset[0])),
                "dir": str(dir(dataset[0])),
            }

        # Load run data if it hasn't been loaded yet or if run name changed
        if st.session_state.single_run_data is None:
            retrieved_chunks, answers_ret, answers_gt = load_run_data(run_dir)
            st.session_state.single_run_data = {
                "retrieved_chunks": retrieved_chunks,
                "answers_ret": answers_ret,
                "answers_gt": answers_gt,
            }

        # Store data in session state for the viewer
        st.session_state.data = {
            "ds": dataset,
            "retrieved_chunks": st.session_state.single_run_data["retrieved_chunks"],
            "answers_ret": st.session_state.single_run_data["answers_ret"],
            "answers_gt": st.session_state.single_run_data["answers_gt"],
            "n_samples": len(dataset),
        }
        return True
    return False


def display_run_comparison(cfg: DictConfig, dataset):
    """Display comparison between two different runs."""
    # Store run data in session_state to persist between reruns
    if "comparison_run_names" not in st.session_state:
        st.session_state.comparison_run_names = {"run1": "", "run2": ""}
        st.session_state.comparison_run_data = {"run1": None, "run2": None}

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Run 1")
        run1_name = st.text_input(
            "Enter first run name:", value=st.session_state.comparison_run_names["run1"]
        )

    with col2:
        st.subheader("Run 2")
        run2_name = st.text_input(
            "Enter second run name:",
            value=st.session_state.comparison_run_names["run2"],
        )

    # Check if run names changed
    if run1_name != st.session_state.comparison_run_names["run1"]:
        st.session_state.comparison_run_names["run1"] = run1_name
        st.session_state.comparison_run_data["run1"] = (
            None  # Reset data when run name changes
        )

    if run2_name != st.session_state.comparison_run_names["run2"]:
        st.session_state.comparison_run_names["run2"] = run2_name
        st.session_state.comparison_run_data["run2"] = (
            None  # Reset data when run name changes
        )

    if not run1_name or not run2_name:
        st.info("Please enter both run names to compare.")
        return False

    if run1_name == run2_name:
        st.warning("Please enter different run names for comparison.")
        return False

    run1_dir = str(Path(cfg.general.data_dir) / "runs" / run1_name)
    run2_dir = str(Path(cfg.general.data_dir) / "runs" / run2_name)

    if not Path(run1_dir).exists():
        st.error(f"Run directory not found: {run1_dir}")
        return False

    if not Path(run2_dir).exists():
        st.error(f"Run directory not found: {run2_dir}")
        return False

    # Load run data for each run if it hasn't been loaded yet or if run name changed
    if st.session_state.comparison_run_data["run1"] is None:
        retrieved_chunks1, answers_ret1, answers_gt1 = load_run_data(run1_dir)
        st.session_state.comparison_run_data["run1"] = {
            "retrieved_chunks": retrieved_chunks1,
            "answers_ret": answers_ret1,
            "answers_gt": answers_gt1,
        }

    if st.session_state.comparison_run_data["run2"] is None:
        retrieved_chunks2, answers_ret2, answers_gt2 = load_run_data(run2_dir)
        st.session_state.comparison_run_data["run2"] = {
            "retrieved_chunks": retrieved_chunks2,
            "answers_ret": answers_ret2,
            "answers_gt": answers_gt2,
        }

    # Store data in session state for the comparison viewer
    st.session_state.comparison_data = {
        "ds": dataset,
        "run1": {
            "name": run1_name,
            "retrieved_chunks": st.session_state.comparison_run_data["run1"][
                "retrieved_chunks"
            ],
            "answers_ret": st.session_state.comparison_run_data["run1"]["answers_ret"],
            "answers_gt": st.session_state.comparison_run_data["run1"]["answers_gt"],
        },
        "run2": {
            "name": run2_name,
            "retrieved_chunks": st.session_state.comparison_run_data["run2"][
                "retrieved_chunks"
            ],
            "answers_ret": st.session_state.comparison_run_data["run2"]["answers_ret"],
            "answers_gt": st.session_state.comparison_run_data["run2"]["answers_gt"],
        },
        "n_samples": len(dataset),
    }

    # Display WandB links
    col1, col2 = st.columns(2)
    with col1:
        wandb_url1 = get_wandb_run_url(cfg, run1_name)
        if wandb_url1:
            st.markdown(f"[View Run 1 in W&B]({wandb_url1})")

    with col2:
        wandb_url2 = get_wandb_run_url(cfg, run2_name)
        if wandb_url2:
            st.markdown(f"[View Run 2 in W&B]({wandb_url2})")

    return True


def display_comparison_view():
    """Display comparison view for two runs."""
    # Access the comparison data from session state
    data = st.session_state.comparison_data
    ds = data["ds"]

    # Sample navigation
    sample_idx = st.number_input(
        "Select Sample:",
        min_value=0,
        max_value=data["n_samples"] - 1,
        step=1,
        key="comparison_sample_idx",
    )
    st.markdown(f"**Showing Sample {sample_idx+1} of {data['n_samples']}**")

    # Get current sample data
    sample = ds[sample_idx]
    query = sample.query
    gt_answer = sample.gt_answers[0] if sample.gt_answers else ""

    # Display query
    st.subheader("Query")
    st.write(query)

    # Display ground truth answer
    st.subheader("Ground Truth Answer")
    st.write(gt_answer)

    # Display comparison of retrieved answers
    st.markdown("## Retrieved Answers Comparison")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**Run 1: {data['run1']['name']}**")
        if query in data["run1"]["answers_ret"]:
            answer1 = data["run1"]["answers_ret"][query]
            if isinstance(answer1, dict) and "answer" in answer1:
                st.write(answer1["answer"])
                if "token_speed" in answer1:
                    st.markdown(f"*Token Speed: {answer1['token_speed']:.2f} tokens/s*")
            else:
                st.write(answer1)
        else:
            st.info("No retrieved answer available")

    with col2:
        st.markdown(f"**Run 2: {data['run2']['name']}**")
        if query in data["run2"]["answers_ret"]:
            answer2 = data["run2"]["answers_ret"][query]
            if isinstance(answer2, dict) and "answer" in answer2:
                st.write(answer2["answer"])
                if "token_speed" in answer2:
                    st.markdown(f"*Token Speed: {answer2['token_speed']:.2f} tokens/s*")
            else:
                st.write(answer2)
        else:
            st.info("No retrieved answer available")

    # Compare retrieved chunks
    st.markdown("## Retrieved Chunks Comparison")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**Run 1: {data['run1']['name']}**")
        ret_docs1 = data["run1"]["retrieved_chunks"].get(query, {}).get("documents", [])
        if ret_docs1:
            for i, chunk in enumerate(ret_docs1[:5]):  # Show top 5
                st.markdown(f"**Chunk {i+1}**")
                st.write(chunk)
                st.markdown("---")
        else:
            st.info("No retrieved chunks available")

    with col2:
        st.markdown(f"**Run 2: {data['run2']['name']}**")
        ret_docs2 = data["run2"]["retrieved_chunks"].get(query, {}).get("documents", [])
        if ret_docs2:
            for i, chunk in enumerate(ret_docs2[:5]):  # Show top 5
                st.markdown(f"**Chunk {i+1}**")
                st.write(chunk)
                st.markdown("---")
        else:
            st.info("No retrieved chunks available")

    # Compare with ground truth chunks
    st.markdown("## Ground Truth Chunks")
    gt_chunks = sample.pos_chunks
    for i, chunk in enumerate(gt_chunks):
        st.markdown(f"**Chunk {i+1}**")
        st.write(chunk)
        st.markdown("---")


def app(cfg: DictConfig):
    """Main Streamlit application logic"""
    # Make the layout use more screen space
    st.set_page_config(layout="wide")
    st.title("RAG Results Viewer")

    # Load dataset once at application startup
    dataset = load_dataset(cfg)

    # Create two columns - left for config, right for main content
    config_col, main_col = st.columns([1, 4])

    with config_col:
        st.subheader("Viewer Mode")
        view_mode = st.radio(
            "Select Mode:",
            ["Single Run", "Compare Runs"],
            index=0,
        )

        # Initialize data based on selected mode
        if view_mode == "Single Run":
            st.subheader("Experiment Config")
            has_data = display_single_run(cfg, dataset)
        else:
            st.subheader("Run Comparison")
            has_data = display_run_comparison(cfg, dataset)

    with main_col:
        if view_mode == "Single Run" and "data" in st.session_state:
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

            # Access sample properties
            query = sample.query
            gt_answer = sample.gt_answers[0] if sample.gt_answers else ""

            retrieved_chunks = st.session_state.data["retrieved_chunks"]
            answers_ret = st.session_state.data["answers_ret"]
            answers_gt = st.session_state.data["answers_gt"]

            # Ground truth chunks from the sample
            gt_chunks = sample.pos_chunks

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
                else:
                    st.info("No retrieved answer available")

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
                else:
                    st.info("No ground truth answer available")

            # Debug information
            with st.expander("Debug Information"):
                if "sample_debug" in st.session_state:
                    st.write("Sample type:", st.session_state.sample_debug["type"])
                    st.write("Sample attributes:", st.session_state.sample_debug["dir"])

                # Current sample inspection
                st.write("Current sample:", sample)

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
                if ret_docs_full:
                    # Display only the top 5 retrieved chunks for brevity
                    for i, chunk in enumerate(ret_docs_full[:5]):
                        st.markdown(f"**Chunk {i+1}**")
                        st.write(chunk)
                        st.markdown("---")
                else:
                    st.info("No retrieved chunks available")

            with chunk_cols[1]:
                st.subheader("Ground Truth Chunks")
                for i, chunk in enumerate(gt_chunks):
                    st.markdown(f"**Chunk {i+1}**")
                    st.write(chunk)
                    st.markdown("---")

        elif view_mode == "Compare Runs" and "comparison_data" in st.session_state:
            # Display comparison view
            display_comparison_view()


@hydra.main(config_path="conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig) -> None:
    # Initialize Hydra manually to avoid reinitialization issues
    try:
        hydra.initialize(config_path="conf", job_name="rag_viewer", version_base="1.3")
    except ValueError:
        # Already initialized, ignore
        pass

    try:
        app(cfg)
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
