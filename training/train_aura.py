
import os
import json
import glob
import torch
import time
import subprocess
from huggingface_hub import login, HfApi
from unsloth import FastLanguageModel
from unsloth.chat_templates import standardize_sharegpt, get_chat_template
from datasets import Dataset
from trl import SFTTrainer
from transformers import TrainingArguments, DataCollatorForSeq2Seq

# --- 0. Setup and Configuration ---
MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"
MAX_SEQ_LENGTH = 2048
LOAD_IN_4BIT = True

LORA_R = 16
LORA_ALPHA = 16
LORA_DROPOUT = 0.05

BATCH_SIZE = 2
GRADIENT_ACCUMULATION_STEPS = 4
NUM_EPOCHS = 3
LEARNING_RATE = 2e-4
WARMUP_STEPS = 5

DATASET_PATH = "aura_merged_training.jsonl"
OUTPUT_DIR = "fine-tuned-ame"
HF_TOKEN = os.environ.get("HF_TOKEN") # Get HF_TOKEN from environment variables

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("--- AURA Fine-tuning Script ---")
print(f"Model: {MODEL_NAME}")
print(f"Dataset: {DATASET_PATH}")
print(f"Output directory: {OUTPUT_DIR}")

# --- 1. Install Unsloth and Dependencies ---
def install_dependencies():
    print("Installing dependencies...")
    # Install bitsandbytes separately as suggested by unsloth for Windows
    try:
        subprocess.run(["pip", "install", "bitsandbytes"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error installing bitsandbytes: {e}")
        print("Please ensure you have the correct CUDA toolkit installed if on NVIDIA GPU.")

    # Install other dependencies including unsloth
    deps = [
        "accelerate", "xformers==0.0.29.post3", "peft", "trl", "triton",
        "cut_cross_entropy", "unsloth_zoo", "sentencepiece", "protobuf",
        "datasets>=3.4.1", "huggingface_hub", "hf_transfer", "unsloth"
    ]
    for dep in deps:
        try:
            subprocess.run(["pip", "install", dep], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error installing {dep}: {e}")
    print("Dependencies installed.")

install_dependencies()

# --- 2. Hugging Face Authentication ---
if HF_TOKEN:
    try:
        login(token=HF_TOKEN)
        api = HfApi()
        user_info = api.whoami()
        print(f"Logged in to Hugging Face as: {user_info['name']}")
    except Exception as e:
        print(f"⚠️ Failed to log in to Hugging Face: {e}")
        print("Model will be saved locally only.")
else:
    print("⚠️ No HF_TOKEN environment variable found. Model will be saved locally only.")

# --- 3. Load Model with 4-bit Quantization ---
print(f"Loading model {MODEL_NAME}...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None, # Auto-detect
    load_in_4bit=LOAD_IN_4BIT,
)
print("Model loaded successfully.")

# --- 4. Add LoRA Adapters ---
print("Adding LoRA adapters...")
model = FastLanguageModel.get_peft_model(
    model,
    r=LORA_R,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    lora_alpha=LORA_ALPHA,
    lora_dropout=LORA_DROPOUT,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=3407,
    use_rslora=False,
    loftq_config=None,
)
model.print_trainable_parameters()
print("LoRA adapters configured.")

# --- 5. Prepare Training Data ---
def load_and_format_jsonl(filepath):
    print(f"Loading training data from {filepath}...")
    all_data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                # Handle different formats: instruction/input/output or text/output
                if "instruction" in entry and "output" in entry:
                    # Alpaca format or similar
                    user_content = entry["instruction"]
                    if entry.get("input"): # Add input if present
                        user_content += "\n" + entry["input"]
                    all_data.append({
                        "conversations": [
                            {"role": "user", "content": user_content},
                            {"role": "assistant", "content": entry["output"]}
                        ]
                    })
                elif "text" in entry and "output" in entry:
                    # AURA format: text=input, output=response
                    all_data.append({
                        "conversations": [
                            {"role": "user", "content": entry["text"]},
                            {"role": "assistant", "content": entry["output"]}
                        ]
                    })
            except json.JSONDecodeError as e:
                print(f"Skipping malformed JSONL line: {line} - Error: {e}")
                continue
    print(f"Total samples loaded: {len(all_data)}")
    return all_data

raw_data = load_and_format_jsonl(DATASET_PATH)
if not raw_data:
    print("Error: No training data loaded. Exiting.")
    exit()

dataset = Dataset.from_list(raw_data)
print(f"Dataset created with {len(dataset)} samples.")

# Standardize format for Qwen2.5 and apply chat template
dataset = standardize_sharegpt(dataset)
tokenizer = get_chat_template(tokenizer, chat_template="qwen_2.5")

def formatting_prompts_func(examples):
    texts = [
        tokenizer.apply_chat_template(
            convo,
            tokenize=False,
            add_generation_prompt=False
        )
        for convo in examples["conversations"]
    ]
    return {"text": texts}

dataset = dataset.map(formatting_prompts_func, batched=True, num_proc=os.cpu_count() // 2 or 1)
print("Data prepared with Qwen2.5 chat template!")
print(f"Sample formatted text:\n{dataset[0]['text'][:500]}...")

# --- 6. Train the Model ---
print("🚀 Starting training...")
training_start_time = time.time()

is_bfloat16_supported = torch.cuda.is_available() and torch.cuda.get_device_properties(0).major >= 8 # Check for Ampere or newer

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer),
    dataset_num_proc=os.cpu_count() // 2 or 1,
    packing=False,
    args=TrainingArguments(
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        warmup_steps=WARMUP_STEPS,
        num_train_epochs=NUM_EPOCHS,
        learning_rate=LEARNING_RATE,
        fp16=not is_bfloat16_supported,
        bf16=is_bfloat16_supported,
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir=os.path.join(OUTPUT_DIR, "outputs"), # Changed to use OUTPUT_DIR
        report_to="none",
    ),
)

trainer_stats = trainer.train()
training_end_time = time.time()

final_train_loss = trainer_stats.metrics['train_loss']
training_time_seconds = training_end_time - training_start_time

print("✅ Training complete!")
print(f"Final train loss: {final_train_loss:.4f}")
print(f"Training time: {training_time_seconds:.2f} seconds")

# --- 7. Save and Export Model ---
# Save LoRA adapters
lora_output_path = os.path.join(OUTPUT_DIR, "aura_finetuned_lora")
model.save_pretrained(lora_output_path)
tokenizer.save_pretrained(lora_output_path)
print(f"✅ LoRA adapters saved to: {lora_output_path}")

# Merge and save full model
print("\nMerging LoRA with base model...")
merged_model = model.merge_and_unload()
merged_output_path = os.path.join(OUTPUT_DIR, "aura_finetuned_merged")
merged_model.save_pretrained(merged_output_path)
tokenizer.save_pretrained(merged_output_path)
print(f"✅ Merged model saved to: {merged_output_path}")

# Export to GGUF for Ollama/LM Studio
print("\nExporting to GGUF format...")
gguf_output_path = os.path.join(OUTPUT_DIR, "aura_finetuned_gguf")
model.save_pretrained_gguf(
    gguf_output_path,
    tokenizer,
    quantization_method="q4_k_m" # Good balance of size and quality
)
print(f"✅ GGUF model saved to: {gguf_output_path}")

# Push to Hugging Face Hub if token provided
hf_upload_command = ""
hf_uploaded = False
if HF_TOKEN:
    print("\n📤 Pushing to Hugging Face Hub...")
    try:
        # The model needs to be merged first to be pushed as a full model
        # Or push the adapters only
        model.push_to_hub(f"aura-finetuned-lora", token=HF_TOKEN) # Push adapters
        tokenizer.push_to_hub(f"aura-finetuned-lora", token=HF_TOKEN)

        # Also push the merged model if desired, but often LoRA adapters are enough
        # merged_model.push_to_hub(f"aura-finetuned-merged", token=HF_TOKEN)
        # tokenizer.push_to_hub(f"aura-finetuned-merged", token=HF_TOKEN)

        hf_uploaded = True
        print("✅ Model (LoRA adapters) pushed to Hugging Face Hub!")
    except Exception as e:
        print(f"⚠️ Failed to push to Hugging Face Hub: {e}")
        hf_upload_command = f"huggingface-cli upload --token {{HF_TOKEN}} {lora_output_path} your-username/aura-finetuned-lora"
        print("Model saved locally. Use the following command to push manually:")
        print(hf_upload_command)
else:
    print("\n⚠️ No HF_TOKEN provided. Model saved locally only.")
    hf_upload_command = f"huggingface-cli upload {lora_output_path} your-username/aura-finetuned-lora"
    print("To push to Hub, set HF_TOKEN environment variable and use this command:")
    print(hf_upload_command)

# --- 8. Report Results ---
print("\n--- Training Report ---")
print(f"Loss Final: {final_train_loss:.4f}")
print(f"Tiempo de entrenamiento: {training_time_seconds:.2f} segundos")
print(f"Ruta del modelo (LoRA): {lora_output_path}")
print(f"Ruta del modelo (Merged): {merged_output_path}")
print(f"Ruta del modelo (GGUF): {gguf_output_path}")
print(f"Subido a HuggingFace Hub: {'Sí' if hf_uploaded else 'No'}")
if hf_upload_command and not hf_uploaded:
    print(f"Comando para subir a HuggingFace Hub (manual): {hf_upload_command}")


