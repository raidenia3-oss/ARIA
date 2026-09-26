@echo off
cd /d "C:\Users\User\Downloads\AURA"
"C:\Users\User\Downloads\AURA\venv-training\Scripts\python.exe" scripts/aura_autonomous_trainer.py --epochs 5 --lr 8e-5 --batch-size 2 --max-length 512 --quality-threshold 0.80 --max-collections 1
