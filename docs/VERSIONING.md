# Versioning de ARIA OS

ARIA OS mantiene **una sola versión canónica**: `pyproject.toml` → `[project].version`.

Todo lo demás que muestra o lleva una versión es una **copia generada** por
`tools/sync_version.py` y vigilada por `tools/verify_version.py`. No edites esas
copias a mano: edita `pyproject.toml` y re-sincroniza.

## Por qué

Sin una fuente única, ARIA declaraba su versión en 14 sitios distintos
(`VERSION` en 2.1.0, `config.yaml` en 2.0.0, `v5/package.json` en 6.0.0,
`v6/axum-poc/Cargo.toml` en 0.1.0, literales `0.1.0-POC` en Rust, etc.). Eso
impossibilita tres cosas del roadmap:

- el **auto-updater** no puede saber qué versión tiene instalada ni cuál es la
  siguiente disponible;
- el **rolling release** no puede detectar un upgrade ni compararse con el canal;
- el **marketplace** no puede mostrar `instalado: 6.0.0`, y los **git tags** no
  significan nada.

## Fuente canónica

```toml
# pyproject.toml
[project]
name = "aura-os"
version = "6.0.0"
```

El formato exigido es **semver estricto `MAJOR.MINOR.PATCH`**: sin sufijo de
pre-release ni de build. `canonical_version()` rechaza cualquier otra cosa,
porque tanto el verificador TUF del updater como la comparación de canales del
rolling release necesitan un orden total y no ambiguo.

## Copias gestionadas

Definidas en un único lugar, `tools/version_manifest.py` (`MANAGED_TARGETS`).
Que el escritor y el verificador compartan la misma lista es deliberado: si cada
uno llevara la suya, divergirían y el gate aprobaría archivos que nadie escribe.

| Archivo | Qué contiene | Notas |
|---|---|---|
| `aria_version.py` | `ARIA_VERSION` | constante de runtime; la usan `setup.py` y los módulos Python |
| `ARIA_APP/__init__.py` | `__version__` | `ARIA_VERSION` se mantiene como alias |
| `VERSION` | texto plano | `6.0.0\n` |
| `v5/package.json` | `"version"` | shell Electron |
| `v6/axum-poc/Cargo.toml` | `[package] version` | solo la tabla `[package]`; las dependencias quedan intactas |
| `v6/axum-poc/src/version.rs` | `pub const ARIA_VERSION` | módulo nuevo; `core.rs` y `admin.rs` lo importan en vez de duplicar el literal |
| `aria-backend-axum/Cargo.toml` | `[package] version` | |
| `v6/airi_mobile/pubspec.yaml` | `version:` | el sufijo de build Flutter (`+1`) se preserva |
| `config.yaml` | `app.version` | solo el bloque `app:`; otros bloques con `version:` no se tocan |

### Copias congeladas (intencionadamente fuera de gestión)

| Ruta | Motivo |
|---|---|
| `aura-v5-tauri/` | shell Tauri, línea v5 — congelado en 5.0.0 |
| `v5.1/` | cliente Godot 4.7, línea v5.1 — congelado |
| `ARIA_v4/` | app desktop v4 heredada — congelada |
| `aria_autoconfig/__init__.py` | `__version__` del *paquete* de setup, no del producto |
| `.github/workflows/release.yml` | build legacy de imagen Alpine v2.1 — reemplazado por el pipeline v6 |
| `README.md`, `docs/*.md` | menciones narrativas; un reemplazo global destruiría referencias históricas y nombres de rama |

Están enumerados en `FROZEN_TARGETS` y `sync_version.py` los imprime en cada
ejecución, para que nadie los "arregle" sincronizándolos por error.

## Uso

```powershell
# Ver el estado (no escribe nada)
.venv\Scripts\python.exe tools\verify_version.py --verbose

# Ver qué cambiaría, sin escribir
.venv\Scripts\python.exe tools\sync_version.py --dry-run

# Sincronizar
.venv\Scripts\python.exe tools\sync_version.py

# Gate de CI: sale con 1 si algo quedó desfasado
.venv\Scripts\python.exe tools\sync_version.py --check
```

Códigos de salida (ambos scripts):

| Código | Significado |
|---|---|
| 0 | consistente |
| 1 | drift: hay copias desfasadas |
| 2 | error de configuración (falta `[project].version`, versión no semver, archivo gestionado ilegible) |

## Flujo de bump de versión

```powershell
# 1. Editar SOLO la fuente canónica
#    pyproject.toml: version = "6.0.0" -> "6.1.0"

# 2. Propagar
.venv\Scripts\python.exe tools\sync_version.py

# 3. Comprobar
.venv\Scripts\python.exe tools\verify_version.py
.venv\Scripts\python.exe -m pytest tests\test_version_sync.py -q

# 4. Commitear (stage explícito; el working tree tiene cambios ajenos)
git add pyproject.toml VERSION config.yaml setup.py aria_version.py `
        ARIA_APP/__init__.py tools/ tests/test_version_sync.py `
        .github/workflows/version-check.yml docs/VERSIONING.md `
        v5/package.json v6/axum-poc/Cargo.toml v6/axum-poc/src/version.rs `
        v6/axum-poc/src/lib.rs v6/axum-poc/src/core.rs v6/axum-poc/src/admin.rs `
        aria-backend-axum/Cargo.toml v6/airi_mobile/pubspec.yaml
git commit -m "chore: bump version to 6.1.0"

# 5. Tag anotado (el workflow comprueba que coincida con pyproject.toml)
git tag -a v6.1.0 -m "Release 6.1.0"

# 6. Push cuando se_pubique
git push origin feature/v6.0-axum-migration
git push origin v6.1.0
```

El commit **debe** incluir los archivos sincronizados. Si el bump y las copias
van en commits distintos, `version-check.yml` queda rojo en el intermedio, que es
exactamente el comportamiento buscado.

## CI

`.github/workflows/version-check.yml` corre en cada push y PR que toque
`pyproject.toml`, cualquier managed target o `tools/`. Hace tres cosas:

1. `tools/verify_version.py --verbose` — falla si alguna copia diverge.
2. `pytest tests/test_version_sync.py` — corre la suite de las herramientas.
3. En tags `v*`: compara el tag contra `pyproject.toml`.

El job es **estrictamente de solo lectura**: CI nunca escribe en el árbol. Un
gate que se auto-repara dejaría de ser un gate.

## Notas de implementación

- **Por qué copias generadas y no leer `pyproject.toml` en runtime.** ARIA se
  distribuye como binario congelado de PyInstaller, que no empaqueta
  `pyproject.toml`. El literal tiene que existir de verdad; lo que lo mantiene
  honesto es el gate.
- **Por qué un manifiesto compartido.** Ver arriba: sync y verify no pueden
  llevar listas propias.
- **Por qué `Cargo.toml` está anclado a `[package]`.** Un `re.sub` global
  reescribiría `axum = "0.7"` y rompería el build. Hay un test que lo cubre.
- **Por qué el sufijo `+N` de Flutter se preserva.** Para Flutter `+4` es el
  contador de build, no parte de la versión; borrarlo en cada bump sería una
  regresión silenciosa en el store.
- **Por qué `config.yaml` se ancla al bloque `app:`.** El archivo tiene otros
  bloques con claves `version:`; un reemplazo global tocaría de más.

## Qué falta para el rolling release

Esto resuelve la *identidad* de release, no la *distribución*. El auto-updater
necesita además (ver `docs/ROLLING_RELEASE_RESEARCH.md`):

- layout versionado en Windows (`versions\<semver>\` + puntero `current` +
  `aria-updater.exe` estable) — un upgrade in-place no permite rollback fiable;
- metadata firmada estilo TUF, con verificación fail-closed de expiración,
  monotonía de versión y firmas;
- canales `testing` / `stable` (hoy `aria_version.ARIA_CHANNEL` está fijado a
  `stable` y aún no se usa para selection de canal).
