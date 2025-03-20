import gradio as gr
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Add the necessary paths for imports
sys.path.append("../dataset")
from dataset import RAGDataset
import data


def load_agent_conversations(run_path: str) -> Dict:
    """Load agent conversations from a run directory"""
    json_path = Path(run_path) / "agent_conversations.json"

    if not json_path.exists():
        return {}

    try:
        with open(json_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_path}")
        return {}


def get_dataset(cfg) -> Optional[RAGDataset]:
    """Load the dataset without caching."""
    try:
        if cfg.data.type == "hf_dpr":
            hf_dpr_dataset = data.get_hf_dpr_dataset(cfg)
            return RAGDataset.from_dpr_dataset(hf_dpr_dataset)
        elif cfg.data.type == "custom":
            custom_datasets = data.parse.get_datasets(
                samples_path=cfg.data.custom_samples_root
            )
            return RAGDataset.from_custom_datasets(
                custom_datasets, split=cfg.data.custom_split
            )
    except Exception as e:
        print(f"Error loading dataset: {e}")
    return None


def find_gt_answer(dataset: RAGDataset, query: str) -> Optional[str]:
    """Find the ground truth answer for a query in the dataset"""
    if not dataset:
        return None

    # Simple exact match search
    for sample in dataset.samples:
        if query.strip().lower() == sample.query.strip().lower():
            return sample.gt_answers[0] if sample.gt_answers else None

    # If no exact match, do a fuzzy search based on token overlap
    query_tokens = set(query.lower().split())
    best_match = None
    best_overlap = 0

    for sample in dataset.samples:
        sample_tokens = set(sample.query.lower().split())
        overlap = len(query_tokens.intersection(sample_tokens))
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = sample

    # Only return if we have a reasonably good match
    if best_match and best_overlap > min(3, len(query_tokens) // 2):
        return best_match.gt_answers[0] if best_match.gt_answers else None

    return None


def display_tool_calls(tool_calls):
    """Format tool calls for display using collapsible HTML sections"""
    if not tool_calls:
        return ""

    result = []
    for i, tool_call in enumerate(tool_calls):
        if isinstance(tool_call, dict):
            tool_type = tool_call.get("type", "unknown")
            tool_name = (
                tool_call.get("function", {}).get("name", "unknown_function")
                if "function" in tool_call
                else "unknown_tool"
            )
            tool_args = (
                tool_call.get("function", {}).get("arguments", {})
                if "function" in tool_call
                else {}
            )

            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except:
                    pass

            # Create a collapsible section for each tool call
            tool_id = f"tool-{i}-{hash(str(tool_call))}"
            result.append(
                f'<details class="tool-call"><summary><strong>Tool {i+1}: {tool_name}</strong> ({tool_type})</summary>'
            )
            result.append('<div class="tool-content">')
            result.append("<strong>Arguments:</strong>")
            result.append('<pre class="json-content">')
            result.append(json.dumps(tool_args, indent=2, ensure_ascii=False))
            result.append("</pre>")

            # Add tool result if available in a nested collapsible section
            if "name" in tool_call and "content" in tool_call:
                result.append(
                    f'<details class="tool-result"><summary><strong>Result</strong></summary>'
                )
                result.append('<div class="result-content">')
                result.append('<pre class="json-content">')
                try:
                    tool_content = (
                        json.loads(tool_call["content"])
                        if isinstance(tool_call["content"], str)
                        else tool_call["content"]
                    )
                    result.append(
                        json.dumps(tool_content, indent=2, ensure_ascii=False)
                    )
                except:
                    result.append(str(tool_call["content"]))
                result.append("</pre>")
                result.append("</div>")
                result.append("</details>")

            result.append("</div>")
            result.append("</details>")

    return "\n".join(result)


def display_conversation_history(conversation_history):
    """Format conversation history for display with improved HTML formatting"""
    if not conversation_history:
        return ""

    result = []
    result.append('<div class="conversation-container">')

    for message in conversation_history:
        role = message.get("role", "unknown")
        content = message.get("content", "")

        if role == "system":
            continue  # Skip system messages

        # Add message with appropriate styling
        role_class = role.lower()
        result.append(f'<div class="message {role_class}">')
        result.append(f'<div class="role"><strong>{role.capitalize()}:</strong></div>')

        # For tool messages, don't display content directly, only in the toggle
        if role == "tool":
            result.append(
                '<div class="content"><em>(Click "Tool Response" below to view details)</em></div>'
            )
        else:
            result.append(
                f'<div class="content">{content if content else "<em>(No content)</em>"}</div>'
            )

        # Display tool calls if present
        tool_calls = message.get("tool_calls", [])
        if tool_calls:
            tool_calls_html = display_tool_calls(tool_calls)
            if tool_calls_html:
                result.append('<div class="tool-calls">')
                result.append(tool_calls_html)
                result.append("</div>")

        # If this is a tool response, format it nicely
        if role == "tool":
            tool_call_id = message.get("tool_call_id", "")
            tool_name = message.get("name", "")

            if tool_name:
                result.append(
                    f'<details class="tool-response"><summary><strong>Tool Response</strong> ({tool_name})</summary>'
                )
                result.append('<div class="tool-response-content">')

                # Try to format tool content as JSON if possible
                tool_content = message.get("content", "")
                try:
                    content_json = (
                        json.loads(tool_content)
                        if isinstance(tool_content, str)
                        else tool_content
                    )
                    result.append('<pre class="json-content">')
                    result.append(
                        json.dumps(content_json, indent=2, ensure_ascii=False)
                    )
                    result.append("</pre>")
                except:
                    # If not JSON, just display as plain text
                    result.append('<pre class="plain-text">')
                    result.append(str(tool_content))
                    result.append("</pre>")

                result.append("</div>")
                result.append("</details>")

        result.append("</div>")  # Close message div

    result.append("</div>")  # Close conversation container

    # Add some CSS styling for the conversation display
    result.append(
        """
    <style>
    .conversation-container {
      display: flex;
      flex-direction: column;
      gap: 10px;
      font-family: system-ui, -apple-system, sans-serif;
      background-color: #f5f5f5;
      padding: 15px;
      border-radius: 8px;
    }
    .message {
      padding: 10px;
      border-radius: 8px;
      border-left: 3px solid #ccc;
      background-color: white;
      margin-bottom: 8px;
    }
    .user {
      background-color: rgba(173, 216, 230, 0.2);
      border-left-color: #4a90e2;
    }
    .assistant {
      background-color: white;
      border-left-color: #50C878;
    }
    .tool {
      background-color: rgba(250, 250, 210, 0.2);
      border-left-color: #E6D333;
    }
    .role {
      font-weight: bold;
      margin-bottom: 5px;
    }
    .tool-calls, .tool-response {
      margin-top: 8px;
    }
    details {
      margin: 5px 0;
      border-radius: 4px;
      overflow: hidden;
    }
    details summary {
      padding: 6px 10px;
      background-color: #f0f0f0;
      cursor: pointer;
      user-select: none;
    }
    details[open] summary {
      border-bottom: 1px solid #ddd;
    }
    .tool-content, .tool-response-content, .result-content {
      padding: 10px;
      background-color: #f9f9f9;
      border-radius: 0 0 4px 4px;
    }
    pre.json-content, pre.plain-text {
      background-color: #f5f5f5;
      padding: 10px;
      border-radius: 4px;
      overflow-x: auto;
      margin: 5px 0;
      font-family: monospace;
      font-size: 13px;
    }
    </style>
    """
    )

    return "\n".join(result)


def format_conversation_card(
    query,
    gt_answer,
    run1_name,
    run1_answer,
    run2_name=None,
    run2_answer=None,
    run1_history=None,
    run2_history=None,
    run1_metrics=None,
    run2_metrics=None,
    category=None,
):
    """Create a formatted HTML card for a single conversation comparison"""

    # Use "Ground truth not found" when ground truth is not available
    gt_display = gt_answer if gt_answer else "Ground truth not found"

    # Format metrics section if available
    def format_metrics(metrics, run_name):
        if not metrics:
            return ""

        metrics_html = f"""
        <div style="background: #f8f9fa; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
            <h4 style="margin-top: 0;">{run_name} Metrics:</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px;">
        """

        # Group metrics by category
        metric_categories = {
            "BERTScore": ["bertscore_precision", "bertscore_recall", "bertscore_f1"],
            "ROUGE": ["rouge1", "rouge2", "rougeL", "rougeLsum"],
            "SacreBLEU": [
                "sacrebleu_score",
                "sacrebleu_precision1",
                "sacrebleu_precision2",
                "sacrebleu_precision3",
                "sacrebleu_bp",
            ],
            "SemScore": ["semscore_paper", "semscore_multilingual"],
            "Other": ["geval_correctness"],
        }

        for category, metric_keys in metric_categories.items():
            metrics_html += f'<div style="background: white; padding: 8px; border-radius: 4px;"><strong>{category}:</strong><br>'
            for key in metric_keys:
                if key in metrics:
                    value = metrics[key]
                    # Format the metric name to be more readable
                    display_name = key.replace("_", " ").title()
                    metrics_html += f"{display_name}: {value:.4f}<br>"
            metrics_html += "</div>"

        metrics_html += "</div></div>"
        return metrics_html

    # Single run mode
    if run2_name is None or run2_answer is None:
        return f"""
        <div style="border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; border-radius: 5px; background-color: white;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <h3 style="margin-top: 0;">Query: {query}</h3>
                <span style="background: #e9ecef; padding: 4px 8px; border-radius: 4px; font-size: 0.9em;">Category: {category}</span>
            </div>
            <div style="background: #f5f5f5; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
                <h4 style="margin-top: 0;">Ground Truth:</h4>
                <p>{gt_display}</p>
            </div>
            
            <div style="padding: 10px; background: #f0f8ff; border-radius: 5px; margin-bottom: 15px;">
                <h4 style="margin-top: 0;">Run: {run1_name}</h4>
                <p>{run1_answer}</p>
            </div>
            
            {format_metrics(run1_metrics, run1_name)}
            
            <div style="padding: 10px; max-height: 600px; overflow-y: auto; border-radius: 5px;">
                <h4 style="margin-top: 0;">Conversation:</h4>
                <div>{run1_history}</div>
            </div>
        </div>
        """

    # Two-run comparison mode
    return f"""
    <div style="border: 1px solid #ddd; padding: 15px; margin-bottom: 20px; border-radius: 5px; background-color: white;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
            <h3 style="margin-top: 0;">Query: {query}</h3>
            <span style="background: #e9ecef; padding: 4px 8px; border-radius: 4px; font-size: 0.9em;">Category: {category}</span>
        </div>
        <div style="background: #f5f5f5; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
            <h4 style="margin-top: 0;">Ground Truth:</h4>
            <p>{gt_display}</p>
        </div>
        
        <div style="display: flex; margin-bottom: 15px;">
            <div style="flex: 1; padding: 10px; margin-right: 5px; background: #f0f8ff; border-radius: 5px;">
                <h4 style="margin-top: 0;">Run 1 ({run1_name}) Answer:</h4>
                <p>{run1_answer}</p>
            </div>
            <div style="flex: 1; padding: 10px; margin-left: 5px; background: #fff0f5; border-radius: 5px;">
                <h4 style="margin-top: 0;">Run 2 ({run2_name}) Answer:</h4>
                <p>{run2_answer}</p>
            </div>
        </div>
        
        <div style="display: flex; margin-bottom: 15px;">
            <div style="flex: 1; margin-right: 5px;">
                {format_metrics(run1_metrics, run1_name)}
            </div>
            <div style="flex: 1; margin-left: 5px;">
                {format_metrics(run2_metrics, run2_name)}
            </div>
        </div>
        
        <div style="display: flex;">
            <div style="flex: 1; padding: 10px; margin-right: 5px; max-height: 600px; overflow-y: auto; border-radius: 5px;">
                <h4 style="margin-top: 0;">Run 1 Conversation:</h4>
                <div>{run1_history}</div>
            </div>
            <div style="flex: 1; padding: 10px; margin-left: 5px; max-height: 600px; overflow-y: auto; border-radius: 5px;">
                <h4 style="margin-top: 0;">Run 2 Conversation:</h4>
                <div>{run2_history}</div>
            </div>
        </div>
    </div>
    """


def agent_viewer_ui():
    """Create the Gradio UI for comparing agent conversations"""

    def load_runs(run1_name: str, run2_name: str = None, data_dir: str = "data"):
        """Load runs and return all the data needed for display"""
        # Use empty string or None handling for run2_name
        run2_name = run2_name if run2_name and run2_name.strip() else None

        data_path = Path(data_dir)
        run1_path = data_path / "runs" / run1_name

        # Run2 path is optional now
        run2_path = data_path / "runs" / run2_name if run2_name else None

        # Load configurations and initialize dataset
        dataset = None
        try:
            import hydra
            from omegaconf import DictConfig, OmegaConf

            # Try to clear Hydra in a way that's compatible with different versions
            try:
                # For newer Hydra versions
                hydra.core.global_hydra.GlobalHydra.instance().clear()
            except:
                try:
                    # Alternative method
                    from hydra.core.config_store import ConfigStore

                    ConfigStore.instance().clear()
                except:
                    # Just try to initialize directly and catch any errors
                    pass

            # Initialize with version_base to avoid warnings
            hydra.initialize(config_path="conf", version_base=None)
            cfg = hydra.compose(config_name="config")
            dataset = get_dataset(cfg)
        except Exception as e:
            print(f"Error loading config or dataset: {e}")

        # Load agent conversations
        run1_conversations = load_agent_conversations(run1_path)
        run2_conversations = load_agent_conversations(run2_path) if run2_name else {}

        if not run1_conversations:
            return {
                "success": False,
                "message": f"Could not load agent conversations for run '{run1_name}'. Please check the run name.",
            }

        # If only one run is specified, use all its queries
        if not run2_name:
            shared_queries = list(run1_conversations.keys())
        else:
            # Get shared queries between the two runs
            shared_queries = set(run1_conversations.keys()).intersection(
                set(run2_conversations.keys())
            )

            if not shared_queries:
                return {
                    "success": False,
                    "message": "No matching queries found between the two runs.",
                }

        # Create a map of query to category for faster lookups
        query_to_category = {}
        if dataset:
            for sample in dataset.samples:
                query_to_category[sample.query] = sample.category

        # Get all unique categories
        all_categories = set()
        if dataset:
            all_categories = set(dataset.unique_categories())

        # Add "Unknown" category for queries not found in the dataset
        all_categories.add("Unknown")

        # Prepare data for all conversations
        conversations = []
        for query in shared_queries:
            run1_answer = (
                run1_conversations[query].get("content", "No answer")
                if query in run1_conversations
                else "No answer"
            )

            run2_answer = (
                run2_conversations[query].get("content", "No answer")
                if query in run2_conversations and run2_name
                else None
            )

            # Get ground truth answer
            gt_answer = find_gt_answer(dataset, query)

            # Format the conversation histories
            run1_history = display_conversation_history(
                run1_conversations[query].get("conversation_history", [])
            )

            run2_history = (
                display_conversation_history(
                    run2_conversations.get(query, {}).get("conversation_history", [])
                )
                if run2_name
                else None
            )

            # Get metrics for each run
            run1_metrics = (
                run1_conversations[query].get("metrics", {})
                if query in run1_conversations
                else {}
            )
            run2_metrics = (
                run2_conversations[query].get("metrics", {})
                if query in run2_conversations and run2_name
                else {}
            )

            # Get category for this query
            category = query_to_category.get(query, "Unknown")

            conversations.append(
                {
                    "query": query,
                    "gt_answer": gt_answer if gt_answer else None,
                    "run1_answer": run1_answer,
                    "run2_answer": run2_answer,
                    "run1_history": run1_history,
                    "run2_history": run2_history,
                    "run1_metrics": run1_metrics,
                    "run2_metrics": run2_metrics,
                    "category": category,
                }
            )

        return {
            "success": True,
            "conversations": conversations,
            "run1_name": run1_name,
            "run2_name": run2_name,
            "single_run_mode": run2_name is None,
            "categories": sorted(list(all_categories)),
        }

    def update_ui(
        load_result,
        search_query="",
        current_index=0,
        selected_category="All Categories",
    ):
        """Update the UI based on loaded data and current index"""
        if not load_result or not load_result.get("success", False):
            message = (
                load_result.get("message", "Failed to load data")
                if load_result
                else "No data loaded"
            )
            return (
                gr.HTML(message),
                gr.Slider(minimum=0, maximum=0, value=0),
                gr.Textbox(value="No results"),
                0,
                0,
                "",
                gr.Dropdown(choices=["All Categories"]),
            )

        conversations = load_result.get("conversations", [])
        run1_name = load_result.get("run1_name", "Run 1")
        run2_name = load_result.get("run2_name", "Run 2")
        single_run_mode = load_result.get("single_run_mode", False)
        categories = load_result.get("categories", ["All Categories"])

        # Filter conversations based on search query and category
        filtered_conversations = []
        for conv in conversations:
            # Check category filter
            if (
                selected_category != "All Categories"
                and conv["category"] != selected_category
            ):
                continue

            # Check search query
            if search_query:
                search_query = search_query.lower()
                if single_run_mode:
                    if (
                        search_query in conv["query"].lower()
                        or search_query in conv["run1_answer"].lower()
                    ):
                        filtered_conversations.append(conv)
                else:
                    if (
                        search_query in conv["query"].lower()
                        or search_query in conv["run1_answer"].lower()
                        or (
                            conv["run2_answer"]
                            and search_query in conv["run2_answer"].lower()
                        )
                    ):
                        filtered_conversations.append(conv)
            else:
                filtered_conversations.append(conv)

        if not filtered_conversations:
            return (
                gr.HTML("<p>No conversations match your search criteria.</p>"),
                gr.Slider(minimum=0, maximum=0, value=0),
                gr.Textbox(value="No results"),
                0,
                0,
                "",
                gr.Dropdown(choices=["All Categories"] + categories),
            )

        # Special case for single result to avoid math domain error
        if len(filtered_conversations) == 1:
            slider_max = 0
        else:
            slider_max = len(filtered_conversations) - 1

        # Ensure current_index is within bounds
        current_index = max(0, min(current_index, slider_max))

        # Get the current conversation
        current_conv = filtered_conversations[current_index]

        # Format the HTML display
        html_content = format_conversation_card(
            current_conv["query"],
            current_conv["gt_answer"],
            run1_name,
            current_conv["run1_answer"],
            run2_name,
            current_conv["run2_answer"],
            current_conv["run1_history"],
            current_conv["run2_history"],
            current_conv["run1_metrics"],
            current_conv["run2_metrics"],
            current_conv["category"],
        )

        # Navigation text
        nav_text = (
            f"Showing conversation {current_index + 1} of {len(filtered_conversations)}"
        )

        return (
            gr.HTML(html_content),
            gr.Slider(
                value=current_index,
                minimum=0,
                maximum=slider_max,
            ),
            gr.Textbox(value=nav_text),
            current_index,
            len(filtered_conversations),
            current_conv["query"],
            gr.Dropdown(choices=["All Categories"] + categories),
        )

    def go_to_next(current_idx, total):
        return min(current_idx + 1, total - 1)

    def go_to_prev(current_idx):
        return max(current_idx - 1, 0)

    def clear_search(loaded_result):
        """Clear the search and show all conversations"""
        return "", update_ui(loaded_result, "", 0, "All Categories")

    with gr.Blocks(title="Agent Conversation Viewer") as demo:
        gr.Markdown("# Agent Conversation Viewer")
        gr.Markdown(
            "View agent conversations from one run or compare conversations from two different runs. Each conversation is displayed on its own page for easier reading."
        )

        # Input area for configuration
        with gr.Row():
            run1_name = gr.Textbox(
                label="Run 1 Name (Required)", placeholder="e.g. demo-1234"
            )
            run2_name = gr.Textbox(
                label="Run 2 Name (Optional for comparison)",
                placeholder="Leave empty to view only one run",
            )

        with gr.Row():
            data_dir = gr.Textbox(
                label="Data Directory",
                value="data",
                placeholder="Path to data directory",
            )
            load_button = gr.Button("Load Run(s)")

        # Store loaded data
        loaded_data = gr.State()
        current_idx = gr.State(0)
        total_items = gr.State(0)
        current_query = gr.State("")

        # Search and filter functionality
        with gr.Row():
            search_input = gr.Textbox(
                label="Search by query text or answers",
                placeholder="Enter search terms...",
                interactive=True,
            )
            category_filter = gr.Dropdown(
                label="Filter by Category",
                choices=["All Categories"],
                value="All Categories",
                interactive=True,
            )
            search_button = gr.Button("Search")
            clear_button = gr.Button("Clear Search")

        # Navigation
        with gr.Row():
            prev_button = gr.Button("Previous")
            idx_slider = gr.Slider(
                minimum=0, maximum=0, step=1, label="Conversation Index"
            )
            next_button = gr.Button("Next")

        nav_text = gr.Textbox(label="Navigation", interactive=False)

        # Display area
        conversation_display = gr.HTML()

        # Button event handlers
        load_button.click(
            fn=load_runs, inputs=[run1_name, run2_name, data_dir], outputs=[loaded_data]
        ).then(
            fn=update_ui,
            inputs=[loaded_data, search_input, current_idx, category_filter],
            outputs=[
                conversation_display,
                idx_slider,
                nav_text,
                current_idx,
                total_items,
                current_query,
                category_filter,
            ],
        )

        # Search functionality
        search_button.click(
            fn=lambda data, query, cat: update_ui(data, query, 0, cat),
            inputs=[loaded_data, search_input, category_filter],
            outputs=[
                conversation_display,
                idx_slider,
                nav_text,
                current_idx,
                total_items,
                current_query,
                category_filter,
            ],
        )

        # Also trigger search on Enter key in the search box
        search_input.submit(
            fn=lambda data, query, cat: update_ui(data, query, 0, cat),
            inputs=[loaded_data, search_input, category_filter],
            outputs=[
                conversation_display,
                idx_slider,
                nav_text,
                current_idx,
                total_items,
                current_query,
                category_filter,
            ],
        )

        # Category filter change
        category_filter.change(
            fn=lambda data, query, cat: update_ui(data, query, 0, cat),
            inputs=[loaded_data, search_input, category_filter],
            outputs=[
                conversation_display,
                idx_slider,
                nav_text,
                current_idx,
                total_items,
                current_query,
                category_filter,
            ],
        )

        # Clear search button
        clear_button.click(
            fn=clear_search,
            inputs=[loaded_data],
            outputs=[
                search_input,
                conversation_display,
                idx_slider,
                nav_text,
                current_idx,
                total_items,
                current_query,
                category_filter,
            ],
        )

        # Navigation events
        prev_button.click(
            fn=go_to_prev, inputs=[current_idx], outputs=[current_idx]
        ).then(
            fn=update_ui,
            inputs=[loaded_data, search_input, current_idx, category_filter],
            outputs=[
                conversation_display,
                idx_slider,
                nav_text,
                current_idx,
                total_items,
                current_query,
                category_filter,
            ],
        )

        next_button.click(
            fn=go_to_next, inputs=[current_idx, total_items], outputs=[current_idx]
        ).then(
            fn=update_ui,
            inputs=[loaded_data, search_input, current_idx, category_filter],
            outputs=[
                conversation_display,
                idx_slider,
                nav_text,
                current_idx,
                total_items,
                current_query,
                category_filter,
            ],
        )

        idx_slider.change(
            fn=lambda idx: idx, inputs=[idx_slider], outputs=[current_idx]
        ).then(
            fn=update_ui,
            inputs=[loaded_data, search_input, current_idx, category_filter],
            outputs=[
                conversation_display,
                idx_slider,
                nav_text,
                current_idx,
                total_items,
                current_query,
                category_filter,
            ],
        )

    return demo


if __name__ == "__main__":
    demo = agent_viewer_ui()
    demo.launch(share=False)
