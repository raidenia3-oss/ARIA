import gradio as gr

DESCRIPTION = """<h1 style="text-align: center;">AURA Chat</h1>"""

def chat_response(message, history, system_prompt, temperature, max_tokens):
    response = f"[AURA HF Space] Recibido: {message}"
    history = history or []
    history.append((message, response))
    return response, history

demo = gr.ChatInterface(
    fn=chat_response,
    title="AURA Chat",
    description=DESCRIPTION,
    additional_inputs=[
        gr.Textbox(label="System Prompt", value="Eres AURA, un asistente de IA avanzado."),
        gr.Slider(0.1, 1.0, value=0.7, label="Temperature"),
        gr.Slider(64, 1024, value=512, step=64, label="Max Tokens"),
    ],
)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
