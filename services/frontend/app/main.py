import gradio as gr
import aiohttp
import json

from coco import CocoClient

cc = CocoClient(
    chunking_base="http://127.0.0.1:8001",
    embedding_base="http://127.0.0.1:8002",
    db_api_base="http://127.0.0.1:8003",
    transcription_base="http://127.0.0.1:8000",
    ollama_base="https://jetson-ollama.mitra-labs.ai",
    api_key="test",
)

cc.health_check()

async def call_rag(user_message, history):
    # Get RAG context
    rag_context = (await cc.rag.retrieve_chunks([user_message], 5))[0]   
    formatted_prompt = cc.rag.format_prompt(user_message, rag_context[1])

    # Prepare messages for Ollama
    messages = []
    if history:
        messages.extend([{"role": m[0], "content": m[1]} for m in history])
    messages.append({"role": "user", "content": formatted_prompt})

    # Call Ollama API
    url = f"{cc.ollama_base}/api/chat"
    payload = {
        "model": "deepseek-r1:14b",
        "messages": messages,
        "stream": True,
    }

    response_buffer = ""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload) as response:
                async for line in response.content:
                    if line:
                        try:
                            data = json.loads(line.decode('utf-8'))
                            content = data.get("message", {}).get("content", "")
                            response_buffer += content
                            
                            # Update the chat interface
                            history_update = history + [(user_message, response_buffer)]
                            yield history_update, str(rag_context)
                            
                        except json.JSONDecodeError:
                            print(f"Failed to parse JSON: {line}")
                            
        except Exception as e:
            print(f"Error: {e}")
            yield history + [(user_message, f"Error: {str(e)}")], str(rag_context)

async def handle_audio_upload(file):
    if file is None:
        return "Please upload a WAV file"
    
    if not file.name.lower().endswith('.wav'):
        return "Only WAV files are supported"
    
    try:
        # Store the audio file and get embeddings
        result = await cc.store(file.name)
        return f"Successfully processed and stored audio file: {file.name}"
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
                    elem_classes="input-height"
                )
                submit_btn = gr.Button(
                    "Submit",
                    scale=1,
                    variant="primary",
                    elem_classes="orange-button small-button"
                )
                file_upload = gr.File(
                    label="Upload Audio",
                    file_types=[".wav"],
                    type="filepath",
                    file_count="single",
                    scale=1,
                    elem_classes="file-upload small-button"
                )
            
            upload_status = gr.Textbox(
                label="Upload Status",
                interactive=False
            )
            
        with gr.Column(scale=1):
            gr.Markdown("### RAG Context")
            rag_context_display = gr.Textbox(
                label="Retrieved Context",
                lines=10,
                interactive=False
            )

    gr.Markdown("""
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
    """)

    # Event handlers
    submit_btn.click(
        fn=call_rag,
        inputs=[input_message, chatbot],
        outputs=[chatbot, rag_context_display],
        api_name="chat"
    )
    
    # Also allow Enter key to submit
    input_message.submit(
        fn=call_rag,
        inputs=[input_message, chatbot],
        outputs=[chatbot, rag_context_display],
        api_name="chat"
    )
    
    # Add file upload handler
    file_upload.upload(
        fn=handle_audio_upload,
        inputs=[file_upload],
        outputs=[upload_status],
        api_name="upload_audio"
    )

if __name__ == "__main__":
    demo.launch()