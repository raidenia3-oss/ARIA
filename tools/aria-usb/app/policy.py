from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import ctypes
    HAS_WIN32 = True
except Exception:
    HAS_WIN32 = False


class AccessLevel(Enum):
    NONE = "none"
    META = "meta"
    READ = "read"
    WRITE = "write"


class PathRisk(Enum):
    READ = "read"
    WRITE = "write"


SENSITIVE_PATTERNS = [
    r"C:\\Users\\[^\\]+\\AppData",
    r"C:\\Users\\[^\\]+\\OneDrive",
    r"C:\\ProgramData",
    r"C:\\Windows",
    r"C:\\Users\\[^\\]+\\\.ssh",
    r"C:\\Users\\[^\\]+\\\.gnupg",
]

MEDIA_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".heic",
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv",
    ".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg",
    ".raw", ".cr2", ".nef", ".arw",
}

SECRET_EXTS = {".key", ".pem", ".pfx", ".env", ".kdbx"}
SECRET_NAMES = {"id_rsa", "id_ed25519", "authorized_keys", "known_hosts"}

SAFE_EXTS = {
    ".txt", ".md", ".py", ".json", ".yaml", ".yml", ".ini", ".cfg", ".conf",
    ".log", ".csv", ".xml", ".html", ".css", ".js", ".ts", ".rs", ".go",
    ".java", ".cpp", ".c", ".h", ".sh", ".bat", ".ps1", ".toml", ".ini",
    ".rst", ".tex", ".bib", ".sql", ".dockerfile", ".gitignore", ".env.example",
}


@dataclass
class PolicyRule:
    pattern: str
    level: AccessLevel
    media_override: bool = False

    def specificity(self) -> int:
        return len(self.pattern)


@dataclass
class Policy:
    rules: List[PolicyRule] = field(default_factory=list)
    fs_roots: List[str] = field(default_factory=list)

    def add_rule(self, pattern: str, level: AccessLevel, media_override: bool = False):
        self.rules.append(PolicyRule(pattern, level, media_override))

    def _match_rule(self, rel_path: str, risk: PathRisk) -> Optional[PolicyRule]:
        path_lower = rel_path.lower()
        matches = []
        for rule in self.rules:
            if self._match_pattern(path_lower, rule.pattern.lower()):
                matches.append(rule)
        if not matches:
            return None
        # For WRITE risk, prefer WRITE level rules; for READ, prefer READ level rules
        if risk == PathRisk.WRITE:
            write_rules = [r for r in matches if r.level == AccessLevel.WRITE]
            if write_rules:
                return max(write_rules, key=lambda r: r.specificity())
            # Fallback to highest level
            return max(matches, key=lambda r: (r.specificity(), r.level.value))
        else:
            read_rules = [r for r in matches if r.level in (AccessLevel.READ, AccessLevel.WRITE)]
            if read_rules:
                return max(read_rules, key=lambda r: r.specificity())
            return max(matches, key=lambda r: (r.specificity(), r.level.value))

    def _match_pattern(self, path: str, pattern: str) -> bool:
        regex = pattern.replace(".", r"\.")
        regex = regex.replace("**", ".*")
        regex = regex.replace("*", "[^/]*")
        return re.fullmatch(regex, path) is not None

    def _is_media(self, path: str) -> bool:
        ext = Path(path).suffix.lower()
        return ext in MEDIA_EXTS

    def _is_secret(self, path: str) -> bool:
        name = Path(path).name.lower()
        ext = Path(path).suffix.lower()
        return ext in SECRET_EXTS or name in SECRET_NAMES

    def _is_safe(self, path: str) -> bool:
        ext = Path(path).suffix.lower()
        return ext in SAFE_EXTS

    def _is_sensitive_location(self, path: str) -> bool:
        path_lower = path.lower()
        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, path_lower, re.IGNORECASE):
                return True
        return False

    def _get_relative_path(self, canonical: str, roots: List[str]) -> Optional[str]:
        for root in roots:
            root_resolved = Path(root).resolve()
            try:
                rel = Path(canonical).resolve().relative_to(root_resolved)
                return rel.as_posix()
            except ValueError:
                continue
        return None

    def check_path(
        self, path: str, fs_roots: List[str], risk: PathRisk
    ) -> Tuple[bool, str]:
        canonical = self._canonicalize(path)
        if not canonical:
            return False, "invalid path"

        if not self._is_within_roots(canonical, fs_roots):
            return False, "outside allowed roots"

        if self._has_traversal(path):
            return False, "path traversal detected"

        if self._has_ads(path):
            return False, "ADS not allowed"

        if self._has_reserved_name(path):
            return False, "reserved name"

        if self._is_reparse_point(canonical):
            return False, "reparse point"

        rel_path = self._get_relative_path(canonical, fs_roots)
        if not rel_path:
            return False, "cannot determine relative path"

        rule = self._match_rule(rel_path, risk)
        is_media = self._is_media(canonical)
        is_secret = self._is_secret(canonical)
        is_safe = self._is_safe(canonical)

        if rule:
            level = rule.level
            if is_media and not rule.media_override:
                level = AccessLevel.META
            if is_secret:
                level = AccessLevel.META
            if not is_media and not is_secret and not is_safe:
                level = AccessLevel.NONE
        else:
            if self._is_sensitive_location(canonical):
                level = AccessLevel.NONE
            elif is_secret:
                level = AccessLevel.META
            elif is_media:
                level = AccessLevel.META
            elif is_safe:
                level = AccessLevel.READ
            else:
                level = AccessLevel.NONE

        if risk == PathRisk.READ:
            allowed = level in (AccessLevel.READ, AccessLevel.WRITE, AccessLevel.META)
        else:
            allowed = level == AccessLevel.WRITE

        return allowed, f"level={level.value}"

    def _canonicalize(self, path: str) -> Optional[str]:
        try:
            p = Path(path).resolve(strict=False)
            return str(p)
        except Exception:
            return None

    def _is_within_roots(self, path: str, roots: List[str]) -> bool:
        if not roots:
            return False
        path_resolved = Path(path).resolve()
        for root in roots:
            root_resolved = Path(root).resolve()
            try:
                path_resolved.relative_to(root_resolved)
                return True
            except ValueError:
                continue
        return False

    def _has_traversal(self, path: str) -> bool:
        parts = path.replace("/", os.sep).split(os.sep)
        return ".." in parts

    def _has_ads(self, path: str) -> bool:
        if re.match(r"^[A-Za-z]:", path):
            return ":" in path[2:]
        return ":" in path and not path.startswith("//")

    def _has_reserved_name(self, path: str) -> bool:
        reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
        name = Path(path).name.upper().split(".")[0]
        return name in reserved

    def _is_reparse_point(self, path: str) -> bool:
        if not HAS_WIN32:
            return False
        try:
            attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
            if attrs == -1:
                return False
            return bool(attrs & 0x400)
        except Exception:
            return False

    def list_visible(self, root: str, pattern: str = "*") -> List[str]:
        try:
            base = Path(root).resolve()
            if not self._is_within_roots(str(base), self.fs_roots):
                return []
            results = []
            for p in base.rglob(pattern):
                if self._is_hidden(p):
                    continue
                rel = p.relative_to(base)
                results.append(str(rel))
            return results
        except Exception:
            return []

    def _is_hidden(self, path: Path) -> bool:
        try:
            if HAS_WIN32:
                attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
                if attrs != -1 and (attrs & 0x2):
                    return True
            return path.name.startswith(".")
        except Exception:
            return False


DEFAULT_POLICY = Policy()
DEFAULT_POLICY.add_rule("*", AccessLevel.NONE)
DEFAULT_POLICY.add_rule("work/**", AccessLevel.READ)
DEFAULT_POLICY.add_rule("work/**", AccessLevel.WRITE, media_override=True)


def load_policy_from_json(path: str) -> Policy:
    import json
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    policy = Policy()
    for rule_data in data.get("rules", []):
        policy.add_rule(
            rule_data["pattern"],
            AccessLevel(rule_data["level"]),
            rule_data.get("media_override", False),
        )
    return policy


def save_policy_to_json(policy: Policy, path: str):
    import json
    data = {
        "rules": [
            {"pattern": r.pattern, "level": r.level.value, "media_override": r.media_override}
            for r in policy.rules
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)