# ARIA v7.0 — Fase 1: Investigación "ARIA como distro"

**Fecha:** 2026-09-29 · **Rama:** `feature/v6.0-axum-migration` · **Estado:** investigación cerrada, lista para diseño (Fase 2)

---

## 0. Resumen ejecutivo (TL;DR)

| Decisión | Recomendación |
|---|---|
| Modelo de release | **Fedora (canales testing/stable) + TUF (metadata firmada), NO Arch** |
| Versionado | **SemVer estricto con `ARIA_VERSION` única en `pyproject.toml`**, inyectada en build |
| "Breaking change" | Cambio de contrato de API/puerto, de schema DB, o de formato de `.env`/snapshot |
| Ramas | `main` = estable, `staging` =候选, `nightly` = bleeding edge |
| Auto-detección de problemas | Canary sintético + **gate de salud post-arranque** (no karma humano) |
| Rollback | **Imposible in-place en Windows** → exige layout versionado + bootstrapper estable |
| Marketplace | Índice firmado estilo **F-Droid index-v2** + `SHA256SUMS` + verificación local |
| UI | **Rich** (ya instalado) para TUI estática; **Textual** solo si se opta por instalarlo |
| Bloqueante real | **El repo no es todavía un producto único** (14 versiones declaradas, 4 sistemas de plugins, 5 CI) |

**El hallazgo más importante de la investigación:** el riesgo de ARIA v7.0 no está en escribir los 4 módulos nuevos, está en que el sistema que se quiere auto-actualizar **todavía no tiene identidad de release**. Un "auto-updater" sobre un producto sin `ARIA_VERSION` única, sin contrato de ports, y con 4 mecanismos de plugins coexistiendo no puede decidir "qué es v7.0" ni "si v7.0 rompió algo". La Fase 2 debe empezar por la **consolidación de identidad**, no por el marketplace.

---

## 1.1 Modelos de release — comparación

### Arch Linux (rolling puro)

| Aspecto | Comportamiento real |
|---|---|
| Cadencia | Diaria; `pacman -Syu` reconstruye **todos** los paquetes que dependen de una librería actualizada |
| Seguridad | Repos oficiales firmados; AUR (comunidad) es *build-from-source*, sin firma de binario |
| Rollback | `pacman -U <paquete-antiguo>` desde caché. **Descartado en Arch**: solo hay que ir hacia atrás en el *almacén de paquetes* |
| Regla dura | *"Partial upgrades are unsupported"*: prohibido `pacman -Sy <pkg>`. Actualización **siempre completa** |
| fricción humana | Obligation de leer las noticias de Arch antes de actualizar; hay paquetes que **"require manual intervention"** (p.ej. `virtualbox-ext-vnc >= 7.2.12-2`, 2026-07-21) |

**Por qué NO encaja con "el usuario no hace nada":**
1. El modelo Arch **transfiere el riesgo al humano** (leer noticias, resolver conflictos). El requisito de ARIA es explícitamente "0 intervención".
2. Arch **rechaza explícitamente los downgrades** como mecanismo de recuperación. El criterio de éxito de ARIA es "upgrade falla → rollback automático".
3. ARIA no tiene un repositorio de paquetes reconstruidos: tiene un *monorepo* con Python + Rust + Electron. El equivalente de "reconstruir los dependientes" no existe todavía.

**Lo que sí se conserva de Arch:** una **única fuente de verdad** de versión, y la regla de "actualización completa, nunca parcial" aplicada a la suite de tests + build de los tres runtimes.

### Fedora (stable + rawhide + Bodhi)

| Aspecto | Comportamiento real |
|---|---|
| Canales | `rawhide` → `updates-testing` → `updates` →Release estable |
| Publicación | **Bodhi** (escrito en Python) con *karma*: `+3`KARMA → estable; `-3` → unpush automático |
| Estados | `Pending` → `Testing` → `Testing/Batched` → `Stable`; agrupado en pushes de los martes |
| Rollback | `dnf history undo <id>` (una transacción) y `dnf history rollback <id>` (todo lo posterior) |
| Límite de rollback | Red Hat **no soporta** downgrade de paquetes base (`glibc`, `kernel`, `selinux-policy*`) |
| Historial | Persistido en **SQLite** (`/var/lib/dnf/history.sqlite`) — sobrevive reinicios |

**Lo que sí encaja con ARIA:**
1. Los **canales** son exactamente lo que el prompt pide (testing vs stable).
2. El **historial transaccional en SQLite** es la abstracción correcta para "aria snapshot restore": `aria history undo` / `aria history rollback`.
3. El rollback *de un producto entero* (no de un paquete base) sí está permitido y probado.

**Lo que NO copiamos:** el *karma humano* de Bodhi. ARIA lo sustituye por un **karma sintético** (sección 1.1.5).

### Ubuntu PPA / unattended-upgrades

| Aspecto | Comportamiento real |
|---|---|
| Concepto | Repo por mantenedor, con *pins* de versión explícitos |
| Actualización | `unattended-upgrades` con ventanas de mantenimiento y permitlist |
| Riesgo | Un PPA puede romper el sistema; la mitigación es *hold* de versión, no rollback |
| Soporte | Debian **deprecó formalmente** el rollback de upgrades: *"Rolling back an upgrade is not supported"* |

**Conclusión:** el modelo PPA sirve para *distribuir plugins/skills versionados* (que es donde de verdad hayHold pins), pero **no** para el core de ARIA.

### openSUSE Tumbleweed + Snapper (el modelo de recuperación)

| Aspecto | Comportamiento real |
|---|---|
| Release | Tumbleweed = rolling, con un gate de QA externo (openQA) que prueba **instancias reales**, no "tests" |
| Snapshots | **Snapper** crea pares `pre`/`post` alrededor de *cada* transacción de zypper y de cada módulo de YaST |
| Automático | Snapshots `hourly` vía timer systemd; `YaST` y `zypper` crean `pre`/`post` |
| Limpieza | Algoritmos `number` (conserva N) y `timeline` (conserva hourly/daily/monthly/yearly); `empty-pre-post` borra pares sin cambios |
| Rollback | Requiere Btrfs; crea un snapshot del estado actual **antes** de revertir; los snapshots de rollback heredan `Cleanup=number` para auto-borrarse |

**Este es el modelo de *recuperación* que mejor encaja.** Btrfs no aplica (Windows/NTFS), pero el *patrón* sí:
- par `pre`/`post` por transacción,
- snapshot del estado actual antes de revertir (para poder deshacer el rollback),
- limpieza por número con los snapshots de rollbackFormatted como los primeros en caer.

---

### 1.1.1–1.1.5 Las 5 preguntas del prompt, respondidas

**P1. ¿Qué modelo aplica mejor a ARIA?**
> **Híbrido Fedora + TUF**, con *recuperación* al estilo Snapper.
> - *Canales y gates:* Fedora (`staging` → `stable`), pero con gate automático en vez de karma humano.
> - *Seguridad del canal:* TUF (metadata firmada, expiración, protección anti-rollback), no solo `SHA256SUMS`.
> - *Recuperación:* Snapper (pre/post + rollback-guard), implementado sobre SQLite + git + copia de config, no sobre Btrfs.
> - *Regla de Arch que sí se hereda:* nunca upgrade parcial; `aria upgrade` siempre mueve core + plugins como una unidad transaccional.

**P2. ¿Cómo versionamos ARIA?**
> SemVer estricto, `MAJOR.MINOR.PATCH`, con `PRELEASE` (`7.0.0-rc.1`) y `BUILD` (`+sha.abc123`) para canaries.
> **Requisito previo bloqueante:* existe una única `ARIA_VERSION` en `pyproject.toml` (`[project].version`), y todos los puntos de build la leen de ahí. Ver §3.1: hoy hay **14 declaraciones de versión distintas** en el repo y la constante `ARIA_VERSION` **no existe**.

**P3. ¿Qué es un "breaking change" en ARIA?**
Concreto, no subjetivo. Son breaking:
- Cambio de puerto o de ruta de API (`/api/chat` → `/v2/chat`, 8000 → 8002).
- Cambio de schema SQLite que requiera migración destructiva, o unificación de tablas equivalentes. Caso real detectado en §2.4: `aura.db` mantiene **dos almacenes de memoria en paralelo** — `memories(key, value, kind, score, …)` declarada por `initializer.py` y usada por Python, y `semantic_memory(id, content, kind, vector_json, timestamp)` usada por `v6/axum-poc/src/memory.rs` (`MEMORY_TABLE = "semantic_memory"`, línea 26).
- Cambio de formato de `.env`, de `.aura/setup_state.json`, o del formato de snapshot.
- Cambio del contrato de `plugin.yaml` (campos requeridos) o del hook `run(params)`.
- Cambio de `ARIA_DB_PATH` por defecto o de la ruta de datos del usuario.
No son breaking: añadir campos opcionales, nuevas skills, nuevos checks, cambios de UI.

**P4. ¿Testing vs stable branches?**
> Tres ramas, con reglas duras:
> - `main` = **estable**. Solo recibe merges de `release/*`. Es la que se **taggea** y alimenta el canal `stable`.
> - `staging` = integración. Recibe merge de `main` + features maduras. Corre la **suite completa + canary sintético**. Si el canary pasa, `staging` → `release/*` → `main`.
> - `nightly` = bleeding edge, tag `v7.1.0-nightly.<sha>`, canal `testing`, opt-in explícito.
>
> Corrección al prompt: hoy el repo tiene 5 workflows con **triggers de rama inconsistentes** (`main`/`develop`, `master`/`develop`, `v*` tags) y `develop` **no existe**. Eso hay que unificar antes de poder hablar de canales.

**P5. ¿Cómo auto-detectamos problemas antes del deploy?**
> **Canary sintético** (el sustituto del karma de Bodhi) ejecutado en cada tag, antes de promover:
> 1. Instalar en un directorio limpio con el `bootstrapper` real (no un entorno de CI ideal).
> 2. Arrancar el stack completo (Axum 8002 + FastAPI si aplica + Ollama + autonomous daemon).
> 3. Ejecutar un guion de **sondeo sintético** ya existente en el repo: `/health`, `/api/system/status`, `chat` con prompt fijo, lectura+escritura en `aura.db`, `scan_ports()`.
> 4. Resultado: `KARMA = +1` por cada probe que pasa, `−1` por cada fallo. `KARMA ≥ 10` (10 probes) → promovible a `stable`. Un solo fallo de **probe CORE** (health, DB rw, chat) bloquea la promoción; los RUNTIME/OPTIONAL solo suman negativo.
> 5. Este es exactamente el modelo de `Tier` que ya existe en `aria_autoconfig/model.py` (CORE/RUNTIME/OPTIONAL) reutilizado tal cual.

---

## 1.2 Control Center — patrones de la industria

### YaST (openSUSE) — "centro de configuración con transacciones"
- Módulos independientes (network, partitioning, software, services, users).
- **El patrón clave no es la UI, es la atomicidad**: abrir un módulo YaST crea un snapshot `pre`, cerrarlo crea `post`. Si algo falla a mitad, se revierte el par.
- Contributor: Python, UI curses/clic.

### GNOME Settings — "search-first, modular, shortcuts"
- Diseño modular, no un monolito.
- **Búsqueda como navegación primaria**: el usuario no navega árbol, busca la acción.
- Atajos de teclado globales; casi todo tiene modo `--json`/CLI equivalente.
- `gnome-settings-daemon` **aplica el mismo patrón en background**: plugins de monitorización (impresoras, updates, tema).

### Cockpit (servidores) — "plugins con manifiesto, sin build step"
- Un paquete = un directorio con `manifest.json`. Se copia a `~/.local/share/cockpit/<nombre>/` y **se carga sin recompilar nada**.
- `manifest.json` declara: `version`, `require: {cockpit: "120"}` (compatibilidad mínima), `tools: {id: {label, path}}`, `keywords` (búsqueda), `conditions` (`path-exists`), `bridges` (procesos backend), `content-security-policy`.
- **Precedencia por directorio, gana el primero** (`$XDG_DATA_HOME` > `/usr/local/share` > `/usr/share`) → permite override de usuario sin tocar el sistema.
- Overrides: `<pkg>.override.json` con **JSON Merge Patch**.

**Aplicación a ARIA — el modelo Cockpit es exactamente el que necesita el marketplace:**
> Un plugin de ARIA = un directorio con `plugin.yaml` en `aria_plugins/`, **cargado por `importlib` sin instalar nada**, con `require: {aria: ">=7.0"}`, `conditions` (¿está `yt-dlp` instalado?), `keywords` (búsqueda del control center) y `permissions` (declaradas, no implícitas).
> Y el punto de entrada único se llama desde **los 4 sitios** que hoy hacen carga de plugins por su cuenta.

**Divergencia importante respecto al prompt:** el prompt propone `aria_control_center/web/app.py` con Flask. **`flask` NO está instalado en `.venv`**, y `fastapi` sí. Añadir Flask es una dependencia nueva sin justificación; la web ya existe en `v5/` (React/Electron). **Recomendación: el control center expone una API, no un servidor web nuevo.** Reutilizar el servidor Axum existente (`v6/axum-poc`) con rutas `/api/system/*` como única fuente de verdad, y que tanto la TUI como la UI Electron la consuman. Cero servicios nuevos, cero puertos nuevos.

---

## 1.3 Snapshots y auto-rollback

### Lo que existe y lo que no
| Capa | Estado | Veredicto |
|---|---|---|
| Git snapshots | Sí, pero **sin usar para releases**: no hay `git tag` de release, `CHANGELOG` está en v2.1.0 y el repo está en "v6.0" sin tag coherente | Reutilizable, falta disciplina |
| FS snapshots (Btrfs/LVM/ZFS) | No aplica (Windows/NTFS) | **Descartado** |
| DB snapshots | No hay ningún `.backup` de SQLite en el repo | **Reutilizable**: `sqlite3.Connection.backup()` es atómico y ya hay `sqlite3` importado |
| Config snapshots | No hay | **Reutilizable** vía el journal de `aria_autoconfig` (`.aura/setup_state.json` con payloads `undo`) |
| **App version snapshots** | **Inexistente** | **BLOQUEANTE — ver abajo** |

### El hallazgo crítico: en Windows **no se puede hacer rollback in-place**
Un instalador NSIS reescribe `$INSTDIR`. Cuando falla, el directorio anterior ya está destruido. Esto no es un problema de ARIA, es una limitación del modelo de despliegue.

**Solución obligatoria: layout versionado + bootstrapper estable** (el modelo de Chrome/Omaha y Squirrel):

```
%LOCALAPPDATA%\ARIA\
  aria-updater.exe          # bootstrapper: 200 KB, NUNCA se actualiza solo
  app\                       # datos del usuario (aura.db, .aura, logs, storage)
  versions\6.0.0\           # aplicación completa v6.0.0
  versions\7.0.0\           # aplicación completa v7.0.0
  current -> versions\7.0.0 # puntero (junction / symlink / fichero puntero)
  staging\                  # descarga en curso
  snapshots\pre-upgrade-7.0.0\
```

Secuencia transaccional:
1. `pre-upgrade-<v>` ← par de snapshot: git tag + `aura.db` backup + copia de `.env*` + lista de plugins + `ARIA_VERSION` actual.
2. Descargar v7.0.0 a `staging\`, verificar **firma + hash**, extraer a `versions\7.0.0\`.
3. **Cambiar el puntero** `current` a `versions\7.0.0\` (esto es instantáneo y reversible).
4. Reiniciar servicios.
5. **Gate de salud post-arranque**: el `aria-updater` arranca el binario con `--health-gate`; el proceso se auto-reporta sano en ≤90 s, o se auto-termina.
6. Si no se reporta sano: el updater **revierte el puntero** a `versions\6.0.0\`, restaura el snapshot de DB/config, reinicia, y marca la release como `blacklisted` (no se reintenta automáticamente). Es el equivalente a "unpkg -3 → unpush" de Bodhi.
7. Si sano: el updater persiste el estado en `setup_runs` y notifica a Discord.

Esto hace que **el rollback sea de segundos y no destructivo**, y da gratis el patrón Snapper (`pre`/`post`, snapshot antes de revertir, `Cleanup=number`).

### Limpieza (patrón Snapper)
- `number`: conservar las **N=3** últimas versiones en `versions\`.
- Las versiones creadas por rollback se marcan `Cleanup=number` → se borran primero.
- Nunca borrar la versión a la que apunta `current` ni la anterior a ella.

### Diff
`aria snapshot diff A B` compara: versión, tablas/filas de `aura.db` (conteos por tabla), diferencias en `.env` **por clave y no por valor** (redacción), y conjunto de plugins.

---

## 1.4 Plugin Marketplace (estilo F-Droid 2.0)

### Cómo funciona realmente F-Droid
- **Todo el repositorio es un índice firmado.** No es una API: es un fichero.
- `index-v1`: un **JAR firmado** que contiene `index-v1.json`. Se verifica el JAR y se extrae.
- `index-v2`: JSON plano con firma **GPG en `.asc` aparte** + SHA-256 de cada fichero (apps, iconos, screenshots).
- `entry.json` + `entry.jar` + `entry.json.asc`: **punto de entrada**, firmado, que lista los índices y diffs disponibles, con `timestamp`, `version`, `maxAge`.
- **Diff files**: desde index-v2 existen ficheros que **solo contienen los cambios** → actualizaciones incrementales.
- `signer-index.json`: índice de las huellas **SHA-256 de cada clave** usada para firmar cada paquete. Es la fuente de verdad para saber "quién firmó esto".
- `verification.f-droid.org`: **rebuilders independientes** que reconstruyen las releases oficiales y verifican que son *reproducible builds*. Por paquete: `<AppId>.json`, `<AppId>_<VersionCode>.apk.json`, y `verified.json` global.
- El cliente **elige espejo** basándose en la lista de espejos que viene en los metadatos firmados, según disponibilidad y frescura.
- Seguridad: repo definido por **clave de firma única**; HTTPS obligatorio (HTTP redirige); clave pública del índice **compilada dentro del cliente**.

### Aplicación a ARIA

**Índice (espejo de `index-v2.json`), firmado y versionado:**
```
aria_repo/
  entry.json          # {version, timestamp, maxAge, index:{name,sha256,size,numPackages}, diffs:{...}}
  entry.json.asc      # firma GPG/Ed25519
  index-v2.json       # catálogo completo
  diff/<ts>.json      # solo cambios desde <ts>
  signer-index.json   # {plugin_id: sha256_de_la_clave_que_lo_firmo}
  SHA256SUMS          # hash de cada .tar.gz
```

**Metadatos de plugin (`plugin.yaml`)** —Joyyan adaptando el prompt:
```yaml
schema_version: 1
name: skill-yt-summarizer
version: 1.0.0
aria_min_version: ">=7.0"     # obligatorio: permite gate por canal
aria_max_version: "<8.0"       # opcional: declara incompatibilidad conocida
description: Resume vídeos de YouTube
author: raidenia3-oss
license: MIT
homepage: https://github.com/...
entry_point: src.plugin:Plugin     # en vez de setup.py: evita ejecución arbitraria
keywords: [video, youtube, resumen]  # alimenta la búsqueda del control center
conditions:                          # equivalente a conditions de Cockpit
  - path-exists: .venv/Scripts/yt-dlp.exe
dependencies:
  python: ["yt-dlp>=2024.1"]
permissions: [network.outbound, fs.read.user]   # declaradas, no implícitas
hooks: [on_chat, on_voice]
anti_features: []
sha256: "..."
signed_by: "..."
```

**Deliberadamente distinto al prompt:** el prompt propone `setup.py` dentro del plugin. Eso es ejecución de código arbitrario en tiempo de instalación y es exactamente lo que F-Droid evita. ARIA usa **`entry_point: módulo:símbolo`** (estilo `console_scripts`), que además es lo que ya hace `backend/plugin_manager.py` con `entry_point="plugin_execute"`. La instalación **nunca ejecuta código del plugin**.

**Verificación en cliente (obligatoria, fail-closed):**
1. Firma de `entry.json` válida contra la clave pública **compilada en el cliente** (nunca descargada del mismo sitio).
2. `timestamp` dentro de `maxAge`; si no, → **freeze attack** → abortar.
3. `index.version` **estrictamente mayor** que el stored local; si no, → **rollback attack** → abortar. *Este es el error clásico de go-tuf CVE-2022-29173; hay que implementarlo bien desde el día 1.*
4. SHA-256 del `.tar.gz` coincide con el del índice firmado.
5. `signer-index.json` dice que la clave que firmó este plugin es la esperada.
6. Solo entonces: extraer a `aria_plugins/<name>/<version>/` y **añadir un symlink/junction** `aria_plugins/<name>/current` (mismo patrón de layout versionado, permite downgrade instantáneo).

**Sobre firma de binarios Windows:** `electron-builder` hoy tiene `forceCodeSigning: false` y sin `publisherName` **fail-open** (skipea la verificación de firma, con aviso; en v28 pasó a fail-closed). Como `nacl` (PyNaCl) **sí está instalado** en `.venv` y `cryptography` también, ARIA puede hacer Ed25519 desde Python sin dependencias nuevas. **Recomendación: firmar los metadatos con Ed25519 (POC, sin herramientas) y los binarios con Authenticode cuando haya certificado**; SHA-256 siempre, como red de seguridad.

**Resolución de dependencias:** `pip` ya resuelve; NO reimplementar un solver. Reutilizar `aria_autoconfig/installer.py` con `IMPORT_NAMES` y `plan()` existentes, y añadir resolución de conflictos = *detectar y reportar*, nunca forzar (regla ya establecida en el código actual).

---

## 1.5 UI moderna

### Textual vs Rich (relevante: **`textual` NO está instalado, `rich` SÍ**)

| | Rich | Textual |
|---|---|---|
| Estado | **Instalado en `.venv`** | No instalado (última 8.2.8, Jun 2026) |
| Naturaleza | Toolkit de render (Panel, Table, Live, Tree) | Framework de app (App, Screens, Widgets, CSS/TCSS) |
| Modelo | Imperativo, `console.print` / `Live` | Reactivo, mensajes, `set_interval` |
| Ideal | Salida estática, informes, progreso, `--json` alterno | Dashboard interactivo con navegación por teclado |
| Coste | 0 (ya presente) | +1 dependencia (731 KB wheel) |

**Recomendación en dos fases:**
- **Fase 1 (`aria status` sin argumentos): `rich` puro.** `Live` + `Table` + `Panel` para el dashboard. Cero dependencias nuevas, funciona hoy, testable con `Console(file=io.StringIO())` — lo que ya hace el `Reporter` de `aria_autoconfig/report.py`. Reutilizar sus helpers en vez de reescribir.
- **Fase 2 (interactividad real: paneles, paleta de comandos, logs en vivo): `textual`**, añadiéndolo como dependencia OPTIONAL (ya existe el tier OPTIONAL en el instalador) y con fallback automático a Rich si no está.

**Paleta Cosmic** (la del prompt) es válida, pero hay que corregir un punto: los colores de las variables del prompt están mezclados con un tema anterior del proyecto. El AGENTS/memoria del proyecto fija `#0a0e27 → #141e3f` como fondo de la UI v4. **Decisión: definir los tokens una sola vez en `aria_ui/theme.py`** (pyproject-level, importable desde Python) y exportarlos a CSS (React) y a TCSS (Textual) desde esa misma fuente. Un solo lugar, tres consumidores. Sin eso, la "UI moderna" se degrada en 6 meses a 6 colores distintos.

**Tipografías:** `JetBrains Mono` / `Inter` son correctas para lo visual, pero el dashboard TUI **debe** usar la fuente del terminal (`$TERM`) — no se puede empaquetar una fuente en un TUI.

---

## 2. Auditoría del estado real de ARIA (previa al diseño)

Esto **no** estaba en el prompt y condiciona toda la Fase 2.

### 2.1 Identidad de release: no existe (BLOQUEANTE)
- **14 declaraciones de versión distintas**: `VERSION`=2.1.0, `setup.py`=2.1.0, `config.yaml`=2.0.0, `build_system.py`=30.0.0, `windows_store/build_store_package.py`=1.2.0.0, `ARIA_v4/.../constants.py`=4.0.0, `main.py`=0.1.0, `aria_autoconfig`=1.0.0, `v5/package.json`=6.0.0, `v6/axum-poc/Cargo.toml`=0.1.0, `aria-backend-axum/Cargo.toml`=6.0.0, `aura-v5-tauri`=5.0.0 (×2), `desktop/package.json`=1.0.0, `frontend/package.json`=0.1.0, `LongMemory`=1.0.0, `extensions/aura-copilot`=1.0.0.
- `CHANGELOG.md` está en v2.1.0.
- **`git tag --list` devuelve 0 tags**: no hay ni un solo tag de release en todo el repositorio, y hay commits que ya dicen "zero-touch ARIA auto-configuration (66 tests passing)".
- La constante **`ARIA_VERSION` no existe en el repo**.
- `pyproject.toml` **no tiene sección `[project]`** → no puede ser la fuente de verdad todavía.
- `release.yml` y `electron-builder.yml` llevan literales de versión hardcodeados ("AURA OS v2.1.0", "ARIA OS v6.0").
→ Sin esto, `aria version` no puede responder, y `aria upgrade` no puede comparar.

### 2.2 Contrato de servicios: hay tres backends y una URL desalineada
- 8000 FastAPI v4 (`ARIA_APP/backend/app.py`), 8001 FastAPI legado, 8002 Axum v6.
- `aria_autonomous.py` apunta a `BASE_URL = http://127.0.0.1:8002` (env-overridable), **pero `v6/axum-poc/src/daemon.rs` sigue llamando a `http://127.0.0.1:8000/api/chat`**. El daemon y su cliente no hablan con el mismo backend.
- `PUBLIC_PATHS = ["/", "/health", "/ws"]` en `lib.rs` — superficie pública a revisar antes de exponer más.
- 4 sistemas de arranque distintos: `v5/electron/main.ts` (spawn), `main_launcher.py`, `start_aura_ecosystem.py`, `aria-os/scripts/*.ps1`, más `install_autostart.py` / `ARIA_APP/auto_start.py` registrando HKCU Run.
- **No hay gestor de procesos** (sin systemd/pm2/supervisor). Windows: falta un equivalente a un service manager.
→ **PR-0 del diseño: un "servicio" declarado con nombre, binario, puerto, healthcheck y política de reinicio, en un único registro declarativo.** Todo lo demás (Electron, TUI, control center, updater) lo consume.

### 2.3 Sistemas de plugins: hay 4 y ninguno tiene marketplace
| Sistema | Carga | Manifiesto | Sandbox | Notas |
|---|---|---|---|---|
| `ARIA_APP/backend/skills/registry.py` (382 L) | **imports estáticos hardcodeados** (líneas 20-39, 151-178) | ✗ | ✗ | Añadir skill = editar el registry |
| `ARIA_APP/backend/plugins/manager.py` | `glob("*.py")` | ✗ | ✗ | Solo `example_plugin.py` |
| `aura_plugin_system.py` (raíz) | `glob` en `./plugins` | `config.json` | ✗ | 4 plugins |
| `backend/plugin_manager.py` | `PluginManifest` dataclass | ✗ | **✓ sandbox real** (`ALLOWED_MODULES`, `SAFE_BUILTINS`) | El único con sandbox |
| `backend/plugins/*/plugin.yaml` (7 paquetes) | — | **✓ YAML** | ✗ | **Solo el manifiesto existe, falta el código** |
| `backend/marketplace/marketplace_manager.py` | — | — | — | Marketplace **de contenido** (fanfic/datasets), no de plugins |

Bug conocido: `PluginManager.register_custom_skill()` llama a `registry.register_skill()`, que **no existe** en `SkillRegistry` → ruta rota.
→ **PR-0: unificar en UN cargador de plugins con manifiesto `plugin.yaml` + sandbox**, deprecando los otros 4 por deprecación progressive (sin borrarlos en el mismo commit, para no romper 25 skills en producción).

### 2.4 Base de datos: 9 ficheros `.db`, schema divergente
- `aura.db` (raíz) tiene **33 tablas**; la define `initializer.py` con 6 tablas CORE.
- **Dos almacenes de memoria en paralelo**, no un conflicto de schema: `memories(id, key, value, kind, score, created_at, updated_at)` — declarada CORE por `initializer.py`, **0 filas** — frente a `semantic_memory(id, content, kind, vector_json, timestamp)` — **3 filas**, y es la que realmente usa el backend Rust (`v6/axum-poc/src/memory.rs:26`). Ambas conviven en el mismo `aura.db`, y solo la segunda tiene escritura real. Python y Rust no comparten el mismo modelo de memoria.
- `LongMemory/longmemory.db` tiene 16 tablas y su propio esquema (`migrations`, `memory_contracts`, `sketch_operations`…) → eso ya es un sistema de **migraciones** escrito a mano.
- Copias duplicadas de DB en `aura-v5-tauri/`, `aura-v5-tauri-webgpu/`, `archives/`, `backend/`, `data/`, `test.db`.
→ **PR-0: un único `aura.db` canónico + tabla `schema_migrations(version, applied_at, checksum)`.** Todo lo demás apunta a él por `ARIA_DB_PATH` (que Axum ya respeta).

### 2.5 CI/CD: 5 workflows inconsistentes
- `ci.yml` → `main`/`develop`; `ci-cd.yml` → `master`/`develop`; `tests.yml` → `main`/`master`; `ci-docker.yml` y `release.yml` → tags `v*`.
- **`develop` y `master` no existen como ramas** → 2 de los 5 workflows nunca se ejecutan.
- `release.yml` invoca `aura-os/distro-builder/build-distro-hardened.sh` (distro Linux) y `mkdocs build` **sin `mkdocs.yml` en la raíz** → job de docs roto.
- Sin caché de pip, sin matriz de versiones de Python, sin `rust` en el job de lint.
- `pyproject.toml` `testpaths` incluye `ame_backend/tests`, **que no existe** → colección inválida.
→ **PR-0: un solo workflow con matriz + un job `release` con `workflow_dispatch` + tag. Nada de `master`/`develop` fantasma.**

### 2.6 Tests: 2000+ tests, ~50% boilerplate
- `tests/` tiene 150 ficheros de test, ~2020 funciones `test_`. Aproximadamente **la mitad** siguen el patrón `test_blockNN.py` / `test_blockNN_kilo.py` (bloques 51→104) → tests generados, nolouyAssert tests unitarios con señal.
- **Único test de integración de backend:** `tests/integration/test_backend_api.py`.
- ~20 `test_*.py` sueltos en la raíz fuera de `tests/`.
- Logs de ejecución acumulados en la raíz (`pytest_global.log`, `suite_b95.txt`, `tests_result.txt`…).
→ Un canary sintético que dependa de "toda la suite verde" **no es fiable hoy**. El gate debe usar probes **explícitos y nombrados**, no "la suite entera". Por eso el gate de §1.1.5 es una lista cerrada de 10 probes, no `pytest -q`.

### 2.7 Higiene y secretos
- `requirements.txt` fija `ccxt==4.0.0`, **versión que no existe en PyPI** (empieza en 4.0.50) → instalación **permanentemente fallida**. Clasificado correctamente como permanent error por el motor de setup.
- **110 ficheros `.pem` versionados** en git (bajo `docs/AURA_OS_Workspace/`) — `.gitignore` no les afecta porque ya están trackeados. **Auditoría de credenciales requerida.**
- `pyproject.toml` no declara `[project]`, así que `pip install -e .` no funciona.
- `.aura/setup_state.json` y `.aura/setup_report.json` están **untracked** (bien, pero no ignorados).
- `docs/` tiene 167 `.md`; la raíz tiene ~150 ficheros de log/txt de depuración y una carpeta corrupta llamada `CUsersUserDownloadsAURA*` (de un path Linux mal pegado) con 25 ficheros + 5 carpetas.
- `.venv` no tiene `ruff` ni `flake8`, pero `ci.yml` corre `flake8` y `black` → **el CI fallaría**.

---

## 3. Conclusiones para la Fase 2 (arquitectura)

### 3.1 Orden de trabajo corregido (el prompt va en orden equivocado)

El prompt empieza por el marketplace. **El orden correcto es:**

| PR | Contenido | Por qué primero |
|---|---|---|
| **PR-0a** | `pyproject.toml [project]` con `version` = **única** `ARIA_VERSION`; script `tools/sync_version.py` que la inyecta en los 14 sitios; CI falla si divergen | Sin identidad no hay upgrade |
| **PR-0b** | Registro declarativo de **servicios** (nombre, binario, puerto, health, política de restart). Unificar Puertos (8000 vs 8002) y arreglar `daemon.rs` → 8002 | Sin contrato no hay health gate |
| **PR-0c** | `schema_migrations` + unificar `memories` Python↔Rust. Un solo `aura.db` | Sin schema común no hay snapshot fiable |
| **PR-0d** | Unificar CI a un workflow; arreglar `testpaths`; probes sintéticos nombrados | Sin gate fiable no hay promoción automática |
| **PR-1** | `aria_snapshot/` (pre/post, backup SQLite, config, validate) — **sin layout versionado aún** | Base del rollback |
| **PR-2** | `aria_control_center/` (TUI con **rich**, API sobre Axum) | Visibilidad antes de automatizar |
| **PR-3** | Unificar plugins (manifiesto + sandbox), **deprecando** los otros 4 | Requisito del marketplace |
| **PR-4** | `aria_marketplace/` (índice firmado Ed25519, verificación fail-closed) | Solo tiene sentido con PR-3 |
| **PR-5** | `aria_upgrade.py` + **layout versionado + bootstrapper** | Lo más caro; depende de todo lo anterior |
| **PR-6** | Layout versionado + updater con health gate y auto-rollback | Fase final |

### 3.2 Riesgos que **deben** registrarse como riesgo, no como feature

1. **Auto-actualización sin intervención en Windows con datos de usuario** (`aura.db` 602 KB con 33 tablas, token de Discord, 3.2 GB de modelos en `data/models/`). El health gate + rollback lo hace seguro, pero **el primer test debe ser en un entorno desechable, nunca en la instalación real**.
2. **Rollback de schema DB**: si v7.0.0 aplica una migración irreversible y luego falla el gate, el snapshot `.backup` de SQLite **sí** restaura los datos, pero el binario v6.0.0 debe seguir siendo compatible con el schema restaurado. **Regla: las migraciones deben ser siempre reversibles durante N releases, o la promoción de una major exige uninstall limpio.**
3. **`data/models/` = 3.2 GB**: nunca debe formar parte del snapshot. Solo el **manifiesto** (hashes), no los bytes.
4. **Cero tests fiables hoy** (§2.6) → la primera versión del gate debe ser *conservadora*: promotion solo si `KARMA >= 10` **y** 0 fallos CORE **y** ≥2 canariesdeanteriores sin incidentes. Después se puede relajar.
5. **El requirement de "usuario no hace nada" choca con los defaults de todas las distribuciones studied**. Ninguna 更新 automática de Fedora/Arch/openSUSE es 100% desatendida. La vía honesta es: **automatizar con gate+rollback, y declarar explícitamente qué NO se automatiza** (migraciones major, cambios de credenciales). Es preferible decir "esto requiere tu atención" que romper en silencio.

---

## 4. Fuentes consultadas

- ArchWiki — *System maintenance* (partial upgrades unsupported, `checkupdates`): `https://wiki.archlinux.org/title/System_maintenance`
- ArchWiki — *Pacman* (`--asdeps`, `IgnorePkg`, caché de paquetes para downgrade)
- Red Hat Docs — *Managing package management history* (`dnf history undo|rollback`, límites de downgrade en `glibc`/`kernel`/`selinux-policy*`): `https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_software_with_the_dnf_tool/`
- Fedora Project Wiki — *Bodhi* (estados, karma +3/-3, Testing/Batched)
- Debian Wiki — *RollbackUpdate* ("rolling back an upgrade is not supported")
- openSUSE/SUSE Docs — *Snapper* (tipos `pre`/`post`/`single`, `Cleanup=number|timeline|empty-pre-post`, `rollback` requiere Btrfs, snapshot previo a revertir): `https://manpages.opensuse.org/Tumbleweed/snapper/snapper.8.en.html`
- F-Droid — *All our APIs* (`entry.json`/`entry.jar`/`.asc`, `index-v1.jar` vs `index-v2.json`, diffs, `signer-index.json`): `https://f-droid.org/docs/All_our_APIs`
- F-Droid — *Security Model* (repo definido por clave, SHA-256 en index-v2, metadatos firmados con timestamp+expiry, clave pública compilada en el cliente, selección de espejo)
- F-Droid — *Release Channels and Signing Keys* (flujo de verificación de clave de admin)
- Cockpit Docs — *Packages* (`manifest.json`, `require`, `tools`, `keywords`, `conditions`, `bridges`, precedencia de `$XDG_DATA_DIRS`, `*.override.json` con JSON Merge Patch): `https://docs.cockpit-project.org/cockpit-guide/latest/guide/packages.html`
- Cockpit — *Creating Plugins for the Cockpit User Interface* (paquete = directorio + manifiesto, sin build step)
- GNOME Docs / man pages — `gnome-settings-daemon` (arquitectura de plugins en background)
- TUF Specification — *tuf-spec.md* (root rotation con doble threshold, check anti-rollback `version == N+1`, anti-freeze por expiración): `https://github.com/theupdateframework/specification/blob/master/tuf-spec.md`
- python-tuf tests (casos de freeze/rollback attack, expiración de `timestamp`)
- NVD — **CVE-2022-29173** (go-tuf: checks de rollback incompletos →적이 cliente instalado software antiguo). Referencia directa para el requisito "fail-closed" del verificador.
- Electron Docs — *auto-updater* (detección automática de formato, MSIX vs NSIS vs Squirrel)
- electron-builder Docs — *Auto Update* (`app-update.yml` con `sha512`, `stagingPercentage` para **staged rollouts**, Squirrel.Windows no soportado en modo simplificado, `verifyUpdateCodeSignature`)
- electron-builder `NsisUpdater.ts` — fail-open actual sin `publisherName`, fail-closed en v28
- Textual/Rich — PyPI `textual` 8.2.8 (2026-06-30), docs de arquitectura (App/Screens/Widgets/Reactive/Workers, TCSS), Real Python — *The Python Rich Package* (`Live` para tablas dinámicas)
- Auditoría local del repo: `git ls-files`, 10 inspección de submódulos (versión, CI, plugins, DB, puertos, tests, docs)
