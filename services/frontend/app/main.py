import gradio as gr

from coco import CocoClient

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

# Get available models
available_models = cc.lm.list_llm_models()
if not available_models:
    available_models = ["meta-llama/Llama-3.3-70B-Instruct"]  # Default fallback model for Ollama

# Start a health check
# cc.health_check()

async def call_rag(user_message, history, selected_model):
    try:
        # Get RAG context
        contexts = await cc.rag.async_retrieve_chunks([user_message], 5)
        rag_context = contexts[0][1]

        # Format prompt
        formatted_prompt = cc.rag.format_prompt(user_message, rag_context)

        # Prepare messages with proper role formatting
        messages = []
        if history:
            for i, (msg_user, msg_assistant) in enumerate(history):
                messages.append({"role": "user", "content": msg_user})
                messages.append({"role": "assistant", "content": msg_assistant})
        messages.append({"role": "user", "content": formatted_prompt})

        responses, tok_ss = await cc.lm.async_chat(
            messages_list=[messages],
            model=selected_model,
            batch_size=20,
            limit_parallel=10,
            show_progress=True,
        )
        reponse, tok_s = responses[0], tok_ss[0]

        print("Token per seconds:", tok_s)
        chat = history + [(user_message, reponse)]
        yield chat, str(rag_context)
    except Exception as e:
        yield history + [(user_message, f"Error: {str(e)}")], "Error in call_rag"
        raise e

    #     # Call Ollama API
    #     url = f"{cc.ollama_base}/api/chat"
    #     payload = {
    #         "model": "deepseek-r1:14b",
    #         "messages": messages,
    #         "stream": True,
    #     }

    #     response_buffer = ""
    #     async with aiohttp.ClientSession() as session:
    #         try:
    #             async with session.post(url, json=payload) as response:
    #                 async for line in response.content:
    #                     if line:
    #                         try:
    #                             data = json.loads(line.decode("utf-8"))
    #                             content = data.get("message", {}).get("content", "")
    #                             response_buffer += content

    #                             # Update the chat interface
    #                             history_update = history + [
    #                                 (user_message, response_buffer)
    #                             ]
    #                             yield history_update, str(rag_context)

    #                         except json.JSONDecodeError:
    #                             print(f"Failed to parse JSON: {line}")

    #         except Exception as e:
    #             print(f"Error: {e}")
    #             yield history + [(user_message, f"Error: {str(e)}")], str(rag_context)
    # except Exception as e:
    #     print(f"Error in call_rag: {e}")
    #     yield history + [(user_message, f"Error: {str(e)}")], "Error in call_rag"


async def handle_audio_upload(file):
    if file is None:
        return "Please upload a WAV file"

    if not file.name.lower().endswith(".wav"):
        return "Only WAV files are supported"

    try:
        # Full processing pipeline
        text, language, filename = await cc.transcription.transcribe_audio(file.name)
        chunks = await cc.chunking.chunk_text(text)
        embeddings = await cc.embedding.create_embeddings(chunks)
        documents = [
            {
                "text": chunk,
                "embedding": embedding,
                "metadata": {
                    "language": language,
                    "filename": filename,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            }
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]

        await cc.db_api.add(documents)

        return f"Processed {len(chunks)} chunks from {filename}"
    except Exception as e:
        return f"Error processing file: {str(e)}"


with gr.Blocks(fill_height=True) as demo:

    gr.Markdown("# CoCo")

    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(height=600)
            with gr.Row():
                input_message = gr.Textbox(
                    placeholder="Type your message here...",
                    lines=1,
                    label="Input",
                    scale=2,
                    elem_classes="input-height",
                )
                submit_btn = gr.Button(
                    "Submit",
                    scale=1,
                    variant="primary",
                    elem_classes="orange-button small-button",
                )
                file_upload = gr.File(
                    label="Upload Audio",
                    file_types=[".wav"],
                    type="filepath",
                    file_count="single",
                    scale=1,
                    elem_classes="file-upload small-button",
                )

            upload_status = gr.Textbox(label="Upload Status", interactive=False)

            # Add model selection dropdown
            model_dropdown = gr.Dropdown(
                choices=available_models,
                value=available_models[0],
                label="Select Model",
                interactive=True,
            )

        with gr.Column(scale=1):
            gr.Markdown("### RAG Context")
            rag_context_display = gr.Textbox(
                label="Retrieved Context", lines=10, interactive=False
            )

    gr.Markdown(
        """
        <style>
        .orange-button {
            background-color: #FF8C00 !important;
            border-color: #FF8C00 !important;
        }
        .orange-button:hover {
            background-color: #FFA500 !important;
            border-color: #FFA500 !important;
        }
        .file-upload {
            margin-left: 8px;
        }
        .small-button {
            height: 46px !important;
            min-height: 46px !important;
            line-height: 1 !important;
        }
        .input-height textarea {
            height: 46px !important;
            min-height: 46px !important;
        }
        </style>
    """
    )

    # Event handlers
    submit_btn.click(
        fn=call_rag,
        inputs=[input_message, chatbot, model_dropdown],
        outputs=[chatbot, rag_context_display],
        api_name="chat",
    )

    # Also allow Enter key to submit
    input_message.submit(
        fn=call_rag,
        inputs=[input_message, chatbot, model_dropdown],
        outputs=[chatbot, rag_context_display],
        api_name="chat",
    )

    # Add file upload handler
    file_upload.upload(
        fn=handle_audio_upload,
        inputs=[file_upload],
        outputs=[upload_status],
        api_name="upload_audio",
    )

if __name__ == "__main__":
    demo.launch()