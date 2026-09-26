@echo off
REM AURA Enhanced Fine-tuning Runner
REM Modelo: Qwen2.5-1.5B | Datos: local + web (Wikipedia)
REM Entorno: venv-training (CPU-only) | Optimizacion: LoRA + gradient checkpointing

call venv-training\Scripts\activate

python scripts\aura_autonomous_trainer.py auto ^
  --model-path models/qwen-1.5b ^
  --epochs 3 ^
  --lr 0.0001 ^
  --batch-size 2 ^
  --max-length 1024 ^
  --web-search ^
  --topics "Transformer machine learning" "Fine-tuning" "Reinforcement learning" "Qwen" ^
  --quality-threshold 0.75 ^
  --max-collections 2

pause
