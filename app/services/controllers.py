from fastapi import HTTPException, UploadFile
from sqlalchemy import text
import bcrypt
import os
import uuid
import shutil

ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif'}

def save_image(file: UploadFile) -> str:
    if not file or not file.filename:
        return ""
    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="이미지 파일(png, jpg,gif,jpeg)만 업로드 가능합니다.")

    filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = f"static/images/{filename}"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return f"/static/images/{filename}"


def get_current_user_id(request, db):
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    sql = text("SELECT data FROM sessions WHERE session_id = :session_id")
    result = db.execute(sql, {"session_id": session_id}).fetchone()

    if not result:
        raise HTTPException(status_code=401, detail="세션이 만료되었습니다.")

    return int(result.data)


# 1. 회원가입
def signup_controller(email, password, nickname, profile_image, db):
    # 이메일 중복 확인
    if db.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone():
        raise HTTPException(status_code=409, detail="이미 존재하는 이메일입니다.")

    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    image_url = save_image(profile_image)

    insert_sql = text("""
                      INSERT INTO users (email, password, nickname, image_url, created_at)
                      VALUES (:email, :password, :nickname, :image_url, NOW())
                      """)
    db.execute(insert_sql, {
        "email": email, "password": hashed_password, "nickname": nickname, "image_url": image_url
    })
    db.commit()
    return {"message": "회원가입 성공"}


# 2. 로그인
def login_controller(email, password, response, db):
    sql = text("SELECT * FROM users WHERE email = :email AND deleted_at IS NULL")
    user = db.execute(sql, {"email": email}).fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호 불일치")

    if not bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호 불일치")

    session_id = str(uuid.uuid4())
    db.execute(
        text("INSERT INTO sessions (session_id, expires, data) VALUES (:sess_id, 0, :u_id)"),
        {"sess_id": session_id, "u_id": str(user.id)}
    )
    db.commit()

    response.set_cookie(key="session_id", value=session_id, httponly=True, samesite="Lax", secure=False)
    return {"message": "로그인 성공"}


# 3. 로그아웃
def logout_controller(request, response, db):
    session_id = request.cookies.get("session_id")
    if session_id:
        db.execute(text("DELETE FROM sessions WHERE session_id = :sess_id"), {"sess_id": session_id})
        db.commit()
    response.delete_cookie("session_id")
    return {"message": "로그아웃"}


# 4. 내 정보 조회
def get_me_controller(request, db):
    user_id = get_current_user_id(request, db)
    user = db.execute(text("SELECT id, email, nickname, image_url FROM users WHERE id = :uid"),
                      {"uid": user_id}).fetchone()
    return {"id": user.id, "email": user.email, "nickname": user.nickname, "profile_image": user.image_url}


# 5. 게시글 목록 (삭제된 글 제외)
def get_posts_list_controller(offset, limit, db):
    sql = text("""
               SELECT p.id,
                      p.title,
                      p.likes_count,
                      p.views_count,
                      p.comments_count,
                      p.created_at,
                      u.nickname  as author_nickname,
                      u.image_url as author_profile_image
               FROM posts p
                        JOIN users u ON p.user_id = u.id
               WHERE p.deleted_at IS NULL
               ORDER BY p.id DESC LIMIT :limit
               OFFSET :offset
               """)
    posts = db.execute(sql, {"limit": limit, "offset": offset}).fetchall()

    results = []
    for p in posts:
        results.append({
            "post_id": p.id,
            "title": p.title,
            "likes": p.likes_count,
            "comments": p.comments_count,
            "views": p.views_count,
            "created_at": str(p.created_at),
            "author_nickname": p.author_nickname,
            "author_profile_image": p.author_profile_image
        })
    return {"posts": results}


# 6. 게시글 상세
def get_post_detail_controller(post_id, request, db):
    sql = text("""
               SELECT id,
                      user_id,
                      title,
                      contents,
                      image_url,
                      likes_count,
                      views_count,
                      comments_count as comments_count,
                      created_at,
                      deleted_at
               FROM posts
               WHERE id = :pid
                 AND deleted_at IS NULL
               """)
    post = db.execute(sql, {"pid": post_id}).fetchone()

    if not post:
        raise HTTPException(status_code=404, detail="삭제되었거나 존재하지 않는 게시글입니다.")

    current_user_id = -1
    try:
        current_user_id = get_current_user_id(request, db)
        if not db.execute(text("SELECT id FROM views WHERE user_id=:uid AND post_id=:pid"),
                          {"uid": current_user_id, "pid": post_id}).fetchone():
            db.execute(text("INSERT INTO views (user_id, post_id) VALUES (:uid, :pid)"),
                       {"uid": current_user_id, "pid": post_id})
            db.execute(text("UPDATE posts SET views_count = views_count + 1 WHERE id = :pid"), {"pid": post_id})
            db.commit()
            post = db.execute(sql, {"pid": post_id}).fetchone()
    except:
        pass

    writer = db.execute(text("SELECT nickname, image_url FROM users WHERE id = :uid"), {"uid": post.user_id}).fetchone()
    is_liked = False
    if current_user_id != -1 and db.execute(text("SELECT id FROM likes WHERE user_id=:uid AND post_id=:pid"),
                                            {"uid": current_user_id, "pid": post_id}).fetchone():
        is_liked = True

    return {
        "post_id": post.id,
        "title": post.title,
        "content": post.contents,
        "image": post.image_url,
        "likes_count": post.likes_count,
        "views_count": post.views_count,
        "comments_count": post.comments_count,
        "created_at": str(post.created_at),
        "author_nickname": writer.nickname if writer else "Unknown",
        "author_profile_image": writer.image_url if writer else "",
        "is_owner": (current_user_id == post.user_id),
        "is_liked": is_liked
    }


# 7. 게시글 작성
def create_post_controller(title, content, image, request, db):
    user_id = get_current_user_id(request, db)
    image_url = save_image(image)
    sql = text(
        "INSERT INTO posts (user_id, title, contents, image_url, created_at) VALUES (:uid, :title, :content, :img, NOW())")
    db.execute(sql, {"uid": user_id, "title": title, "content": content, "img": image_url})
    db.commit()
    return {"message": "게시글 등록 성공"}


# 8. 게시글 수정
def update_post_controller(post_id, title, content, image, request, db):
    user_id = get_current_user_id(request, db)
    post = db.execute(text("SELECT user_id FROM posts WHERE id=:pid AND deleted_at IS NULL"),
                      {"pid": post_id}).fetchone()
    if not post or post.user_id != user_id: raise HTTPException(status_code=403, detail="권한 없음")

    if image:
        new_url = save_image(image)
        db.execute(text("UPDATE posts SET title=:t, contents=:c, image_url=:i WHERE id=:pid"),
                   {"t": title, "c": content, "i": new_url, "pid": post_id})
    else:
        db.execute(text("UPDATE posts SET title=:t, contents=:c WHERE id=:pid"),
                   {"t": title, "c": content, "pid": post_id})
    db.commit()
    return {"message": "수정 완료"}


# 9. 게시글 삭제 (Soft Delete)
def delete_post_controller(post_id, request, db):
    user_id = get_current_user_id(request, db)
    post = db.execute(text("SELECT user_id FROM posts WHERE id=:pid AND deleted_at IS NULL"),
                      {"pid": post_id}).fetchone()
    if not post or post.user_id != user_id: raise HTTPException(status_code=403, detail="권한 없음")

    db.execute(text("UPDATE posts SET deleted_at = NOW() WHERE id=:pid"), {"pid": post_id})
    db.commit()
    return {"message": "삭제 완료"}


# 10. 좋아요
def like_post_controller(post_id, request, db):
    user_id = get_current_user_id(request, db)
    post = db.execute(text("SELECT * FROM posts WHERE id=:pid AND deleted_at IS NULL"), {"pid": post_id}).fetchone()
    if not post: raise HTTPException(status_code=404, detail="게시글 없음")

    existing = db.execute(text("SELECT id FROM likes WHERE user_id=:uid AND post_id=:pid"),
                          {"uid": user_id, "pid": post_id}).fetchone()
    is_liked = False
    if existing:
        db.execute(text("DELETE FROM likes WHERE id=:lid"), {"lid": existing.id})
        if post.likes_count > 0: db.execute(text("UPDATE posts SET likes_count = likes_count - 1 WHERE id=:pid"),
                                           {"pid": post_id})
    else:
        db.execute(text("INSERT INTO likes (user_id, post_id) VALUES (:uid, :pid)"), {"uid": user_id, "pid": post_id})
        db.execute(text("UPDATE posts SET likes_count = likes_count + 1 WHERE id=:pid"), {"pid": post_id})
        is_liked = True
    db.commit()
    updated = db.execute(text("SELECT likes_count FROM posts WHERE id=:pid"), {"pid": post_id}).fetchone()
    return {"likes_count": updated.likes_count, "is_liked": is_liked}


# 11. 댓글 작성
def create_comment_controller(post_id, content, request, db):
    user_id = get_current_user_id(request, db)

    if not content:
        raise HTTPException(status_code=400, detail="내용을 입력해주세요.")
    if len(content) > 1000:
        raise HTTPException(status_code=400, detail="댓글은 1000자까지만 가능합니다.")

    if not db.execute(text("SELECT id FROM posts WHERE id=:pid AND deleted_at IS NULL"), {"pid": post_id}).fetchone():
        raise HTTPException(status_code=404, detail="게시글이 없습니다.")

    db.execute(
        text("INSERT INTO comments (post_id, user_id, content, created_at) VALUES (:pid, :uid, :content, NOW())"),
        {"pid": post_id, "uid": user_id, "content": content})
    db.execute(text("UPDATE posts SET comments_count = comments_count + 1 WHERE id = :pid"), {"pid": post_id})
    db.commit()
    return {"message": "댓글 등록"}


# 12. 댓글 목록
def get_comments_controller(post_id, request, db):
    sql = text("""
               SELECT c.*, u.nickname, u.image_url
               FROM comments c
                        JOIN users u ON c.user_id = u.id
               WHERE c.post_id = :pid
                 AND c.deleted_at IS NULL
               """)
    comments = db.execute(sql, {"pid": post_id}).fetchall()

    current_user_id = -1
    try:
        current_user_id = get_current_user_id(request, db)
    except:
        pass

    results = []
    for c in comments:
        results.append({
            "comment_id": c.id,
            "content": c.content,
            "created_at": str(c.created_at),
            "author_nickname": c.nickname,
            "author_profile_image": c.image_url,
            "is_owner": (c.user_id == current_user_id)
        })
    return results


# 13. 댓글 삭제 (Soft Delete)
def delete_comment_controller(comment_id, request, db):
    user_id = get_current_user_id(request, db)
    check = db.execute(text("SELECT user_id FROM comments WHERE id=:cid AND deleted_at IS NULL"),
                       {"cid": comment_id}).fetchone()
    if not check or check.user_id != user_id: raise HTTPException(status_code=403, detail="권한 없음")

    db.execute(text("UPDATE comments SET deleted_at = NOW() WHERE id=:cid"), {"cid": comment_id})
    db.commit()
    return {"message": "삭제 완료"}


# 14. 댓글 수정
def update_comment_controller(comment_id, content, request, db):
    user_id = get_current_user_id(request, db)
    check = db.execute(text("SELECT user_id FROM comments WHERE id=:cid AND deleted_at IS NULL"),
                       {"cid": comment_id}).fetchone()
    if not check or check.user_id != user_id: raise HTTPException(status_code=403, detail="권한 없음")

    db.execute(text("UPDATE comments SET content=:c WHERE id=:cid"), {"c": content, "cid": comment_id})
    db.commit()
    return {"message": "수정 완료"}


# 15. 이메일 중복 체크
def check_email_controller(email, db):
    if db.execute(text("SELECT id FROM users WHERE email=:e"), {"e": email}).fetchone():
        raise HTTPException(status_code=409, detail="중복")
    return {"message": "가능"}


# 16. 닉네임 수정
def update_nickname_controller(user_id, nickname, request, db):
    current_user_id = get_current_user_id(request, db)
    if current_user_id != user_id: raise HTTPException(status_code=403, detail="권한 없음")
    db.execute(text("UPDATE users SET nickname=:n WHERE id=:uid"), {"n": nickname, "uid": user_id})
    db.commit()
    return {"message": "수정 완료"}


# 17. 비밀번호 수정
def update_password_controller(password, request, db):
    user_id = get_current_user_id(request, db)
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    db.execute(text("UPDATE users SET password=:p WHERE id=:uid"), {"p": hashed_password, "uid": user_id})
    db.commit()
    return {"message": "수정 완료"}


# 18. 회원 탈퇴 (Soft Delete)
def delete_user_controller(request, response, db):
    user_id = get_current_user_id(request, db)
    db.execute(text("UPDATE users SET deleted_at = NOW() WHERE id=:uid"), {"uid": user_id})
    db.commit()
    response.delete_cookie("session_id")
    return {"message": "탈퇴 완료"}