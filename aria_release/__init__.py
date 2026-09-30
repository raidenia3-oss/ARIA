"""ARIA Rolling Release Pipeline.

Implements Fedora-style channels + TUF-signed metadata + Windows-style
versioned layout with atomic symlink updates and rollback.
"""

from .models import Release, Channel, Metadata, ReleaseChannel
from .detector import ReleaseDetector
from .verifier import MetadataVerifier, verify_checksum
from .downloader import ReleaseDownloader
from .updater import Updater
from .pipeline import RollingReleasePipeline

__all__ = [
    "Release",
    "Channel",
    "Metadata",
    "ReleaseChannel",
    "ReleaseDetector",
    "MetadataVerifier",
    "verify_checksum",
    "ReleaseDownloader",
    "Updater",
    "RollingReleasePipeline",
]

__version__ = "1.0.0"