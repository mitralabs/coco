import gradio as gr
from shared import (
    cc,
    system_message_default,
    CONTEXT_FORMAT,
    EMBEDDING_MODEL,
    DEFAULT_LLM_MODEL,
    update_available_models,
    get_available_models,
    parse_datetime,
)


async def add_context(user_message, history, messages, start_date=None, end_date=None):
    start_datetime_obj = parse_datetime(start_date)
    end_datetime_obj = parse_datetime(end_date)

    # Get RAG context with datetime filters
    contexts = await cc.rag.async_retrieve_multiple(
        [user_message],
        5,
        start_date_time=start_datetime_obj,
        end_date_time=end_datetime_obj,
        model=EMBEDDING_MODEL,
    )
    context_chunks = contexts[0][1]
    rag_context = CONTEXT_FORMAT.format(context="\n-----\n".join(context_chunks))

    # Add RAG context
    messages.append({"role": "user", "content": rag_context})
    history.append(
        gr.ChatMessage(
            role="user",
            content=f"```{rag_context}```",  # Markdown code block
            metadata={"title": "RAG Context", "status": "done"},
        )
    )
    return messages, history


async def call_rag_stream(
    user_message,
    history,
    selected_model,
    system_message,
    start_date,
    end_date,
    include_context,
):
    start_datetime_obj = parse_datetime(start_date)
    end_datetime_obj = parse_datetime(end_date)

    messages = []
    # Add system message
    if system_message == "":
        system_message = system_message_default
    messages.append({"role": "system", "content": system_message})

    # Add previous messages
    for element in history:
        messages.append({"role": element["role"], "content": element["content"]})

    if include_context == "Yes":
        # Get the user message from history if available
        actual_user_message = user_message
        if not actual_user_message and history and len(history) > 0:
            if hasattr(history[-1], "role") and history[-1].role == "user":
                actual_user_message = history[-1].content
            elif isinstance(history[-1], dict) and history[-1].get("role") == "user":
                actual_user_message = history[-1].get("content", "")

        messages, history = await add_context(
            actual_user_message, history, messages, start_datetime_obj, end_datetime_obj
        )
    else:
        messages.append({"role": "user", "content": user_message})

    if cc.lm.llm_api == "openai":
        from shared import openai

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
        from shared import ollama

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


def user(user_message, history):
    if history is None:
        history = []
    history.append({"role": "user", "content": user_message})
    return "", history


def retry(history):
    history.pop()
    return history


def clear(input_message):
    return ""


# Main chat interface
with gr.Blocks() as demo:
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

        model_dropdown = gr.Dropdown(
            choices=get_available_models(),
            value=DEFAULT_LLM_MODEL,
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

    # Current user message state
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
            render_markdown=True,
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

        # Handle message submission and response
        input_message.submit(
            update_user_message, [input_message], [current_user_message]
        ).then(
            user, [input_message, chatbot], [input_message, chatbot], queue=False
        ).then(
            fn=call_rag_stream,
            inputs=[
                current_user_message,
                chatbot,
                model_dropdown,
                system_message,
                chat_start_date,
                chat_end_date,
                include_context,
            ],
            outputs=[chatbot],
        )

        # Handle retry functionality
        chatbot.retry(retry, [chatbot], [chatbot], queue=False).then(
            fn=call_rag_stream,
            inputs=[
                current_user_message,
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
                current_user_message,
                chatbot,
                model_dropdown,
                system_message,
                chat_start_date,
                chat_end_date,
                include_context,
            ],
            outputs=[chatbot],
        )
