"""Guardarrail: ningun fichero TRACKEADO por git puede contener un secreto.

Existe porque ya paso dos veces: un PAT en
`ARIA_APP/.github_webhook_config.json` y otro en `.kilo/kilo.json:56`.

Borrar el secreto del HEAD no sirve de nada: si esta en un commit, ya se
publico y hay que ROTARLO en GitHub. La unica defensa real es que el commit
llegue a existir. Este test lee el indice de git y falla antes de que eso pase.

Los valores jamas se imprimen: solo fichero, linea y nombre del patron.
"""

from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Permitido sin mas: se comprobo que el valor es un placeholder obvious.
ALLOWLIST: dict[str, str] = {
    "v6/DISCORD_BOT_GUIDE.md": "documentacion: el valor es 'ghp_xxxxxxxxxxxx'",
}

# Deuda CONOCIDA: hay valores con forma de credencial en ficheros trackeados.
# No se allowlistan para que el test siga verde: se catalogan para que no crezca
# en silencio y quede pendiente de revisar, ROTAR y mover a variable de entorno.
KNOWN_EXPOSED: dict[str, str] = {
    "deploy.sh": "claves de OpenRouter/Gemini/Groq/AURA en `flyctl secrets set`",
    "setup.ps1": "AURA_API_KEY metida en el script de setup",
    "railway_deploy.py": "FIREBASE_API_KEY metida en el codigo",
    "scripts/build-mobile-apk.sh": "KEYSTORE_PASSWORD / KEY_PASSWORD por defecto",
    "tools/scripts/build-mobile-apk.sh": "copia del anterior",
    "integrations/n8n_workflows/aura_news_workflow.json": "api_key/apiKey en el workflow de n8n",
    "docs/API.md": "access_token en la documentacion",
    "docs/CONTROL_CENTER.md": "ARIA_API_KEY en la documentacion",
    "aura-os/API_DOCUMENTATION.md": "password en documentacion de API",
    ".kilo/skills/secrets-vault-manager/SKILL.md": "password de ejemplo en la skill",
    ".kilo/skills/secrets-vault-manager/references/vault_patterns.md": "password de ejemplo",
    "tests/test_block61.py": "fixture de test",
}

SKIP_DIRS = {
    ".git", ".venv", "node_modules", "target", "__pycache__", "dist", "build",
    "release", ".gradle", ".godot",
}
SKIP_DIR_PREFIXES = ("docs/AURA_OS_Workspace",)

BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".7z", ".exe", ".dll", ".so", ".dylib", ".bin", ".dat", ".db", ".sqlite",
    ".sqlite3", ".pdb", ".woff", ".woff2", ".ttf", ".mp3", ".mp4", ".wav",
    ".pth", ".jar", ".class", ".o", ".obj", ".a", ".rlib", ".whl",
}
MAX_BYTES = 2 * 1024 * 1024

# Los prefijos de GitHub, OpenAI o Anthropic tienen longitudes conocidas, asi
# que un placeholder corto ("sk-xxx") no dispara la alarma por accidente.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("github_pat", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("github_classic", re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}")),
    ("anthropic", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai", re.compile(r"sk-(?!ant-)[A-Za-z0-9]{20,}")),
    ("aws_access_key", re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}")),
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("slack", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("discord_bot", re.compile(
        r"\b[MNO][A-Za-z0-9_\-]{23,}\.[A-Za-z0-9_\-]{6}\.[A-Za-z0-9_\-]{27,}"
    )),
    ("private_key_block", re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"
    )),
    ("generic_secret_literal", re.compile(
        r"""(?ix)
        (?:api[_-]?key|access[_-]?token|auth[_-]?token|personal_access_token
          |secret[_-]?key|client[_-]?secret|password|bearer)
        ["']?\s*[:=]\s*["']([^"'\s]{12,})["']
        """
    )),
]

PLACEHOLDER_HINTS = (
    # ingles
    "example", "your_", "your-", "changeme", "placeholder", "redacted",
    "xxxx", "notareal", "dummy", "test", "fake", "sample",
    # espanol: en este repo los placeholders se escriben en castellano
    "tu-", "tu_", "cambia", "cambiar", "reemplaza", "reemplazar",
    "produccion", "secreto", "aquí", "aqui", "pendiente",
)

# Envuelve referencias de configuracion y variables de shell, no credenciales:
#   {file:.kilo/github_token}, ${KEYSTORE_PASSWORD}, ${VAR:-default}
_REFERENCE = re.compile(r"^\{.*\}$")


def _entropy(value: str) -> float:
    """Bits por caracter. Una frase tiene entropia baja; un token, alta."""
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(value)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _is_placeholder(value: str) -> bool:
    if _REFERENCE.match(value):
        return True
    low = value.lower()
    if any(hint in low for hint in PLACEHOLDER_HINTS):
        return True
    body = re.sub(r"^(ghp|gho|ghu|ghs|ghr|github_pat|sk|xoxb|xoxa)_", "", value)
    # Un valor de un solo caracter repetido ("xxxxxxxxxxxx") es un ejemplo.
    if len(set(body)) <= 2 and len(body) >= 8:
        return True
    # Una frase en palabras simples ("tu-secreto-super-seguro") tiene entropia
    # baja; cualquier credencial real la tiene alta.
    if _entropy(body) < 3.2:
        return True
    return False


def _tracked_files() -> list[str]:
    # Sin `text=True`: en Windows la salida de git viene en la codificacion de
    # la consola (cp1252) y hay rutas con acentos que rompen el decode.
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO, capture_output=True, check=True,
    ).stdout.decode("utf-8", errors="surrogateescape")
    return [p for p in out.split("\0") if p]


def _read(rel: str) -> str | None:
    path = REPO / rel
    if path.suffix.lower() in BINARY_SUFFIXES:
        return None
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:4096]:
        return None
    return data.decode("utf-8", errors="ignore")


def _scan(rel: str) -> list[str]:
    text = _read(rel)
    if text is None:
        return []
    hits: list[str] = []
    for name, pattern in PATTERNS:
        for match in pattern.finditer(text):
            whole = match.group(0)
            value = match.group(1) if name == "generic_secret_literal" else whole
            if _is_placeholder(value):
                continue
            line = text.count("\n", 0, match.start()) + 1
            hits.append(f"{rel}:{line}  [{name}]")
    return hits


def _skipped(rel: str) -> bool:
    if any(part in SKIP_DIRS for part in Path(rel).parts):
        return True
    return any(rel.startswith(prefix) for prefix in SKIP_DIR_PREFIXES)


def test_no_tracked_file_contains_a_credential_literal() -> None:
    """Falla si aparece una credencial que NO estaba en el catalogo conocido."""
    findings: list[str] = []
    for rel in _tracked_files():
        if rel in ALLOWLIST or _skipped(rel):
            continue
        hits = _scan(rel)
        if rel in KNOWN_EXPOSED:
            # Deuda declarada: se registra, pero no rompe el gate. Si el fichero
            # se limpia hay que quitarlo de KNOWN_EXPOSED (test de abajo).
            findings.extend(f"deuda: {h}" for h in hits)
            continue
        findings.extend(hits)

    nuevas = [f for f in findings if not f.startswith("deuda: ")]
    assert not nuevas, (
        "Credenciales NUEVAS en ficheros TRACKEADOS. Borrarlas del HEAD no las "
        "borra del historico: hay que ROTARLAS en GitHub y rehacer el commit.\n"
        "  " + "\n  ".join(nuevas)
    )


def test_the_token_file_is_not_tracked() -> None:
    """`.kilo/github_token` es donde vive el PAT: jamas puede estar en git."""
    tracked = set(_tracked_files())
    assert ".kilo/github_token" not in tracked, (
        ".kilo/github_token esta TRACKEADO: el PAT del MCP seria publico."
    )

    ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".kilo/github_token"],
        cwd=REPO, capture_output=True,
    ).returncode == 0
    assert ignored, ".kilo/github_token debe estar en .gitignore"


def test_the_mcp_token_is_referenced_not_inlined() -> None:
    """.kilo/kilo.json debe LEER el token, nunca escribirlo dentro."""
    config_path = REPO / ".kilo" / "kilo.json"
    config = config_path.read_text(encoding="utf-8")
    assert "{file:.kilo/github_token}" in config, (
        "kilo.json deberia leer el PAT con {file:.kilo/github_token}"
    )
    assert not _scan(".kilo/kilo.json"), (
        "kilo.json tiene una credencial escrita dentro"
    )


def test_known_exposed_debt_is_still_accurate() -> None:
    """Cada entrada de KNOWN_EXPOSED debe seguir teniendo algo que rotar.

    Si alguien limpia un fichero, el test obliga a quitarlo del catalogo: asi
    la lista no se convierte en un cajon donde todo acaba permitida.
    """
    stale: list[str] = []
    for rel in KNOWN_EXPOSED:
        if not _scan(rel):
            stale.append(rel)
    assert not stale, (
        "Estos ficheros ya NO tienen credenciales pero siguen en "
        f"KNOWN_EXPOSED: {stale}. Quitalos del catalogo."
    )


def test_allowlist_entries_still_look_like_placeholders() -> None:
    """Si un fichero de la allowlist recibe un token real, el test se cae."""
    for rel, reason in ALLOWLIST.items():
        text = _read(rel)
        if text is None:
            continue
        for name, pattern in PATTERNS:
            for match in pattern.finditer(text):
                whole = match.group(0)
                value = match.group(1) if name == "generic_secret_literal" else whole
                if _is_placeholder(value):
                    continue
                line = text.count("\n", 0, match.start()) + 1
                raise AssertionError(
                    f"{rel}:{line} [{name}] estaba en la allowlist como "
                    f"'{reason}', pero ya no es un placeholder. Revoca ese "
                    "token y quita el fichero de la allowlist."
                )