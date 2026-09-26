"""Validator — Validación de inputs"""

from typing import Any, Dict, List


class Validator:
    """Valida inputs y datos"""

    @staticmethod
    def validate_string(value: Any, min_len: int = 1, max_len: int = 10000) -> bool:
        if not isinstance(value, str):
            return False
        return min_len <= len(value) <= max_len

    @staticmethod
    def validate_number(value: Any, min_val: float = None, max_val: float = None) -> bool:
        if not isinstance(value, (int, float)):
            return False
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False
        return True

    @staticmethod
    def validate_dict(value: Any, required_keys: List[str] = None) -> bool:
        if not isinstance(value, dict):
            return False
        if required_keys:
            return all(k in value for k in required_keys)
        return True

    @staticmethod
    def sanitize(text: str) -> str:
        """Limpia texto de inyección"""
        dangerous = ['<script', '</script>', 'DROP ', 'DELETE ', ';--']
        for d in dangerous:
            text = text.replace(d, '')
        return text.strip()
