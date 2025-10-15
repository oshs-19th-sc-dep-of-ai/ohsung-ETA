import json
from typing import Any, Dict, Optional, Tuple

from flask import jsonify, request, session

from utils.database_util import DatabaseManager


def require_login() -> Tuple[Optional[int], Optional[Tuple[Any, int]]]:
    sid = session.get('session_student_id')
    if not sid:
        return None, (jsonify({
            "status": "error",
            "message": "로그인이 필요합니다."
        }), 401)

    db = DatabaseManager()
    exists = db.query(
        """
        SELECT 1 FROM Students WHERE student_id = %(sid)s
        """,
        sid=sid
    ).result
    if not exists:
        return None, (jsonify({
            "status": "error",
            "message": "유효하지 않은 세션입니다. 다시 로그인해 주세요."
        }), 401)
    return sid, None


def to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        return v in ("1", "true", "t", "yes", "y", "on")
    return default


def parse_request_payload() -> Dict[str, Any]:
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        return data

    content_type = (request.content_type or '').lower()

    if 'multipart/form-data' in content_type or request.form:
        form_dict = request.form.to_dict(flat=True)

        payload_candidates = []
        if 'payload' in request.form:
            payload_candidates.extend(request.form.getlist('payload'))
        if '' in request.form:
            payload_candidates.extend([value for value in request.form.getlist('') if value])

        for candidate in payload_candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

        cleaned = {k: v for k, v in form_dict.items() if k}
        if cleaned:
            return cleaned

    if request.data:
        try:
            parsed = json.loads(request.data.decode('utf-8'))
            if isinstance(parsed, dict):
                return parsed
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass

    return {}
