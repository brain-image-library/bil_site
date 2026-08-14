"""Resolve the /etc/<uuid>/ working directory for a collection."""
import os
import tempfile

from django.conf import settings


def get_etc_dir(collection) -> str:
    """Return the absolute /etc working directory path for this collection.

    Production: derived from collection.data_path via "/lz/" -> "/etc/" swap,
    matching ingest/views.py:3684.

    Local dev (FAKE_STORAGE_AREA truthy): a per-collection subdirectory under
    the system tempdir.

    Does not create the directory. Use ensure_etc_dir() to also create.
    """
    if getattr(settings, 'FAKE_STORAGE_AREA', False):
        return os.path.join(tempfile.gettempdir(), 'bil-etc', collection.bil_uuid)
    return collection.data_path.replace('/lz/', '/etc/')


def ensure_etc_dir(collection) -> str:
    path = get_etc_dir(collection)
    os.makedirs(path, exist_ok=True)
    return path
