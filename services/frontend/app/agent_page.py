import gradio as gr
import json
from shared import (
    cc,
    DEFAULT_LLM_MODEL,
    update_available_models,
    get_available_models,
    ollama,
    openai,
)

default_agent_system_message = """
You are Coco, a helpful assistant who provides the best possible help to users. You use tools that you have access to. You speak German, unless the user explicitly starts talking in another language.

# Tools
- You can always execute tools before responding.
- You never ask if you should execute a tool, you just do it.
- You never mention that you will use a tool, you just do it.
- IMPORTANT: You write tool calls to the appropriate property of your response, never in the actual message for the user.
- IMPORTANT: Your answers should always reference the results of the tools when you have used them!

# Your Knowledge
- Your knowledge is stored in the database, which you can access through tools.
- When the user asks for any information, use the database tools to find the answer.
- If you set certain filters on the database, you don't mention them in the query string as well.
- You interpret all document content with respect to the document's metadata.
- Your knowledge is in German, so you should make database queries in German as well.
- IMPORTANT: You act as if you simply remember your knowledge. You never mention the database itself to the user. (But you obviously reference its content.)
"""


# Define agent chat function
async def agent_chat(
    user_message,
    history,
    actual_conversation,
    model,
    system_message,
    max_iterations,
    max_tool_calls,
    temperature,  # Parameter kept for compatibility but not used
):
    # Initialize histories if empty
    if history is None:
        history = []

    if actual_conversation is None:
        actual_conversation = []

    # Prepare system message for the agent
    if system_message and system_message.strip():
        system_msg = {"role": "system", "content": system_message}
        # Only add system message to actual_conversation if it's not already there
        if not actual_conversation or actual_conversation[0].get("role") != "system":
            actual_conversation = [system_msg] + actual_conversation

    # Add current user message to the actual conversation if not already included
    if (
        not actual_conversation
        or actual_conversation[-1].get("role") != "user"
        or actual_conversation[-1].get("content") != user_message
    ):
        actual_conversation.append({"role": "user", "content": user_message})

    try:
        # Call agent with temperature always 0 for tool calls
        result = cc.agent.chat(
            messages=actual_conversation,
            model=model,
            max_iterations=max_iterations,
            max_tool_calls=max_tool_calls,
            temperature=0.0,  # Always use temperature 0 for tool calls
            stream=False,
        )

        # Update the actual conversation with what the agent returned
        actual_conversation = result["conversation_history"]
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
            print(f"Tool call {i+1}: {tool_call}")

            # Format tool call and result in an accordion
            tool_call_args_str = json.dumps(tool_args, indent=2)
            tool_result_str = json.dumps(tool_result, indent=2)

            # Create accordion content with tool usage details
            tool_usage_content = f"""
`{tool_name}`

**Arguments:**
```json
{tool_call_args_str}
```

**Result:**
```json
{tool_result_str}
```
"""

            # Add accordion to history similar to context
            history.append(
                gr.ChatMessage(
                    role="assistant",
                    content=f"{tool_usage_content}",  # Use markdown code block to match context style
                    metadata={"title": "🔧 Tool Usage", "status": "done"},
                )
            )
            yield history, actual_conversation

        # Look for Python tag in the content and remove it (handle malformed outputs)
        final_content = result.get("content", "")

        # Only if there's content, display it
        if final_content and final_content.strip() and final_content != "None":
            history.append(gr.ChatMessage(role="assistant", content=final_content))
            yield history, actual_conversation

    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(f"Agent error: {error_message}")
        history.append(gr.ChatMessage(role="assistant", content=error_message))
        yield history, actual_conversation


# Function to update agent_current_user_message
def update_agent_user_message(msg):
    return msg


from chat_page import clear

# Agent page interface
with gr.Blocks() as demo:
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
            value=DEFAULT_LLM_MODEL,
            label="Select Model",
            interactive=True,
        )

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
            value=10,
            step=1,
            label="Max Tool Calls",
        )

        agent_provider_dropdown.input(
            update_available_models, [agent_provider_dropdown], [agent_model_dropdown]
        )

    # Current agent conversation state
    agent_current_user_message = gr.State("")
    # Add state for the actual conversation used by the agent
    agent_actual_conversation = gr.State([])

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

    # Connect UI event handlers
    agent_input_message.submit(
        update_agent_user_message, [agent_input_message], [agent_current_user_message]
    ).then(
        # Add the user message to history, ensuring it's a gr.ChatMessage
        lambda msg, history, actual_conv: (
            "",  # Clear input box
            (history or []) + [gr.ChatMessage(role="user", content=msg)],
            actual_conv,  # Pass through the actual conversation unchanged
        ),
        [agent_input_message, agent_chatbot, agent_actual_conversation],
        [agent_input_message, agent_chatbot, agent_actual_conversation],
        queue=False,
    ).then(
        fn=agent_chat,
        inputs=[
            agent_current_user_message,
            agent_chatbot,
            agent_actual_conversation,
            agent_model_dropdown,
            agent_system_message,
            max_iterations,
            max_tool_calls,
            gr.State(0.0),  # Always use temperature 0.0 instead of the slider
        ],
        outputs=[agent_chatbot, agent_actual_conversation],
    )

    # Clear chat button for the agent
    agent_clear_button = gr.Button("Clear Chat")
    agent_clear_button.click(
        lambda: ([], []), outputs=[agent_chatbot, agent_actual_conversation]
    )
