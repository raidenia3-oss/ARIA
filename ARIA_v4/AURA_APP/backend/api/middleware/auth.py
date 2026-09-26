"""Auth Middleware"""

from typing import Optional


class AuthMiddleware:
    """Middleware de autenticación"""

    def __init__(self):
        self.enabled = False
        self.api_keys = set()

    def set_api_key(self, key: str) -> None:
        self.api_keys.add(key)

    def authenticate(self, api_key: Optional[str] = None) -> bool:
        if not self.enabled:
            return True
        return api_key in self.api_keys
