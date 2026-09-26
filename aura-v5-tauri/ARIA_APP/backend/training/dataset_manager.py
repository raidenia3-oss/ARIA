import asyncio
import json
import os
from typing import Any, Dict, List, Optional, Tuple


class DatasetManager:
    def __init__(self, data_dir: str = "") -> None:
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(self.data_dir, exist_ok=True)

    async def load_dataset(self, path: str, format: str = "jsonl") -> List[Dict[str, Any]]:
        full_path = os.path.join(self.data_dir, path)
        if not os.path.exists(full_path):
            return []
        data = []
        with open(full_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return data

    async def clean_data(
        self, data: List[Dict[str, Any]], required_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        if required_fields is None:
            required_fields = ["input", "output"]
        cleaned = []
        for item in data:
            if all(f in item for f in required_fields):
                if all(item.get(f) is not None for f in required_fields):
                    cleaned.append(item)
        return cleaned

    async def augment_data(
        self, data: List[Dict[str, Any]], multiplier: int = 2
    ) -> List[Dict[str, Any]]:
        augmented = list(data)
        for item in data:
            for i in range(multiplier - 1):
                new_item = dict(item)
                if "input" in new_item:
                    new_item["input"] = new_item["input"] + " " + str(i)
                augmented.append(new_item)
        return augmented

    async def split_train_test(
        self, data: List[Dict[str, Any]], train_ratio: float = 0.8
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        split_idx = int(len(data) * train_ratio)
        import random

        shuffled = list(data)
        random.shuffle(shuffled)
        return shuffled[:split_idx], shuffled[split_idx:]
