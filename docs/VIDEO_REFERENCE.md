# ARIA Video Reference Library

A USB stick that accumulates short-form video references, describes them, and
tells the autonomous agents which ones are worth watching.

```
download  →  describe  →  index  →  notify
yt-dlp      ffprobe      index   →  Discord
            ffmpeg       .json  →  aura.db
            whisper
            ollama
```

Everything lives in `aria_video_library/`. The HTTP face of the library is
`/api/videos/*` on the Axum backend, and the terminal face is `aria-videos`.

---

## Layout on the stick

```
<usb>/
  videos/
    reference-library/     the media files
    cache/                 transcripts, quarantined indexes
    index.json             searchable metadata
    index.lock             cross-process write lock
    index.json.bak         last known-good index
```

Filenames are `<source>_<slug>-<url-hash>_<YYYYMMDD>.<ext>`, e.g.
`instagram_ai-tools-episode-5-a1b2c3_20260930.mp4`. The source name keeps
provenance, the date lets two versions of the same topic coexist, and the hash is
derived from the canonical URL — titles collide ("AI Tools Episode 5" is a
routine reel title) and a collision would attribute one video's content to
another.

## Where the library looks

Resolved in this order by `aria_video_library.storage.resolve_usb_root`:

| Order | Source | Notes |
|-------|--------|-------|
| 1 | `--root` / constructor argument | always wins |
| 2 | `$ARIA_USB_PATH` | what a service or the Axum route sets |
| 3 | the only removable drive (Windows) | `GetLogicalDrives` + `GetDriveType` |
| 4 | `%LOCALAPPDATA%\ARIA\usb-library` or `~/.local/share/aria-usb` | **not a USB** |

The fallback exists so a laptop with no stick plugged in still works. It is
reported as `removable: false` in `aria-videos status` rather than pretending
to be the drive you meant. With **several** removable drives the auto-detect is
skipped and a warning is logged: guessing would create the library tree on a
camera card, so `ARIA_USB_PATH` chooses.

The Axum routes resolve the same way, with one addition: when neither
`ARIA_USB_PATH` nor the per-user fallback holds an index, every mounted drive
letter is checked for `videos/index.json` (read-only — nothing is created), so a
stick plugged in after boot is still found.

## External tools

| Tool | Used for | If missing |
|------|----------|-----------|
| `yt-dlp` | download + remote metadata | `ToolMissingError`, download refused |
| `ffprobe` | duration, resolution, fps, bitrate | `ExtractionError`; the file is not described |
| `ffmpeg` | scene-change keyframes | one `0:00 start (ffmpeg missing)` marker, no invented cuts |
| `whisper` | transcripts | empty transcript plus a `note` saying why |
| Ollama | summaries | the opening of the transcript, which is extractive and traceable |

None of them are Python dependencies. The runner uses `subprocess` with an argv
list and never a shell, and it is injectable, so the whole path is testable
offline (`tests/test_video_library.py`).

Check what is installed:

```powershell
.venv\Scripts\python.exe -m aria_video_library status
```

## CLI

```powershell
.venv\Scripts\python.exe -m aria_video_library status
.venv\Scripts\python.exe -m aria_video_library download "https://instagram.com/reel/…" --tag ai --agent agent-image-analysis
.venv\Scripts\python.exe -m aria_video_library search "agent tools"
.venv\Scripts\python.exe -m aria_video_library list --limit 10
.venv\Scripts\python.exe -m aria_video_library info instagram_ai-tools-episode-5-a1b2c3_20260930
.venv\Scripts\python.exe -m aria_video_library pending agent-image-analysis
.venv\Scripts\python.exe -m aria_video_library clean --drop-media
.venv\Scripts\python.exe -m aria_video_library rebuild
```

Every command takes `--json` for the agent loop. After `pip install -e .` the
entry point is `aria-videos`.

`clean` is the reclamation path: it removes yt-dlp leftovers, cached
transcripts for videos that are no longer indexed, and notifications older than
`--retention-days` (30). `--drop-media` additionally deletes media files that
are not in the index; indexed videos are never removed.

## HTTP API

All routes are behind the auth guard (`Bearer $ARIA_API_KEY`), like the rest of
the control plane.

| Route | Behaviour |
|-------|-----------|
| `GET /api/videos/list?limit=50` | indexed videos, newest first; `truncated` when the limit bites |
| `GET /api/videos/search?q=…&limit=20` | ranked hits; every term must match |
| `GET /api/videos/{id}` | one entry, or `404 unknown_video` |
| `POST /api/videos/download` | `202` + `job_id`; poll `GET /api/control/jobs/{id}` |

```json
POST /api/videos/download
{
  "url": "https://instagram.com/reel/…",
  "tags": ["ai", "tools"],
  "agent_type": "agent-image-analysis",
  "context": "reference for the orb",
  "transcribe": true
}
```

Why `202`: a download runs yt-dlp, ffprobe, ffmpeg and possibly Whisper. Running
it inline would hold the socket open for minutes and risk the client giving up
while the file lands anyway, so the route dispatches a detached job through the
same job machinery as `/api/control/restart`.

**Source allowlist.** Only `instagram.com`, `instagr.am`, `tiktok.com`,
`youtube.com`, `youtu.be`, `x.com` and `twitter.com` are accepted, because the
route dispatches a command that takes a URL. Widen it with
`ARIA_VIDEO_SOURCES=instagram.com,vimeo.com`. `file://`, `ftp://` and
non-web schemes are always rejected.

**Ranking.** Title (10) > tags (8) > summary (5) > agent notes (3) >
transcript (2), and every term of a multi-word query must match. The canonical
implementation is `aria_video_library.indexer.VideoIndexer.search`; the Rust
route mirrors those weights over the same `index.json` so a UI can filter
without spawning Python.

**Environment.** `ARIA_PYTHON` selects the interpreter the route dispatches
(plus whatever `PYTHONPATH` it inherits) and `ARIA_USB_PATH` the library root:

```powershell
$env:ARIA_PYTHON = "C:\Users\User\Downloads\AURA\.venv\Scripts\python.exe"
$env:PYTHONPATH  = "C:\Users\User\Downloads\AURA"
$env:ARIA_USB_PATH = "E:\"
```

## Agents

`aria_usb_agent.py` gained a `video_reference` task type, so the daemon can be
told to fetch a reference while the PC is idle:

```json
{"type": "video_reference",
 "payload": {"url": "https://instagram.com/reel/…",
             "tags": ["ai"], "agent_type": "agent-image-analysis",
             "context": "reference for the orb"}}
```

It returns `{"status": "success"|"failed", …}` in the task result — a bad URL
reports a failure instead of killing the polling loop.

An agent reads what is waiting for it:

```python
from aria_video_library import AgentNotifier

for notification in AgentNotifier().pending("agent-image-analysis"):
    library.search(notification.video_id)  # transcript, summary, keyframes
    AgentNotifier().mark_read("agent-image-analysis", notification.video_id)
```

Notifications live in `aura.db`, table `agents_video_references`
(`$ARIA_DB_PATH` overrides the path). Discord delivery is best-effort: a
webhook outage never means the agents miss the video, because the row is
written independently.

Webhook resolution: `$ARIA_VIDEO_WEBHOOK`, then `$DISCORD_WEBHOOK_URL`, then
`$DISCORD_WEBHOOK`. The URL is a credential and is never logged or written into
a message.

## Resilience

- **Atomic index writes.** Temp file plus `os.replace`, so an agent reading
  mid-write never sees a truncated `index.json`.
- **Corrupt index.** Moved to `index.json.corrupt-<stamp>` and rebuilt from the
  files on the stick. Recovered entries carry the truth that survives without
  ffprobe (name, size, mtime) and say so instead of inventing a duration.
- **Capacity check.** A download that would leave the stick without 512 MB of
  headroom is refused before it starts.
- **Re-downloads are free.** A video already on the stick is re-described from
  disk, not fetched again.
- **Failures are honest.** A missing tool, a rejected URL or an unreachable
  Ollama produces a message saying which, never a plausible-looking placeholder.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest tests\test_video_library.py
cd v6\axum-poc; cargo test --offline --lib videos
```
