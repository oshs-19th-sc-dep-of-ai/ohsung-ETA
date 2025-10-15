from flask import jsonify

from utils.database_util import DatabaseManager

from . import post_bp
from .utils import parse_request_payload, require_login, to_bool


@post_bp.route('/api/posts/<int:post_id>/comments/<int:comment_id>/replies/', methods=['POST'])
def create_sub_comment(post_id: int, comment_id: int):
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
                "message": "대댓글 내용을 입력하세요."
            }), 400

        db = DatabaseManager()

        comment_exists = db.query(
            """
            SELECT 1 FROM Comments 
            WHERE comment_id = %(comment_id)s AND post_id = %(post_id)s
            """,
            comment_id=comment_id,
            post_id=post_id
        ).result
        if not comment_exists:
            return jsonify({
                "status": "error",
                "message": "대상 댓글을 찾을 수 없습니다."
            }), 404

        db.query(
            """
            INSERT INTO Sub_comments (comment_id, student_id, content, is_anonymous)
            VALUES (%(comment_id)s, %(sid)s, %(content)s, %(is_anonymous)s)
            """,
            comment_id=comment_id,
            sid=sid,
            content=content,
            is_anonymous=is_anonymous
        )
        scid_row = db.query("SELECT LAST_INSERT_ID()")
        db.commit()

        sub_comment_id = None
        if scid_row.result and len(scid_row.result[0]) > 0:
            sub_comment_id = scid_row.result[0][0]

        return jsonify({
            "status": "success",
            "message": "대댓글 작성 성공",
            "sub_comment_id": sub_comment_id
        }), 201
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "서버 오류가 발생했습니다.",
            "detail": str(e)
        }), 500


@post_bp.route('/api/posts/<int:post_id>/comments/<int:comment_id>/replies/', methods=['GET'])
def list_sub_comments(post_id: int, comment_id: int):
    try:
        db = DatabaseManager()

        comment_exists = db.query(
            """
            SELECT 1 FROM Comments 
            WHERE comment_id = %(comment_id)s AND post_id = %(post_id)s
            """,
            comment_id=comment_id,
            post_id=post_id
        ).result
        if not comment_exists:
            return jsonify({
                "status": "error",
                "message": "대상 댓글을 찾을 수 없습니다."
            }), 404

        rows = db.query(
            """
            SELECT 
                sc.sub_comment_id,
                sc.student_id,
                s.student_name,
                sc.content,
                sc.is_anonymous,
                DATE_FORMAT(sc.created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at
            FROM Sub_comments sc
            LEFT JOIN Students s ON sc.student_id = s.student_id
            WHERE sc.comment_id = %(comment_id)s
            ORDER BY sc.created_at ASC
            """,
            comment_id=comment_id
        ).result

        sub_comments = []
        for r in rows:
            (scid, s_student_id, s_student_name, s_content, s_is_anonymous, s_created_at) = r
            s_anon = bool(s_is_anonymous)
            sub_comments.append({
                "sub_comment_id": scid,
                "student_id": None if s_anon else s_student_id,
                "student_name": "익명" if s_anon else s_student_name,
                "content": s_content,
                "is_anonymous": s_anon,
                "created_at": s_created_at
            })

        return jsonify({
            "status": "success",
            "sub_comments": sub_comments
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "서버 오류가 발생했습니다.",
            "detail": str(e)
        }), 500
