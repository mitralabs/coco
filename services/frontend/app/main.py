import gradio as gr
import pandas as pd
import numpy as np
import datetime
from datetime import date
import json

from coco import CocoClient

# See Gradio Docs for reference: https://www.gradio.app/docs

# Can be removed, only until functions are in SDK
from ollama import AsyncClient
from openai import AsyncOpenAI

openai = AsyncOpenAI(
    base_url="https://openai.inference.de-txl.ionos.com/v1",
)
ollama = AsyncClient(
    host="http://host.docker.internal:11434",
)

theme = gr.themes.Ocean(
    primary_hue="sky",
    neutral_hue="neutral",
    spacing_size="sm",
)

cc = CocoClient(
    chunking_base="http://chunking:8000",
    db_api_base="http://db-api:8000",
    transcription_base="http://host.docker.internal:8000",
    # ollama_base="https://jetson-ollama.mitra-labs.ai",
    ollama_base="http://host.docker.internal:11434",
    openai_base="https://openai.inference.de-txl.ionos.com/v1",
    embedding_api="ollama",
    llm_api="openai",
    api_key="test",
)


system_message_default = "Du bist coco.\n\nDu hilfst dem User bestmöglich.\n\nDu antwortest präzise und kommunizierst auf Deutsch."

CONTEXT_FORMAT = """
    Der nachfolgende Inhalt könnte hilfreich sein, um die Frage zu beantworten:
    
    -----
    {context}
    -----
"""


def user(user_message, history):
    if history is None:
        history = []
    history.append({"role": "user", "content": user_message})
    # Return empty string for input_message to clear the textbox
    # But the message is already stored in current_user_message state
    return "", history


def retry(history):
    # print(user_message)
    history.pop()
    return history


def clear(input_message):
    return ""


def update_available_models(llmapi: str):
    cc.lm.llm_api = llmapi
    available_models = get_available_models()

    return gr.Dropdown(
        choices=available_models,
        interactive=True,
    )


def get_available_models():
    available_models = cc.lm.list_llm_models()
    embedding_models_ollama = [
        "nomic-embed-text:latest",
        "mxbai-embed-large:latest",
        "snowflake-arctic-embed:latest",
        "bge-m3:latest",
        "all-minilm:latest",
        "bge-large:latest",
        "snowflake-arctic-embed2:latest",
        "paraphrase-multilingual:latest",
        "granite-embedding:latest",
    ]
    non_llms_ionos = [
        "meta-llama/CodeLlama-13b-Instruct-hf",
        "black-forest-labs/FLUX.1-schnell",
        "BAAI/bge-large-en-v1.5",
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "BAAI/bge-m3",
        "stabilityai/stable-diffusion-xl-base-1.0",
    ]
    # combine embedding models and non-llms
    blacklisted_models = embedding_models_ollama + non_llms_ionos

    available_models = [
        model for model in available_models if model not in blacklisted_models
    ]

    if not available_models:
        available_models = [
            "meta-llama/Llama-3.3-70B-Instruct"
        ]  # Default fallback model for Openai

    if cc.lm.llm_api == "openai":
        try:
            available_models = [
                (model.split("/")[-1], model) for model in available_models
            ]
        except:
            pass

    # print(available_models)
    return available_models


async def add_context(
    user_message: str = "",
    history: list = [],
    messages: list = [],
    start_date=None,
    end_date=None,
):
    # Convert DateTime component output to date objects
    start_date_obj = None
    end_date_obj = None

    if start_date:
        # Handle different possible formats from gr.DateTime
        if isinstance(start_date, datetime.datetime):
            start_date_obj = start_date.date()
        elif isinstance(start_date, date):
            start_date_obj = start_date
        elif isinstance(start_date, str) and start_date.strip():
            try:
                start_date_obj = datetime.datetime.fromisoformat(start_date).date()
            except ValueError:
                print(f"Invalid start date format: {start_date}")

    if end_date:
        # Handle different possible formats from gr.DateTime
        if isinstance(end_date, datetime.datetime):
            end_date_obj = end_date.date()
        elif isinstance(end_date, date):
            end_date_obj = end_date
        elif isinstance(end_date, str) and end_date.strip():
            try:
                end_date_obj = datetime.datetime.fromisoformat(end_date).date()
            except ValueError:
                print(f"Invalid end date format: {end_date}")

    # Get RAG context with date filters
    contexts = await cc.rag.async_retrieve_chunks(
        [user_message], 5, start_date=start_date_obj, end_date=end_date_obj
    )
    context_chunks = contexts[0][1]
    rag_context = CONTEXT_FORMAT.format(context="\n-----\n".join(context_chunks))
    # Add RAG context -> Note the "tool" role is ollama specific and will be useful in the future. See: https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-chat-completion
    messages.append(
        {
            "role": "user",
            "content": rag_context,
        }
    )
    history.append(
        gr.ChatMessage(
            role="user",
            content=f"```{rag_context}```",  # Markdown code block, to prevent the context from being displayed formatted
            metadata={"title": "RAG Context", "status": "done"},
        )
    )
    return messages, history


async def call_rag(
    user_message,
    history,
    selected_model,
    system_message,
    start_date=None,
    end_date=None,
):
    try:
        # Get RAG context with date filters
        contexts = await cc.rag.async_retrieve_chunks(
            [user_message], 5, start_date=start_date, end_date=end_date
        )
        context_chunks = contexts[0][1]
        rag_context = CONTEXT_FORMAT.format(context="\n-----\n".join(context_chunks))

        messages = []
        # Add system message
        if system_message == "":
            system_message = system_message_default
        messages.append({"role": "system", "content": system_message})

        # Add previous messages
        for element in history:
            messages.append({"role": element["role"], "content": element["content"]})

        if include_context == "Yes":
            messages, history = await add_context(user_message, history, messages)
        else:
            messages.append({"role": "user", "content": user_message})

        responses, tok_ss = await cc.lm.async_chat_multiple(
            messages_list=[messages],
            model=selected_model,
            batch_size=20,
            limit_parallel=10,
            show_progress=True,
        )
        reponse, tok_s = responses[0], tok_ss[0]
        history.append(gr.ChatMessage(role="assistant", content=reponse))
        yield history

    except Exception as e:
        history.append({"role": "assistant", "content": f"Error: {str(e)}"})
        yield history
        raise e


async def call_rag_stream(
    user_message,
    history,
    selected_model,
    system_message,
    start_date,
    end_date,
    include_context,
):
    messages = []
    # Add system message
    if system_message == "":
        system_message = system_message_default
    messages.append({"role": "system", "content": system_message})

    # Add previous messages
    for element in history:
        messages.append({"role": element["role"], "content": element["content"]})

    if include_context == "Yes":
        # Explicitly get the user message from history if available
        actual_user_message = user_message
        if not actual_user_message and history and len(history) > 0:
            # Try to get the user message from the last history item
            if hasattr(history[-1], "role") and history[-1].role == "user":
                actual_user_message = history[-1].content
            elif isinstance(history[-1], dict) and history[-1].get("role") == "user":
                actual_user_message = history[-1].get("content", "")

        messages, history = await add_context(
            actual_user_message, history, messages, start_date, end_date
        )
    else:
        messages.append({"role": "user", "content": user_message})

    if cc.lm.llm_api == "openai":
        # Stream response from OpenAI
        async with await openai.chat.completions.create(
            model=selected_model,
            messages=messages,
            temperature=0,
            stream=True,
        ) as response:
            async for chunk in response:
                delta_content = chunk.choices[0].delta.content
                if delta_content:
                    if history[-1].role == "user":
                        history.append(
                            gr.ChatMessage(role="assistant", content=delta_content)
                        )
                    else:
                        history[-1].content += delta_content
                    yield history

    elif cc.lm.llm_api == "ollama":
        # Stream response from Ollama
        async for part in await ollama.chat(
            model=selected_model, messages=messages, stream=True
        ):
            delta_content = part["message"]["content"]
            if delta_content:
                if history[-1].role == "user":
                    history.append(
                        gr.ChatMessage(role="assistant", content=delta_content)
                    )
                else:
                    history[-1].content += delta_content
                yield history

    else:
        raise ValueError("Invalid LLM API")


def handle_audio_upload(file):
    if file is None:
        return "Please upload a WAV file"

    if not file.name.lower().endswith(".wav"):
        return "Only WAV files are supported"

    try:
        cc.transcribe_and_store(file.name)
        return f"Audio stored in DB."
    except Exception as e:
        return f"Error processing file: {str(e)}"


def create_dataframe(query=None, start_date=None, end_date=None):
    # Convert DateTime component output to date objects
    start_date_obj = None
    end_date_obj = None

    if start_date:
        # Handle different possible formats from gr.DateTime
        if isinstance(start_date, datetime.datetime):
            start_date_obj = start_date.date()
        elif isinstance(start_date, date):
            start_date_obj = start_date
        elif isinstance(start_date, str) and start_date.strip():
            try:
                start_date_obj = datetime.datetime.fromisoformat(start_date).date()
            except ValueError:
                print(f"Invalid start date format: {start_date}")

    if end_date:
        # Handle different possible formats from gr.DateTime
        if isinstance(end_date, datetime.datetime):
            end_date_obj = end_date.date()
        elif isinstance(end_date, date):
            end_date_obj = end_date
        elif isinstance(end_date, str) and end_date.strip():
            try:
                end_date_obj = datetime.datetime.fromisoformat(end_date).date()
            except ValueError:
                print(f"Invalid end date format: {end_date}")

    if query:
        query_answers = cc.rag.retrieve_chunks(
            query_texts=[query], start_date=start_date_obj, end_date=end_date_obj
        )
        ids, documents, metadata, distances = query_answers[0]
        df = pd.DataFrame(
            {
                "ids": ids,
                "documents": documents,
                "filename": [e["filename"] for e in metadata],
                "date": [e.get("date", "N/A") for e in metadata],
                "distances": [round(e, 2) for e in distances],
            }
        )
        # sort by distance
        df = df.sort_values(by="distances", ascending=False)
        return df
    else:
        # Get all documents, possibly filtered by date
        ids, documents, metadata = cc.db_api.get_full_database(
            start_date_obj, end_date_obj
        )
        df = pd.DataFrame(
            {
                "ids": ids,
                "documents": documents,
                "filename": [e["filename"] for e in metadata],
                "date": [
                    e.get("date", "N/A") for e in metadata
                ],  # Include date in dataframe
            }
        )
        return df


def filter_by_date(start_date, end_date):
    """Filter the database by date range without a query."""
    return create_dataframe(query=None, start_date=start_date, end_date=end_date)


with gr.Blocks(
    fill_height=True,
    fill_width=True,
    theme=theme,
    title="coco",
    css="#input_message {background-color: transparent} footer {visibility: hidden} ",
) as demo:
    with gr.Sidebar(open=False):
        gr.Markdown("# ")
        gr.Markdown("# Set some options")
        initial_provider = cc.lm.llm_api
        provider_dropdown = gr.Dropdown(
            choices=["ollama", "openai"],
            value=initial_provider,
            label="Select Provider",
            interactive=True,
        )
        # Add model selection dropdown
        model_dropdown = gr.Dropdown(
            choices=get_available_models(),
            label="Select Model",
            interactive=True,
        )
        system_message = gr.Textbox(
            label="System Message",
            lines=10,
            placeholder=system_message_default,
        )
        include_context = gr.Radio(
            choices=["Yes", "No"],
            value="Yes",
            label="Include Context?",
        )

        provider_dropdown.input(
            update_available_models, [provider_dropdown], [model_dropdown]
        )

    # Add a state variable to store the current user message
    current_user_message = gr.State("")

    with gr.Group():
        with gr.Row():
            chat_start_date = gr.DateTime(
                label="Filter documents from",
                value=None,
            )
            chat_end_date = gr.DateTime(
                label="Filter documents to",
                value=None,
            )

        chatbot = gr.Chatbot(
            label="coco",
            type="messages",
            height="80vh",
            # editable="user",
            render_markdown=True,  # If Rag Context is messed up, this is where to look.
        )
        input_message = gr.Textbox(
            placeholder="Type your message here...",
            show_label=False,
            autofocus=True,
            submit_btn=True,
            elem_id="input_message",
        )

        # Function to update the current_user_message state
        def update_user_message(msg):
            return msg

        # Also allow Enter key to submit
        input_message.submit(
            update_user_message, [input_message], [current_user_message]
        ).then(
            user, [input_message, chatbot], [input_message, chatbot], queue=False
        ).then(
            fn=call_rag_stream,
            inputs=[
                current_user_message,  # Use the state variable instead of input_message
                chatbot,
                model_dropdown,
                system_message,
                chat_start_date,
                chat_end_date,
                include_context,
            ],
            outputs=[chatbot],
        )

        # For retry, we don't have a new user message, so use empty string or last message in history
        chatbot.retry(retry, [chatbot], [chatbot], queue=False).then(
            fn=call_rag_stream,
            inputs=[
                current_user_message,  # Use stored message for retry
                chatbot,
                model_dropdown,
                system_message,
                chat_start_date,
                chat_end_date,
                include_context,
            ],
            outputs=[chatbot],
        )

        # Second retry handler
        chatbot.retry(retry, [chatbot], [chatbot], queue=False).then(
            fn=call_rag_stream,
            inputs=[
                current_user_message,  # Use stored message for retry
                chatbot,
                model_dropdown,
                system_message,
                chat_start_date,
                chat_end_date,
                include_context,
            ],
            outputs=[chatbot],
        )

with demo.route("Memory") as incrementer_demo:

    with gr.Sidebar(open=False):
        gr.Markdown("# ")
        gr.Markdown("# Upload additional data")
        file_upload = gr.File(
            label="Upload Audio (.wav)",
            file_types=[".wav"],
            type="filepath",
            file_count="single",
        )
        upload_status = gr.Textbox(label="Upload Status", interactive=False)

    with gr.Row():
        query = gr.Textbox(
            label="Query",
            lines=1,
            placeholder="Insert some query you want to search for...",
        )

    with gr.Row():
        start_date = gr.DateTime(label="Start Date", value=None)
        end_date = gr.DateTime(label="End Date", value=None)

    data_view = gr.DataFrame(create_dataframe, wrap=True)
    with gr.Row():
        btn_show_all = gr.Button("Show All")
        btn_filter_by_date = gr.Button("Filter by Date")
        btn_clear_dates = gr.Button("Clear Date Filters")
        gr.Button("Clear Database (Not yet implemented)")

    # Add file upload handler
    file_upload.upload(
        fn=handle_audio_upload,
        inputs=[file_upload],
        outputs=[upload_status],
    ).then(create_dataframe, [], [data_view])

    query.submit(
        fn=create_dataframe,
        inputs=[query, start_date, end_date],
        outputs=[data_view],
        queue=False,
    ).then(clear, [query], [query])

    # Date filter buttons
    btn_show_all.click(create_dataframe, outputs=[data_view])
    btn_filter_by_date.click(
        filter_by_date, inputs=[start_date, end_date], outputs=[data_view]
    )
    btn_clear_dates.click(lambda: (None, None), outputs=[start_date, end_date]).then(
        create_dataframe, [], [data_view]
    )

# Add new Agent page with agent capabilities
with demo.route("Agent") as agent_demo:
    with gr.Sidebar(open=False):
        gr.Markdown("# ")
        gr.Markdown("# Set agent options")
        agent_provider_dropdown = gr.Dropdown(
            choices=["ollama", "openai"],
            value=cc.lm.llm_api,
            label="Select Provider",
            interactive=True,
        )
        # Add model selection dropdown
        agent_model_dropdown = gr.Dropdown(
            choices=get_available_models(),
            label="Select Model",
            interactive=True,
        )
        # Add a simple default system message that explicitly forbids Python tag usage
        default_agent_system_message = """
Du bist Coco, ein hilfreicher Assistent mit Zugriff auf verschiedene Tools. 
Nutze diese Tools, um die Anfrage des Benutzers zu erfüllen. Antworte immer
präzise und nützlich. Wenn du mehr Informationen benötigst, verwende die
entsprechenden Tools, um sie zu erhalten. Wenn du mehrere Tools ausführen musst,
tue dies ohne nachfrage nacheinander und beziehe die Ergebnisse in deine
Überlegungen ein.
"""

        agent_system_message = gr.Textbox(
            label="System Message",
            lines=10,
            value=default_agent_system_message,
            placeholder="Du bist Coco, ein Assistent mit Zugriff auf Tools. Nutze Tools um Anfragen zu erfüllen. Verwende die Werte aus Tool-Ergebnissen direkt in deinen Antworten.",
        )
        max_iterations = gr.Slider(
            minimum=1, maximum=10, value=5, step=1, label="Max Iterations"
        )
        max_tool_calls = gr.Slider(
            minimum=1,
            maximum=20,
            value=10,  # Higher default value
            step=1,
            label="Max Tool Calls",
        )
        # temperature slider removed as it causes issues with tool usage

        agent_provider_dropdown.input(
            update_available_models, [agent_provider_dropdown], [agent_model_dropdown]
        )

    # Current agent conversation state
    agent_current_user_message = gr.State("")
    agent_chat_history = gr.State([])

    # Main agent chat interface
    agent_chatbot = gr.Chatbot(
        label="Agent Chat",
        type="messages",
        height="80vh",
        render_markdown=True,
    )
    agent_input_message = gr.Textbox(
        placeholder="Ask the agent to do something...",
        show_label=False,
        autofocus=True,
        submit_btn=True,
    )

    # Define agent chat function
    async def agent_chat(
        user_message,
        history,
        model,
        system_message,
        max_iterations,
        max_tool_calls,
        temperature,  # Parameter kept for compatibility but not used
    ):
        # Initialize chat history if empty
        if history is None:
            history = []

        # Convert history format for agent
        agent_messages = []
        if system_message and system_message.strip():
            agent_messages.append({"role": "system", "content": system_message})

        # Safely extract messages from history
        for msg in history:
            # Handle both gr.ChatMessage and dict formats
            if hasattr(msg, "role") and hasattr(msg, "content"):
                role = msg.role
                content = msg.content
            elif isinstance(msg, dict) and "role" in msg and "content" in msg:
                role = msg["role"]
                content = msg["content"]
            else:
                continue  # Skip invalid message formats

            agent_messages.append({"role": role, "content": content})

        # Add user message to agent messages if not already included
        if (
            not agent_messages
            or agent_messages[-1].get("role") != "user"
            or agent_messages[-1].get("content") != user_message
        ):
            agent_messages.append({"role": "user", "content": user_message})

        try:
            # Call agent with temperature always 0 for tool calls
            result = cc.agent.chat(
                messages=agent_messages,
                model=model,
                max_iterations=max_iterations,
                max_tool_calls=max_tool_calls,
                temperature=0.0,  # Always use temperature 0 for tool calls
                stream=False,
            )

            # Display tool calls and results with minimal formatting
            for i, (tool_call, tool_result) in enumerate(
                zip(result["tool_calls"], result["tool_results"])
            ):
                tool_name = tool_call.name
                tool_args = tool_call.arguments
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except:
                        pass

                # Log tool call for debugging
                print(f"Tool call {i+1}: {tool_name}({tool_args})")

                # Format tool call with minimal formatting
                tool_call_content = f"🔧 **Using tool:** `{tool_name}`\n\n**Arguments:**\n```json\n{json.dumps(tool_args, indent=2)}\n```"
                history.append(
                    gr.ChatMessage(role="assistant", content=tool_call_content)
                )
                yield history

                # Format tool result with minimal formatting
                tool_result_str = json.dumps(tool_result, indent=2)
                result_display = f"**Tool Result:**\n```json\n{tool_result_str}\n```"
                history.append(gr.ChatMessage(role="assistant", content=result_display))
                yield history

            # Look for Python tag in the content and remove it (handle malformed outputs)
            final_content = result.get("content", "")

            # Only if there's content, display it
            if final_content and final_content.strip() and final_content != "None":
                history.append(gr.ChatMessage(role="assistant", content=final_content))
                yield history

        except Exception as e:
            error_message = f"Error: {str(e)}"
            print(f"Agent error: {error_message}")
            history.append(gr.ChatMessage(role="assistant", content=error_message))
            yield history

    # Function to update agent_current_user_message
    def update_agent_user_message(msg):
        return msg

    # Connect UI event handlers
    agent_input_message.submit(
        update_agent_user_message, [agent_input_message], [agent_current_user_message]
    ).then(
        # Add the user message to history, ensuring it's a gr.ChatMessage
        lambda msg, history: (
            "",  # Clear input box
            (history or []) + [gr.ChatMessage(role="user", content=msg)],
        ),
        [agent_input_message, agent_chatbot],
        [agent_input_message, agent_chatbot],
        queue=False,
    ).then(
        fn=agent_chat,
        inputs=[
            agent_current_user_message,
            agent_chatbot,
            agent_model_dropdown,
            agent_system_message,
            max_iterations,
            max_tool_calls,
            gr.State(0.0),  # Always use temperature 0.0 instead of the slider
        ],
        outputs=[agent_chatbot],
    )

    # Clear chat button for the agent
    agent_clear_button = gr.Button("Clear Chat")
    agent_clear_button.click(lambda: [], outputs=[agent_chatbot])

if __name__ == "__main__":
    demo.launch(favicon_path="favicon.png")
