"""
Fine-tune Qwen2.5 model with custom training data using LoRA.
Phase 58 - Option D2: Model Fine-tuning
Output: ./fine-tuned-ame/ (model files + tokenizer)
"""

import json
import os
import sys
import logging
import argparse
from typing import Optional, Dict, List
from pathlib import Path

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
    BitsAndBytesConfig,
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    TaskType,
)
from datasets import Dataset
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ModelFinetuner")


class ModelFinetuner:
    """Fine-tune Qwen2.5 model using LoRA for memory efficiency."""

    def __init__(
        self,
        model_id: str = "Qwen/Qwen2.5-Coder-3B",
        output_dir: str = "./fine-tuned-ame",
        use_4bit: bool = True,
        use_lora: bool = True,
    ):
        self.model_id = model_id
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_4bit = use_4bit
        self.use_lora = use_lora
        self.tokenizer = None
        self.model = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def load_model(self) -> None:
        """Load base model from HuggingFace with quantization."""
        logger.info(f"Loading model: {self.model_id}")
        logger.info(f"Device: {self.device}")

        # Quantization config for memory efficiency
        bnb_config = None
        if self.use_4bit and self.device.type == "cuda":
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            trust_remote_code=True,
            padding_side="right",
        )
        
        # Add padding token if not present
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load model
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            quantization_config=bnb_config,
            device_map="auto" if self.device.type == "cuda" else None,
            trust_remote_code=True,
            torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
        )

        # Prepare for LoRA fine-tuning
        if self.use_lora:
            if self.use_4bit and self.device.type == "cuda":
                self.model = prepare_model_for_kbit_training(self.model)
            
            lora_config = LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=8,  # LoRA rank
                lora_alpha=32,
                lora_dropout=0.1,
                target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
                bias="none",
            )
            
            self.model = get_peft_model(self.model, lora_config)
            self.model.print_trainable_parameters()

        logger.info("Model loaded successfully")

    def prepare_dataset(
        self, training_data_path: str, max_length: int = 2048
    ) -> tuple:
        """
        Prepare dataset for training.
        
        Args:
            training_data_path: Path to JSONL training data
            max_length: Maximum token length
            
        Returns:
            Tuple of (train_dataset, eval_dataset)
        """
        logger.info(f"Loading training data from: {training_data_path}")

        # Load JSONL data
        conversations = []
        with open(training_data_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    conversations.append(entry)
                except json.JSONDecodeError:
                    continue

        logger.info(f"Loaded {len(conversations)} conversations")

        # Format as text for causal LM
        texts = []
        for conv in conversations:
            text = conv.get("text", "")
            output = conv.get("output", "")
            # Format: "User: {text}\nAssistant: {output}"
            formatted = f"User: {text}\nAssistant: {output}"
            texts.append(formatted)

        # Tokenize
        tokenized = self.tokenizer(
            texts,
            truncation=True,
            padding=False,
            max_length=max_length,
            return_overflowing_tokens=False,
        )

        # Convert to dataset
        dataset = Dataset.from_dict({
            "input_ids": tokenized["input_ids"],
            "attention_mask": tokenized["attention_mask"],
        })

        # Split into train/eval (80/20)
        dataset = dataset.train_test_split(test_size=0.2, seed=42)
        train_dataset = dataset["train"]
        eval_dataset = dataset["test"]

        logger.info(
            f"Dataset prepared: {len(train_dataset)} train, {len(eval_dataset)} eval"
        )

        return train_dataset, eval_dataset

    def compute_metrics(self, eval_pred):
        """Compute evaluation metrics."""
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=-1)
        
        # Calculate accuracy
        mask = labels != -100
        correct = (predictions[mask] == labels[mask]).sum()
        total = mask.sum()
        accuracy = correct / total if total > 0 else 0
        
        return {"eval_accuracy": float(accuracy)}

    def finetune(
        self,
        training_data_path: str,
        output_dir: Optional[str] = None,
        num_epochs: int = 3,
        learning_rate: float = 1e-4,
        batch_size: int = 8,
        max_length: int = 2048,
        test_mode: bool = False,
    ) -> str:
        """
        Fine-tune the model.
        
        Args:
            training_data_path: Path to JSONL training data
            output_dir: Output directory for model
            num_epochs: Number of training epochs
            learning_rate: Learning rate
            batch_size: Batch size
            max_length: Maximum token length
            test_mode: If True, run a dry run with minimal data
            
        Returns:
            Path to saved model
        """
        if test_mode:
            logger.info("RUNNING IN TEST MODE (dry run)")
            num_epochs = 1
            batch_size = 2
            max_length = 128

        # Prepare dataset
        train_dataset, eval_dataset = self.prepare_dataset(
            training_data_path, max_length
        )

        if test_mode:
            # Use only 10 samples for test
            train_dataset = train_dataset.select(range(min(10, len(train_dataset))))
            eval_dataset = eval_dataset.select(range(min(5, len(eval_dataset))))

        # Data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False,  # Causal LM, not masked LM
        )

        # Training arguments
        actual_output_dir = output_dir or str(self.output_dir)
        training_args = TrainingArguments(
            output_dir=actual_output_dir,
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            per_device_eval_batch_size=batch_size,
            gradient_accumulation_steps=4,
            warmup_steps=100,
            learning_rate=learning_rate,
            fp16=self.device.type == "cuda",
            logging_steps=10,
            eval_strategy="steps",
            eval_steps=100,
            save_strategy="steps",
            save_steps=500,
            save_total_limit=2,
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False,
            report_to="none",
            remove_unused_columns=False,
            dataloader_pin_memory=False,
        )

        # Trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            data_collator=data_collator,
        )

        # Train
        logger.info("Starting training...")
        trainer.train()

        # Save model
        self.save_model(actual_output_dir)
        
        # Log final metrics
        if not test_mode:
            eval_results = trainer.evaluate()
            logger.info(f"Final evaluation results: {eval_results}")

        return actual_output_dir

    def save_model(self, output_dir: Optional[str] = None) -> str:
        """
        Save the fine-tuned model.
        
        Args:
            output_dir: Output directory
            
        Returns:
            Path to saved model
        """
        save_path = output_dir or str(self.output_dir)
        
        # Save model
        self.model.save_pretrained(save_path)
        
        # Save tokenizer
        self.tokenizer.save_pretrained(save_path)
        
        # Save config
        with open(os.path.join(save_path, "training_config.json"), "w") as f:
            json.dump({
                "base_model": self.model_id,
                "fine_tuning_method": "LoRA" if self.use_lora else "Full",
                "quantization": "4-bit" if self.use_4bit else "None",
            }, f, indent=2)

        logger.info(f"Model saved to: {save_path}")
        return save_path

    def push_to_hub(
        self, repo_id: str = "raidenia3-oss/ame-finetuned"
    ) -> None:
        """
        Push model to HuggingFace Hub.
        
        Args:
            repo_id: HuggingFace repository ID
        """
        try:
            from huggingface_hub import HfApi, login
            
            # Check if logged in
            api = HfApi()
            
            logger.info(f"Pushing model to HuggingFace Hub: {repo_id}")
            
            # Upload model files
            api.upload_folder(
                folder_path=str(self.output_dir),
                repo_id=repo_id,
                repo_type="model",
            )
            
            logger.info(f"Model pushed to: https://huggingface.co/{repo_id}")
        except Exception as e:
            logger.error(f"Failed to push to Hub: {e}")
            logger.info("Model saved locally. Push manually with: huggingface-cli upload")


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Qwen2.5 model for AME")
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-1.5B", help="Base model ID")
    parser.add_argument("--data", default="training-data.jsonl", help="Training data path")
    parser.add_argument("--output-dir", default="./fine-tuned-ame", help="Output directory")
    parser.add_argument("--epochs", type=int, default=3, help="Number of epochs")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    parser.add_argument("--max-length", type=int, default=2048, help="Max token length")
    parser.add_argument("--no-4bit", action="store_true", help="Disable 4-bit quantization")
    parser.add_argument("--no-lora", action="store_true", help="Disable LoRA (full fine-tune)")
    parser.add_argument("--push-to-hub", action="store_true", help="Push to HuggingFace Hub")
    parser.add_argument("--hub-repo", default="raidenia3-oss/ame-finetuned", help="Hub repo ID")
    parser.add_argument("--test", action="store_true", help="Dry run with minimal data")
    
    args = parser.parse_args()
    
    # Initialize finetuner
    finetuner = ModelFinetuner(
        model_id=args.model_id,
        output_dir=args.output_dir,
        use_4bit=not args.no_4bit,
        use_lora=not args.no_lora,
    )
    
    # Load model
    finetuner.load_model()
    
    # Fine-tune
    output_path = finetuner.finetune(
        training_data_path=args.data,
        output_dir=args.output_dir,
        num_epochs=args.epochs,
        learning_rate=args.lr,
        batch_size=args.batch_size,
        max_length=args.max_length,
        test_mode=args.test,
    )
    
    # Push to Hub if requested
    if args.push_to_hub:
        finetuner.push_to_hub(args.hub_repo)
    
    print(f"\n[OK] Model fine-tuned and saved to: {output_path}")
    if args.test:
        print("   (Test mode - model not fully trained)")


if __name__ == "__main__":
    main()