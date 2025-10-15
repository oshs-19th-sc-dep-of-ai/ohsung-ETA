from flask import jsonify

from utils.database_util import DatabaseManager

from . import post_bp
from .utils import parse_request_payload, require_login, to_bool


@post_bp.route('/api/posts/<int:post_id>/comments/', methods=['POST'])
def create_comment(post_id: int):
    try:
        sid, err = require_login()
        if err:
            return err

        payload = parse_request_payload()
        content = (payload.get('content') or '').strip()
        is_anonymous = 1 if to_bool(payload.get('is_anonymous'), False) else 0

        if not content:
            return jsonify({
                "status": "error",
                "message": "댓글 내용을 입력하세요."
            }), 400

        db = DatabaseManager()

        exists = db.query(
            "SELECT 1 FROM Posts WHERE post_id = %(post_id)s",
            post_id=post_id
        ).result
        if not exists:
            return jsonify({
                "status": "error",
                "message": "게시물을 찾을 수 없습니다."
            }), 404

        db.query(
            """
            INSERT INTO Comments (post_id, student_id, content, is_anonymous)
            VALUES (%(post_id)s, %(sid)s, %(content)s, %(is_anonymous)s)
            """,
            post_id=post_id,
            sid=sid,
            content=content,
            is_anonymous=is_anonymous
        )
        cid_row = db.query("SELECT LAST_INSERT_ID()")
        db.commit()

        comment_id = None
        if cid_row.result and len(cid_row.result[0]) > 0:
            comment_id = cid_row.result[0][0]

        return jsonify({
            "status": "success",
            "message": "댓글 작성 성공",
            "comment_id": comment_id
        }), 201
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "서버 오류가 발생했습니다.",
            "detail": str(e)
        }), 500
