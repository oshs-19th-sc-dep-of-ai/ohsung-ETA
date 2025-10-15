# Posts API (routes/post.py) 정리

이 문서는 `routes/post.py`에 구현된 게시물 관련 REST API를 요약합니다. 공통 사항, 각 엔드포인트의 동작, 입력/출력 형식, 주요 예외 처리 및 DB 상호작용을 간단히 정리합니다. 모든 경로는 `/api/posts`를 기준으로 합니다.

---

## 공통
- 인증: 세션 기반. 세션 키 `session_student_id`가 있어야 로그인된 상태로 간주.
  - 로그인 필요 시 응답: 401, `{"status":"error","message":"로그인이 필요합니다."}`
- DB 유틸: `utils.database_util.DatabaseManager` 사용.
- 익명 처리:
  - DB 컬럼 `is_anonymous`(1/0)로 저장. API 응답에서는 boolean으로 변환.
  - 익명인 경우 `student_id`는 NULL, `student_name`에는 `'익명'` 표시.
- 에러 처리:
  - 입력 검증 실패: 400
  - 리소스 없음: 404
  - DB 무결성 오류: 400 (예: INSERT 제약 위반)
  - 기타 서버 오류: 500 (응답에 `detail` 포함)

---

## POST /api/posts/
게시물 생성

- 인증: 필요
- 요청 형식:
  - 기본: `Content-Type: application/json`
  - 이미지 포함 시: `multipart/form-data` (`images` 필드 사용)
- 요청 바디:
  - `title` (string, required)
  - `content` (string, required)
  - `is_anonymous` (boolean | "1" | "true" 등, optional, default false)
  - `images` (multipart file[], optional, 허용 확장자: jpg/jpeg/png/gif/webp, 1파일 최대 5MB 기본값)
- 동작:
  - 세션의 `student_id` 존재 확인(Students 테이블).
  - Posts에 레코드 삽입.
  - 이미지가 있다면 파일을 저장하고 `PostImages`에 메타데이터 기록.
  - 삽입 후 `LAST_INSERT_ID()`로 `post_id` 반환.
- 응답:
  - 성공: 201
    ```json
    {
      "status": "success",
      "message": "게시물 작성 성공",
      "post_id": 123,
      "images": [
        {
          "image_id": 1,
          "original_name": "sample.png",
          "url": "/api/posts/images/3f...ab.png",
          "content_type": "image/png",
          "file_size": 102400
        }
      ]
    }
    ```
  - 입력 누락: 400, `{"status":"error","message":"제목과 내용을 모두 입력하세요."}`
  - 이미지 검증 실패: 400, 원인별 메시지 반환
  - 세션 불일치: 401, `{"status":"error","message":"유효하지 않은 세션입니다. 다시 로그인해 주세요."}`

예:
```bash
# JSON 전송
curl -X POST /api/posts/ \
  -H "Content-Type: application/json" \
  -d '{"title":"제목","content":"내용","is_anonymous":true}'

# 이미지 포함 multipart 예시
curl -X POST /api/posts/ \
  -H "Content-Type: multipart/form-data" \
  -F "title=제목" \
  -F "content=본문" \
  -F "is_anonymous=false" \
  -F "images=@/path/to/image1.png" \
  -F "images=@/path/to/image2.jpg"
```

---

## GET /api/posts/
게시물 목록 (페이징)

- 인증: 불필요 (공개 목록)
- 쿼리 파라미터:
  - `page` (int, default 1)
  - `size` (int, default 10, min 1, max 100)
- 동작:
  - 전체 개수 조회 `SELECT COUNT(*) FROM Posts`
  - 게시물과 작성자(Students) 조인으로 목록 조회. 각 항목에 댓글 수(subquery) 포함. 여기서 댓글 수는 `Comments`만 집계되며 대댓글은 포함되지 않습니다.
  - 관련 이미지가 있으면 `PostImages`에서 메타데이터를 가져와 `images` 배열 반환.
  - 익명 글은 `student_id`를 NULL로, `student_name`을 "익명"으로 반환.
- 응답: 200
  ```json
  {
    "status": "success",
    "page": 1,
    "size": 10,
    "total": 42,
    "items": [
      {
        "post_id": 1,
        "student_id": 123,         // 익명 시 null
        "student_name": "홍길동",  // 익명 시 "익명"
        "title": "...",
        "content": "...",
        "is_anonymous": false,
        "like_count": 5,
        "comment_count": 2,
        "created_at": "2025-08-27 12:00:00",
        "images": [
          {
            "image_id": 1,
            "original_name": "sample.png",
            "url": "/api/posts/images/3f...ab.png",
            "content_type": "image/png",
            "file_size": 102400
          }
        ]
      },
      ...
    ]
  }
  ```
- 잘못된 페이지 파라미터: 400

---

## POST /api/posts/<post_id>/comments/
댓글 작성

- 인증: 필요
- 경로 파라미터: `post_id` (int)
- 요청 바디 (JSON):
  - `content` (string, required)
  - `is_anonymous` (boolean, optional)
- 동작:
  - 대상 게시물 존재 확인 (`Posts`).
  - `Comments` 테이블에 삽입, `LAST_INSERT_ID()`로 `comment_id` 반환.
- 응답:
  - 성공: 201
    ```json
    {
      "status": "success",
      "message": "댓글 작성 성공",
      "comment_id": 456
    }
    ```
  - 내용 누락: 400, `{"status":"error","message":"댓글 내용을 입력하세요."}`
  - 게시물 없음: 404

예:
```bash
curl -X POST /api/posts/1/comments/ \
  -H "Content-Type: application/json" \
  -d '{"content":"댓글","is_anonymous":false}'
```

---

## POST /api/posts/<post_id>/comments/<comment_id>/replies/
대댓글(답글) 작성

- 인증: 필요
- 경로 파라미터: `post_id` (int), `comment_id` (int)
- 요청 바디 (JSON):
  - `content` (string, required)
  - `is_anonymous` (boolean, optional)
- 동작:
  - `comment_id`가 해당 `post_id`에 속하는지 검증.
  - `Sub_comments`에 삽입, `LAST_INSERT_ID()`로 `sub_comment_id` 반환.
- 응답:
  - 성공: 201
    ```json
    {
      "status": "success",
      "message": "대댓글 작성 성공",
      "sub_comment_id": 789
    }
    ```
  - 내용 누락: 400, `{"status":"error","message":"대댓글 내용을 입력하세요."}`
  - 대상 댓글 없음: 404

예:
```bash
curl -X POST /api/posts/1/comments/10/replies/ \
  -H "Content-Type: application/json" \
  -d '{"content":"대댓글입니다","is_anonymous":true}'
```

---

## GET /api/posts/<post_id>/comments/<comment_id>/replies/
특정 댓글의 대댓글 목록 조회

- 인증: 불필요 (공개)
- 경로 파라미터: `post_id` (int), `comment_id` (int)
- 동작:
  - `comment_id`가 해당 `post_id`에 속하는지 검증.
  - 해당 댓글의 대댓글 목록 조회(작성자 익명 처리).
- 응답: 200
  ```json
  {
    "status": "success",
    "items": [
      {
        "sub_comment_id": 1,
        "student_id": null,
        "student_name": "익명",
        "content": "대댓글 내용",
        "is_anonymous": true,
        "created_at": "2025-08-27 12:02:00"
      }
    ]
  }
  ```
- 대상 댓글 없음: 404

예:
```bash
curl -X GET /api/posts/1/comments/10/replies/
```

---

## POST /api/posts/<post_id>/like/
게시물 좋아요 토글(추가/취소)

- 인증: 필요
- 경로 파라미터: `post_id` (int)
- 동작:
  - 게시물 존재 확인.
  - `PostLikes` 테이블에서 (post_id, student_id) 존재 여부 검사.
    - 존재하면 삭제(좋아요 취소) 및 Posts.like_count 감소(GREATEST로 음수 방지).
    - 존재하지 않으면 삽입 및 Posts.like_count 증가.
  - 변경 후 현재 like_count 조회 및 반환.
- 응답: 200
  ```json
  {
    "status": "success",
    "liked": true,      // 현재 요청 후의 상태
    "like_count": 10
  }
  ```
- 게시물 없음: 404

예:
```bash
curl -X POST /api/posts/1/like/
```

---

## GET /api/posts/<post_id>/
게시물 상세 + 댓글 목록 조회

- 인증: 불필요 (공개)
- 경로 파라미터: `post_id` (int)
- 동작:
  - 게시물 상세 조회(작성자명은 익명 처리 반영) 및 첨부 이미지 목록(`PostImages`).
  - 해당 게시물의 댓글 목록 조회(작성자명 익명 처리). 대댓글은 포함되지 않으며 별도 API로 조회합니다.
  - 댓글은 `created_at` 오름차순으로 정렬.
- 응답: 200
  ```json
  {
    "status": "success",
    "post": {
      "post_id": 1,
      "student_id": 123,
      "student_name": "홍길동",
      "title": "...",
      "content": "...",
      "is_anonymous": false,
      "like_count": 5,
      "created_at": "2025-08-27 12:00:00",
      "images": [
        {
          "image_id": 1,
          "original_name": "sample.png",
          "url": "/api/posts/images/3f...ab.png",
          "content_type": "image/png",
          "file_size": 102400
        }
      ]
    },
    "comments": [
      {
        "comment_id": 10,
        "student_id": null,
        "student_name": "익명",
        "content": "댓글 내용",
        "is_anonymous": true,
        "created_at": "2025-08-27 12:01:00"
      },
      ...
    ]
  }
  ```
- 게시물 없음: 404

---

## GET /api/posts/images/<filename>
게시물 이미지 다운로드

- 인증: 불필요 (이미지 URL은 게시글 공개 범위와 동일하게 취급)
- 경로 파라미터: `filename` (업로드 시 부여된 저장 파일명)
- 동작:
  - 업로드 디렉터리(`POST_IMAGE_UPLOAD_FOLDER`)에서 파일을 찾아 전송.
- 응답:
  - 성공: 200, 실제 이미지 바이너리 반환 (적절한 `Content-Type` 설정)
  - 파일 없음: 404

---

## DB/스키마 관련 힌트 (코드에서 사용되는 테이블들)
- Posts (post_id, student_id, title, content, is_anonymous, like_count, created_at, ...)
- Students (student_id, student_name, ...)
- Comments (comment_id, post_id, student_id, content, is_anonymous, created_at, ...)
- PostLikes (post_id, student_id)
- Sub_comments (sub_comment_id, comment_id, student_id, content, is_anonymous, created_at)
- PostImages (image_id, post_id, original_name, stored_name, content_type, file_size, created_at)

---
