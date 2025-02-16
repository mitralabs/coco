import gradio as gr
import pandas as pd
import numpy as np

from coco import CocoClient

# See Gradio Docs for reference: https://www.gradio.app/docs

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
    llm_api="ollama",
    api_key="test",
)

# Get available models
available_models = cc.lm.list_llm_models()
embedding_models = [
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
available_models = [
    model for model in available_models if model not in embedding_models
]

if not available_models:
    available_models = [
        "meta-llama/Llama-3.3-70B-Instruct"
    ]  # Default fallback model for Ollama


system_message_default = "Du bist coco.\n\nDu hilfst dem User bestmöglich.\n\nDu antwortest präzise und kommunizierst auf Deutsch."

CONTEXT_FORMAT = """
    Eine Recherche in der Datenbank hat folgende Inhalte ergeben:

    -----
    {context}
    -----
"""


def user(user_message, history):
    # print(user_message)
    if history is None:
        history = []
    history.append({"role": "user", "content": user_message})
    # print(history)
    return "", history


def clear(input_message):
    return ""


async def call_rag(user_message, history, selected_model, system_message):
    try:
        # Get RAG context
        contexts = await cc.rag.async_retrieve_chunks([user_message], 5)
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

        # Add RAG context -> Note the "tool" role is ollama specific. See: https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-chat-completion
        messages.append(
            {
                "role": "tool",
                "content": rag_context,
            }
        )
        print(messages)

        responses, tok_ss = await cc.lm.async_chat(
            messages_list=[messages],
            model=selected_model,
            batch_size=20,
            limit_parallel=10,
            show_progress=True,
        )
        reponse, tok_s = responses[0], tok_ss[0]

        print("Token per seconds:", tok_s)

        history.extend(
            [
                gr.ChatMessage(
                    role="assistant",
                    content=rag_context,
                    metadata={"title": "RAG Context", "status": "done"},
                ),
                gr.ChatMessage(role="assistant", content=reponse),
            ]
        )
        yield history
    except Exception as e:
        history.append({"role": "assistant", "content": f"Error: {str(e)}"})
        yield history
        raise e


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


def create_dataframe(query=None):
    ids, documents, metadata = cc.db_api.get_full_database()
    # print(documents[0])
    df = pd.DataFrame(
        {
            "ids": ids,
            "documents": documents,
            "filename": [e["filename"] for e in metadata],
        }
    )
    print(f"query: {query}")

    if query:
        query_answers = cc.rag.retrieve_chunks(query_texts=[query])
        ids, documents, metadata, distances = query_answers[0]
        df = pd.DataFrame(
            {
                "ids": ids,
                "documents": documents,
                "filename": [e["filename"] for e in metadata],
                "distances": [round(e, 2) for e in distances],
            }
        )
        # sort by distance
        df = df.sort_values(by="distances", ascending=False)
        return df
    else:
        return df


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
        # Add model selection dropdown
        model_dropdown = gr.Dropdown(
            choices=available_models,
            value=available_models[0],
            label="Select Model",
            interactive=True,
        )
        system_message = gr.Textbox(
            label="System Message",
            lines=10,
            placeholder=system_message_default,
        )

    with gr.Group():
        chatbot = gr.Chatbot(
            label="coco",
            type="messages",
            height="80vh",
            # editable="user",
            render_markdown=False,
        )
        input_message = gr.Textbox(
            placeholder="Type your message here...",
            show_label=False,
            autofocus=True,
            submit_btn=True,
            elem_id="input_message",
        )

        # Also allow Enter key to submit
        input_message.submit(
            user, [input_message, chatbot], [input_message, chatbot], queue=False
        ).then(
            fn=call_rag,
            inputs=[
                input_message,
                chatbot,
                model_dropdown,
                system_message,
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

    query = gr.Textbox(
        label="Query",
        lines=1,
        placeholder="Insert some query you want to search for...",
    )

    data_view = gr.DataFrame(create_dataframe, wrap=True)
    with gr.Row():
        btn_show_all = gr.Button("Show All")
        btn_show_all.click(create_dataframe, outputs=[data_view])
        gr.Button("Clear Database (Not yet implemented)")

    # Add file upload handler
    file_upload.upload(
        fn=handle_audio_upload,
        inputs=[file_upload],
        outputs=[upload_status],
    ).then(create_dataframe, [], [data_view])

    query.submit(
        fn=create_dataframe,
        inputs=[query],
        outputs=[data_view],
        queue=False,
    ).then(clear, [query], [query])

    # test if change detected. again.

if __name__ == "__main__":
    demo.launch(favicon_path="favicon.png")
