import gradio as gr

def greet(name):
    return f"Hello, {name}! This is AURA Space."

with gr.Blocks(title="AURA Test Space") as demo:
    gr.Markdown("# AURA Test Space\nThis is a simple Gradio app to test the Space functionality.")
    name_input = gr.Textbox("Your Name")
    output_text = gr.Textbox()
    greet_button = gr.Button("Greet")
    greet_button.click(greet, inputs=name_input, outputs=output_text)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)