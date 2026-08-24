import os
import shutil

from django.conf import settings


def search_by_uuid(bil_uuid: str) -> list:
    """Search the configured spreadsheet directory for files whose name contains bil_uuid.

    Returns list of dicts with keys: id, name, modified.
    The 'id' field is the absolute file path (used by download_file).
    """
    root = settings.V2_SPREADSHEET_DIR
    if not root or not os.path.isdir(root):
        raise FileNotFoundError(f"V2_SPREADSHEET_DIR not configured or does not exist: {root}")

    matches = []
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            if bil_uuid in filename and filename.endswith(('.xlsx', '.xls')):
                full_path = os.path.join(dirpath, filename)
                mtime = os.path.getmtime(full_path)
                matches.append({
                    'id': full_path,
                    'name': filename,
                    'modified': mtime,
                })

    matches.sort(key=lambda f: f['modified'], reverse=True)
    return matches


def download_file(file_id: str, dest_path: str) -> str:
    """Copy a local spreadsheet to dest_path. Returns dest_path.

    file_id is the absolute path returned by search_by_uuid.
    """
    shutil.copy2(file_id, dest_path)
    return dest_path
