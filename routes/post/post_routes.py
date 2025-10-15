from flask import jsonify, request

from utils.database_util import DatabaseManager

from . import post_bp
from .image_service import (
    cleanup_saved_images,
    collect_image_files,
    fetch_post_images,
    save_post_images,
)
from .utils import parse_request_payload, require_login, to_bool


@post_bp.route('/api/posts/', methods=['POST'])
def create_post():
    db = None
    saved_images = []
    try:
        sid, err = require_login()
        if err:
            return err

        is_multipart = request.content_type and 'multipart/form-data' in request.content_type
        payload = parse_request_payload()
        title = (payload.get('title') or '').strip()
        content = (payload.get('content') or '').strip()
        is_anonymous = 1 if to_bool(payload.get('is_anonymous'), False) else 0

        if not title or not content:
            return jsonify({
                "status": "error",
                "message": "제목과 내용을 모두 입력하세요."
            }), 400

        image_files = collect_image_files() if is_multipart else []
        saved_images = save_post_images(image_files)

        db = DatabaseManager()
        db.query(
            """
            INSERT INTO Posts (student_id, title, content, is_anonymous)
            VALUES (%(sid)s, %(title)s, %(content)s, %(is_anonymous)s)
            """,
            sid=sid,
            title=title,
            content=content,
            is_anonymous=is_anonymous
        )
        post_id_row = db.query("SELECT LAST_INSERT_ID()")

        post_id = post_id_row.result[0][0] if post_id_row.result else None

        if post_id is None:
            raise ValueError("게시물 ID를 가져올 수 없습니다.")

        if saved_images:
            db.query_many(
                """
                INSERT INTO PostImages (post_id, original_name, stored_name, content_type, file_size)
                VALUES (%(post_id)s, %(original_name)s, %(stored_name)s, %(content_type)s, %(file_size)s)
                """,
                [
                    {
                        'post_id': post_id,
                        'original_name': img['original_name'],
                        'stored_name': img['stored_name'],
                        'content_type': img['content_type'],
                        'file_size': img['file_size']
                    }
                    for img in saved_images
                ]
            )

        db.commit()

        images = fetch_post_images(db, [post_id]).get(post_id, [])

        return jsonify({
            "status": "success",
            "message": "게시물 작성 성공",
            "post_id": post_id,
            "images": images
        }), 201
    except ValueError as ve:
        cleanup_saved_images(saved_images)
        if db and getattr(db, 'db_conn', None):
            try:
                db.db_conn.rollback()
            except Exception:
                pass
        return jsonify({
            "status": "error",
            "message": str(ve)
        }), 400
    except Exception as e:
        cleanup_saved_images(saved_images)
        if db and getattr(db, 'db_conn', None):
            try:
                db.db_conn.rollback()
            except Exception:
                pass
        return jsonify({
            "status": "error",
            "message": "서버 오류가 발생했습니다.",
            "detail": str(e)
        }), 500


@post_bp.route('/api/posts/', methods=['GET'])
def list_posts():
    try:
        try:
            page = int(request.args.get('page', 1))
            size = int(request.args.get('size', 10))
        except ValueError:
            return jsonify({
                "status": "error",
                "message": "유효한 페이지/크기를 입력하세요."
            }), 400

        if page < 1 or size < 1 or size > 100:
            return jsonify({
                "status": "error",
                "message": "페이지는 1 이상, 크기는 1~100 사이여야 합니다."
            }), 400

        offset = (page - 1) * size

        db = DatabaseManager()
        total = db.query("SELECT COUNT(*) FROM Posts").result[0][0]

        rows = db.query(
            """
            SELECT 
                p.post_id,
                p.student_id,
                s.student_name,
                p.title,
                p.content,
                p.is_anonymous,
                p.like_count,
                DATE_FORMAT(p.created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at,
                (SELECT COUNT(*) FROM Comments c WHERE c.post_id = p.post_id) as comment_count
            FROM Posts p
            LEFT JOIN Students s ON p.student_id = s.student_id
            ORDER BY p.post_id DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            limit=size,
            offset=offset
        ).result

        items = []
        post_ids = []
        for r in rows:
            (post_id, student_id, student_name, title, content, is_anonymous,
             like_count, created_at, comment_count) = r
            anon = bool(is_anonymous)
            post_ids.append(post_id)
            items.append({
                "post_id": post_id,
                "student_id": None if anon else student_id,
                "student_name": "익명" if anon else student_name,
                "title": title,
                "content": content,
                "is_anonymous": anon,
                "like_count": like_count,
                "comment_count": comment_count,
                "created_at": created_at
            })

        images_map = fetch_post_images(db, post_ids)
        for item in items:
            item["images"] = images_map.get(item["post_id"], [])

        return jsonify({
            "status": "success",
            "page": page,
            "size": size,
            "total": total,
            "items": items
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "서버 오류가 발생했습니다.",
            "detail": str(e)
        }), 500


@post_bp.route('/api/posts/<int:post_id>/', methods=['GET'])
def get_post_detail(post_id: int):
    try:
        db = DatabaseManager()
        post_row = db.query(
            """
            SELECT 
                p.post_id,
                p.student_id,
                s.student_name,
                p.title,
                p.content,
                p.is_anonymous,
                p.like_count,
                DATE_FORMAT(p.created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at
            FROM Posts p
            LEFT JOIN Students s ON p.student_id = s.student_id
            WHERE p.post_id = %(post_id)s
            """,
            post_id=post_id
        ).result

        if not post_row:
            return jsonify({
                "status": "error",
                "message": "게시물을 찾을 수 없습니다."
            }), 404

        (pid, student_id, student_name, title, content, is_anonymous,
         like_count, created_at) = post_row[0]
        anon = bool(is_anonymous)
        post_obj = {
            "post_id": pid,
            "student_id": None if anon else student_id,
            "student_name": "익명" if anon else student_name,
            "title": title,
            "content": content,
            "is_anonymous": anon,
            "like_count": like_count,
            "created_at": created_at
        }

        post_obj["images"] = fetch_post_images(db, [post_id]).get(post_id, [])

        comments = db.query(
            """
            SELECT 
                c.comment_id,
                c.student_id,
                s.student_name,
                c.content,
                c.is_anonymous,
                DATE_FORMAT(c.created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at
            FROM Comments c
            LEFT JOIN Students s ON c.student_id = s.student_id
            WHERE c.post_id = %(post_id)s
            ORDER BY c.created_at ASC
            """,
            post_id=post_id
        ).result

        comment_items = []
        for r in comments:
            (cid, c_student_id, c_student_name, c_content, c_is_anonymous, c_created_at) = r
            c_anon = bool(c_is_anonymous)
            comment_items.append({
                "comment_id": cid,
                "student_id": None if c_anon else c_student_id,
                "student_name": "익명" if c_anon else c_student_name,
                "content": c_content,
                "is_anonymous": c_anon,
                "created_at": c_created_at
            })

        return jsonify({
            "status": "success",
            "post": post_obj,
            "comments": comment_items
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "서버 오류가 발생했습니다.",
            "detail": str(e)
        }), 500


@post_bp.route('/api/posts/<int:post_id>/like/', methods=['POST'])
def toggle_like(post_id: int):
    try:
        sid, err = require_login()
        if err:
            return err

        db = DatabaseManager()
        post_exists = db.query(
            "SELECT 1 FROM Posts WHERE post_id = %(post_id)s",
            post_id=post_id
        ).result
        if not post_exists:
            return jsonify({
                "status": "error",
                "message": "게시물을 찾을 수 없습니다."
            }), 404

        liked_row = db.query(
            """
            SELECT 1 FROM PostLikes 
            WHERE post_id = %(post_id)s AND student_id = %(sid)s
            """,
            post_id=post_id,
            sid=sid
        ).result

        if liked_row:
            db.query(
                "DELETE FROM PostLikes WHERE post_id = %(post_id)s AND student_id = %(sid)s",
                post_id=post_id,
                sid=sid
            )
            db.query(
                "UPDATE Posts SET like_count = GREATEST(like_count - 1, 0) WHERE post_id = %(post_id)s",
                post_id=post_id
            )
            liked = False
        else:
            db.query(
                "INSERT INTO PostLikes (post_id, student_id) VALUES (%(post_id)s, %(sid)s)",
                post_id=post_id,
                sid=sid
            )
            db.query(
                "UPDATE Posts SET like_count = like_count + 1 WHERE post_id = %(post_id)s",
                post_id=post_id
            )
            liked = True

        count_row = db.query(
            "SELECT like_count FROM Posts WHERE post_id = %(post_id)s",
            post_id=post_id
        ).result
        db.commit()

        like_count = count_row[0][0] if count_row else 0

        return jsonify({
            "status": "success",
            "liked": liked,
            "like_count": like_count
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": "서버 오류가 발생했습니다.",
            "detail": str(e)
        }), 500
