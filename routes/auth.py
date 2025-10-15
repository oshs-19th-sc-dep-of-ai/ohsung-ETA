import json

from flask import Blueprint, request, session, jsonify
from utils.database_util import DatabaseManager

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods = ['POST'])
def login():
    data = request.get_json(silent=True)

    if data is None:
        data = {}
        if request.form:
            payload = request.form.get('payload')
            if payload:
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    data = {}
            if not data:
                data = {key: request.form.get(key) for key in request.form.keys()}
                if '' in data and not {'student_id', 'password'} & data.keys():
                    single_value = data.get('')
                    if single_value:
                        try:
                            data = json.loads(single_value)
                        except json.JSONDecodeError:
                            pass
        elif request.data:
            try:
                data = json.loads(request.data.decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError):
                data = {}

    if not isinstance(data, dict):
        data = {}

    input_student_id = (data.get('student_id') or '').strip()
    input_student_pw = data.get('password')

    # 입력값 체크
    if not input_student_id or not input_student_pw:
        return jsonify({
            "message": "ID와 비밀번호를 모두 입력해주세요.",
            "status": "error"
        }), 400
    db = DatabaseManager()

    # 학생 로그인 처리
    student = db.query(
            """
            SELECT student_id, student_name, is_admin FROM Students
            WHERE student_id = %(student_id)s AND student_pw = SHA2(%(student_pw)s, 256)
            """,
            student_id=input_student_id,
            student_pw=input_student_pw
        ).result

    db.commit()

    if student:
        student = student[0]
        student_id, student_name, is_admin = student
        if is_admin:
            session['session_admin_id'] = student[0]
            session['session_admin_name'] = student[1]
            return jsonify({
                "message": "관리자 로그인 성공!",
                "status": "admin",
                "student_id": student[0],
                "student_name": student[1]
            }), 200

        else:
            session['session_student_id'] = student[0]
            session['session_student_name'] = student[1]
            return jsonify({
                "message": "로그인 성공!",
                "status": "success",
                "student_id": student[0],
                "student_name": student[1]
            }), 200
    else:
        return jsonify({
            "message": "잘못된 ID 또는 비밀번호입니다.",
            "status": "error"
        }), 401


# 로그아웃
@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({
        "message": "로그아웃 되었습니다."
    })
