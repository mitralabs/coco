import json
import gradio as gr
import aiohttp
import requests
import asyncio

from coco import CocoClient, only_rag, rag_query

cc = CocoClient(
    chunking_base="http://127.0.0.1:8001",
    embedding_base="http://127.0.0.1:8002",
    db_api_base="http://127.0.0.1:8003",
    transcription_base="http://127.0.0.1:8000",
    api_key="test",
)

async def slow_echo(user_message, history):
    
    rag_content = only_rag(cc, user_message)
    print(rag_content)
    messages_ollama = [{"role": m['role'], "content": m['content']} for m in history]
    #messages_ollama.extend([{"role": "system","content": system_prompt.format(rag_result=rag_content)}])
    messages_ollama.append({"role": "user", "content": rag_content})

    url = "https://jetson-ollama.mitra-labs.ai/api/generate"
    payload = {
        "model": "deepseek-r1:14b",
        "messages": messages_ollama,
        "stream": True,
    }
    
    thought_buffer = ""
    response_buffer = ""
    in_thought = False
    response_started = False

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload) as response:
                async for line in response.content:
                    if line:
                        line = line.decode("utf-8")
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")

                            if "<think>" in content and not in_thought:
                                in_thought = True
                                content = content.replace("<think>", "")

                            if "</think>" in content and in_thought:
                                in_thought = False                        
                                response_started = True

                                thought_content = gr.ChatMessage(
                                        role="assistant",
                                        content=thought_buffer,
                                        metadata={"title": "Thinking completed", "status": "done"}
                                    )
                                yield thought_content, gr.Textbox(label="",lines = 10,value=rag_content) # more info https://www.gradio.app/docs/gradio/textbox

                            if in_thought:
                                thought_buffer += content
                                yield gr.ChatMessage(
                                        role="assistant",
                                        content=thought_buffer,
                                        metadata={"title": "Thinking...", "status": "pending"}
                                    ) , gr.Textbox(label="",lines = 10,value=rag_content) # more info https://www.gradio.app/docs/gradio/textbox

                            elif response_started:
                                response_buffer += content
                                yield [
                                    thought_content,
                                    gr.ChatMessage(
                                        role="assistant",
                                        content=response_buffer,
                                    )
                                    ] , gr.Textbox(label="",lines = 10,value=rag_content) # more info https://www.gradio.app/docs/gradio/textbox
                                
                        except json.JSONDecodeError:
                            print(f"Failed to parse JSON: {line}")
        except aiohttp.ClientError as e:
            print(f"Error: {e}")


with gr.Blocks(fill_height=True) as demo:
    
    rag_reply = gr.Textbox(render=False)
    gr.Markdown("# A Gradio Chatinterface for CoCo Development")
    with gr.Row():
        with gr.Column():
            #gr.Markdown("### ")
            gr.ChatInterface(
                slow_echo,
                type="messages",
                #flagging_mode="manual",
                #save_history=True,
                #additional_outputs=[rag_reply]
            )
        with gr.Column():
            gr.Markdown("### Reply from RAG System")
            rag_reply.render()
    
if __name__ == "__main__":
    demo.launch()