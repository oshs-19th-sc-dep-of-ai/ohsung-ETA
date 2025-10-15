import os
from pathlib import Path
from typing import Dict, Iterable, List
from uuid import uuid4

from flask import current_app, request, url_for
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from utils.database_util import DatabaseManager

SavedImage = Dict[str, str]


def cleanup_saved_images(saved_images: Iterable[SavedImage]) -> None:
    upload_dir = Path(current_app.config['POST_IMAGE_UPLOAD_FOLDER'])
    for img in saved_images:
        try:
            (upload_dir / img['stored_name']).unlink()
        except (FileNotFoundError, OSError):
            continue


def collect_image_files() -> List[FileStorage]:
    if not request.files:
        return []

    files: List[FileStorage] = []
    if 'images' in request.files:
        files.extend(request.files.getlist('images'))

    for key in request.files:
        if key == 'images':
            continue
        files.extend(request.files.getlist(key))

    return files


def save_post_images(files: Iterable[FileStorage]) -> List[SavedImage]:
    upload_dir = Path(current_app.config['POST_IMAGE_UPLOAD_FOLDER'])
    allowed_exts = current_app.config.get('POST_IMAGE_ALLOWED_EXTENSIONS', set())
    max_bytes = current_app.config.get('POST_IMAGE_MAX_BYTES')

    saved: List[SavedImage] = []
    try:
        for storage in files:
            if not storage or not storage.filename:
                continue

            original_name = storage.filename
            safe_name = secure_filename(original_name)
            if not safe_name:
                raise ValueError("유효한 파일 이름이 아닙니다.")

            ext = safe_name.rsplit('.', 1)[1].lower() if '.' in safe_name else ''
            if allowed_exts and ext not in allowed_exts:
                raise ValueError(f"지원하지 않는 이미지 형식입니다: {original_name}")

            stream = storage.stream
            try:
                stream.seek(0, os.SEEK_END)
                size = stream.tell()
                stream.seek(0)
            except Exception as exc:  # pragma: no cover - defensive
                raise ValueError("이미지 크기를 확인할 수 없습니다.") from exc

            if max_bytes and size > max_bytes:
                limit_mb = max_bytes / (1024 * 1024)
                raise ValueError(f"이미지 크기는 {limit_mb:.0f}MB 이하만 가능합니다: {original_name}")

            stored_name = f"{uuid4().hex}{f'.{ext}' if ext else ''}"
            storage.save(upload_dir / stored_name)

            saved.append({
                'original_name': original_name,
                'stored_name': stored_name,
                'content_type': storage.mimetype,
                'file_size': size
            })
    except Exception:
        cleanup_saved_images(saved)
        raise

    return saved


def fetch_post_images(db: DatabaseManager, post_ids: Iterable[int]) -> Dict[int, List[Dict[str, object]]]:
    unique_ids = list(dict.fromkeys(post_ids))
    if not unique_ids:
        return {}

    params = {f"id_{idx}": pid for idx, pid in enumerate(unique_ids)}
    placeholders = ", ".join([f"%({key})s" for key in params])

    rows = db.query(
        f"""
        SELECT
            post_id,
            image_id,
            original_name,
            stored_name,
            content_type,
            file_size
        FROM PostImages
        WHERE post_id IN ({placeholders})
        ORDER BY image_id ASC
        """,
        **params
    ).result

    images: Dict[int, List[Dict[str, object]]] = {pid: [] for pid in unique_ids}
    for row in rows:
        (pid, image_id, original_name, stored_name, content_type, file_size) = row
        size = int(file_size) if file_size is not None else None
        images.setdefault(pid, []).append({
            "image_id": image_id,
            "original_name": original_name,
            "url": url_for('post.get_post_image', filename=stored_name, _external=False),
            "content_type": content_type,
            "file_size": size
        })

    for pid in unique_ids:
        images.setdefault(pid, [])

    return images
