import gradio as gr
import chat_page
import memory_page
import agent_page
from shared import theme

with gr.Blocks(
    fill_height=True,
    fill_width=True,
    theme=theme,
    title="coco",
    css="#input_message {background-color: transparent} footer {visibility: hidden} ",
) as demo:
    # Render the main chat page
    agent_page.demo.render()

# Add Memory page
with demo.route("Memory"):
    memory_page.demo.render()

# Add Agent page
# with demo.route("Chat"):
#     chat_page.demo.render()

if __name__ == "__main__":
    demo.launch(favicon_path="favicon.png")
