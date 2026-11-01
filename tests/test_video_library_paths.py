"""Tests de contención de paths para la video library (paso G).

Toda construcción de ruta bajo videos/reference-library/ pasa por
VideoLibraryStorage.contain(), que RECHAZA el escape (no lo colapsa con
Path(name).name). Cubre: traversal absoluto, traversal relativo, nombre
reservado de Windows y symlink (skip fuera de posix).
"""
from __future__ import annotations

import os

import pytest

from aria_video_library.errors import StorageError
from aria_video_library.storage import VideoLibraryStorage


def _storage(tmp_path) -> VideoLibraryStorage:
    return VideoLibraryStorage(root=tmp_path)


def test_relative_traversal_rejected(tmp_path):
    s = _storage(tmp_path)
    with pytest.raises(StorageError):
        s.contain("../../etc/passwd")


def test_windows_traversal_rejected(tmp_path):
    s = _storage(tmp_path)
    for evil in ("..\\..\\Windows\\System32", "../../etc/passwd"):
        with pytest.raises(StorageError):
            s.contain(evil)


def test_absolute_path_rejected(tmp_path):
    s = _storage(tmp_path)
    for evil in ("C:\\Windows\\System32\\evil", "/etc/passwd"):
        with pytest.raises(StorageError):
            s.contain(evil)


def test_reserved_windows_name_rejected(tmp_path):
    s = _storage(tmp_path)
    for evil in ("CON", "nul", "COM1", "LPT9", "AUX.txt"):
        with pytest.raises(StorageError):
            s.contain(evil)


def test_nul_byte_rejected(tmp_path):
    s = _storage(tmp_path)
    with pytest.raises(StorageError):
        s.contain("evil\x00name")


def test_legit_video_id_works(tmp_path):
    s = _storage(tmp_path)
    p = s.video_path("mi-video-01")
    assert p.resolve().is_relative_to(s.video_dir.resolve())
    assert p.suffix == ".mp4"
    assert p.name.startswith("mi-video-01")


def test_cache_path_contained(tmp_path):
    s = _storage(tmp_path)
    p = s.cache_path("transcript.txt")
    assert p.resolve().is_relative_to(s.cache_dir.resolve())


@pytest.mark.skipif(os.name != "posix", reason="symlinks fuera de root requieren posix/dev perms")
def test_symlink_pointing_outside_rejected(tmp_path):
    s = _storage(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    link = s.video_dir / "evil-link"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("sin permisos para crear symlinks")
    resolved = link.resolve()
    assert not resolved.is_relative_to(s.video_dir.resolve())
