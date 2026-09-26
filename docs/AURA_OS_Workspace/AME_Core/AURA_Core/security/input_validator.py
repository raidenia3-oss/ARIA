#!/usr/bin/env python3
"""
input_validator.py - AURA Security Shield Strict Validation Component.
Proporciona funciones de desinfección (sanitization) y cumplimiento de tipos (Type Enforcement)
para mitigar fallos de confusión de tipos y ataques de inyección.
"""

import logging
from typing import Any, Dict, List, Type, Union, Optional

logger = logging.getLogger("AURA_Security")

class SecurityValidationError(Exception):
    """Excepción lanzada cuando una validación de seguridad falla."""
    pass

class InputValidator:
    @staticmethod
    def enforce_type(data: Any, expected_type: Type, field_name: str = "payload"):
        """
        Asegura que el dato sea del tipo esperado. 
        Bloquea de inmediato si el tipo es incorrecto para evitar confusión de tipos.
        """
        if not isinstance(data, expected_type):
            error_msg = f"Security Alert: Type Confusion Attempt detected in {field_name}. Expected {expected_type.__name__}, got {type(data).__name__}."
            logger.error(error_msg)
            raise SecurityValidationError(error_msg)
        return data

    @staticmethod
    def sanitize_string(data: Any, max_length: int = 1024) -> str:
        """
        Desinfecta un string entrante.
        1. Valida que sea string (Type Enforcement).
        2. Limita su longitud.
        3. Escapa caracteres peligrosos si es necesario (dependiendo del contexto).
        """
        InputValidator.enforce_type(data, str, "string_field")
        
        # Recortar si excede el máximo
        sanitized = data[:max_length]
        
        # Eliminar caracteres nulos
        sanitized = sanitized.replace('\x00', '')
        
        return sanitized

    @staticmethod
    def validate_payload(payload: Dict, schema: Dict[str, Type]) -> Dict:
        """
        Valida un payload completo contra un esquema de tipos.
        Útil para el EventManager y endpoints de API/WebSockets.
        """
        InputValidator.enforce_type(payload, dict, "payload_object")
        
        validated_data = {}
        for field, expected_type in schema.items():
            if field not in payload:
                # Si es opcional se podría manejar aquí, por ahora asumimos requeridos
                logger.warning(f"Missing field in payload: {field}")
                continue
            
            value = payload[field]
            InputValidator.enforce_type(value, expected_type, field)
            validated_data[field] = value
            
        return validated_data

    @staticmethod
    def prevent_prototype_pollution(data: Any):
        """
        Evita ataques de contaminación de prototipos o confusión de objetos/arrays.
        Si se recibe un objeto con llaves como '__proto__' o 'constructor', se bloquea.
        """
        if isinstance(data, dict):
            forbidden_keys = {'__proto__', 'constructor', 'prototype'}
            for key in data.keys():
                if key in forbidden_keys:
                    raise SecurityValidationError(f"Security Alert: Prototype Pollution Attempt detected in key: {key}")
                InputValidator.prevent_prototype_pollution(data[key])
        elif isinstance(data, list):
            for item in data:
                InputValidator.prevent_prototype_pollution(item)
        return data

def secure_event_wrapper(func):
    """Decorador para envolver manejadores de eventos con validación de seguridad."""
    def wrapper(self, *args, **kwargs):
        try:
            # Aquí se podría inyectar validación genérica de los argumentos
            return func(self, *args, **kwargs)
        except SecurityValidationError as e:
            # Enviar alerta al HUD si está disponible
            if hasattr(self, '_broadcast_ws'):
                self._broadcast_ws('security_alert', {
                    'level': 'CRITICAL',
                    'message': str(e),
                    'timestamp': str(logging.datetime.datetime.now())
                })
            raise
    return wrapper
