from __future__ import annotations

import inspect
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, get_type_hints

from .policy import Policy, PathRisk


class ToolStatus(Enum):
    OK = "ok"
    FAILED = "failed"


@dataclass
class ToolResult:
    tool: str
    status: ToolStatus
    result: Any = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, tool: str, result: Any) -> "ToolResult":
        return cls(tool=tool, status=ToolStatus.OK, result=result)

    @classmethod
    def failed(cls, tool: str, error: str) -> "ToolResult":
        return cls(tool=tool, status=ToolStatus.FAILED, error=error)


@dataclass
class ToolSpec:
    name: str
    schema: Dict[str, Any]
    risk: PathRisk
    path_args: List[str]
    handler: Callable


class ToolRegistry:
    def __init__(self, policy: Policy):
        self._tools: Dict[str, ToolSpec] = {}
        self._policy = policy

    def register(
        self,
        name: str,
        schema: Dict[str, Any],
        risk: PathRisk,
        path_args: List[str],
    ) -> Callable[[Callable], Callable]:
        def decorator(func: Callable) -> Callable:
            sig = inspect.signature(func)
            hints = get_type_hints(func)
            for arg in path_args:
                if arg not in sig.parameters:
                    raise ValueError(f"path_arg '{arg}' not in function signature")
            self._tools[name] = ToolSpec(
                name=name,
                schema=schema,
                risk=risk,
                path_args=path_args,
                handler=func,
            )
            return func

        return decorator

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def list_tools(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def run(
        self, name: str, args: Dict[str, Any], fs_roots: List[str]
    ) -> ToolResult:
        spec = self._tools.get(name)
        if not spec:
            return ToolResult.failed(name, f"tool not found: {name}")

        validated_args = {}
        for arg_name, arg_value in args.items():
            if arg_name in spec.path_args:
                allowed, reason = self._policy.check_path(arg_value, fs_roots, spec.risk)
                if not allowed:
                    return ToolResult.failed(
                        name, f"policy deny {arg_name}={arg_value}: {reason}"
                    )
            validated_args[arg_name] = arg_value

        try:
            result = spec.handler(**validated_args)
        except Exception as e:
            return ToolResult.failed(name, f"handler exception: {e}")

        if not isinstance(result, ToolResult):
            return ToolResult.failed(
                name, f"tipo de retorno invalido: {type(result).__name__}"
            )
        return result


def create_registry(policy: Policy) -> ToolRegistry:
    return ToolRegistry(policy)