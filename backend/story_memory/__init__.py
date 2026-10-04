from backend.story_memory.story_storage import StoryStorage
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.chapter_planner import ChapterPlanner
from backend.story_memory.consistency_checker import StoryConsistencyChecker
from backend.story_memory.story_context import StoryContextManager
from backend.story_memory.session_context import (
    set_session_context,
    get_session_context,
    clear_session_context,
    clear_all,
)
from backend.story_memory.versioning import (
    LiterarySnapshotEngine,
    get_snapshot_engine,
    set_engine_store_path,
)
from backend.story_memory.vault_backup import (
    DiscordVaultBackup,
    get_vault_backup,
    reset_vault_backup,
)
from backend.story_memory.vector_rag import (
    VectorRAGEngine,
    LocalEmbeddingVectorizer,
    get_vector_engine,
    set_engine_store_path as set_vector_store_path,
    reset_vector_engine,
)

__all__ = [
    "StoryStorage",
    "CharacterBible",
    "CanonTracker",
    "ChapterPlanner",
    "StoryConsistencyChecker",
    "StoryContextManager",
    "set_session_context",
    "get_session_context",
    "clear_session_context",
    "clear_all",
    "LiterarySnapshotEngine",
    "get_snapshot_engine",
    "set_engine_store_path",
    "DiscordVaultBackup",
    "get_vault_backup",
    "reset_vault_backup",
    "VectorRAGEngine",
    "LocalEmbeddingVectorizer",
    "get_vector_engine",
    "set_vector_store_path",
    "reset_vector_engine",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
