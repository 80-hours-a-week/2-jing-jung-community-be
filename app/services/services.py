from datetime import datetime
from app.schemas.model import UserCreate, UserLogin, PostCreate, PostUpdate

users_db = []
posts_db = []
comments_db = [
    {
        "id": 1,
        "post_id": 1,
        "user_id": 1,
        "content": "댓글 목록",
        "created_at": str(datetime.now())
    }
]


# 회원(User) 관련 함수들

def create_user(user: UserCreate):
    for u in users_db:
        if u["email"] == user.email:
            return False

    new_user = user.dict()
    new_user["id"] = len(users_db) + 1
    new_user["created_at"] = str(datetime.now())
    users_db.append(new_user)
    return new_user


def login_user(data: UserLogin):
    for u in users_db:
        if u["email"] == data.email and u["password"] == data.password:
            return u
    return None


def get_user_by_id(user_id: int):
    for u in users_db:
        if u["id"] == user_id:
            return {
                "id": u["id"],
                "email": u["email"],
                "nickname": u["nickname"],
                "created_at": u["created_at"]
            }
    return None


def delete_user_by_id(user_id: int):
    user = get_user_by_id(user_id)
    if not user:
        return False

    nickname = None
    for u in users_db:
        if u["id"] == user_id:
            nickname = u["nickname"]
            break

    if not nickname:
        return False

    for i in range(len(posts_db) - 1, -1, -1):
        if posts_db[i]["writer"] == nickname:
            post_id = posts_db[i]["id"]
            delete_comments_by_post_id(post_id)
            del posts_db[i]

    delete_comments_by_user_id(user_id)

    for i in range(len(users_db) - 1, -1, -1):
        if users_db[i]["id"] == user_id:
            del users_db[i]
            return True

    return False


# 게시글(Post) 관련 함수들

def get_post_list(page: int, size: int):
    if page < 1 or size < 1:
        return []

    start = (page - 1) * size
    end = start + size
    return posts_db[start:end]


def create_post(post: PostCreate, writer: str):
    new_post = post.dict()
    new_post["id"] = len(posts_db) + 1
    new_post["writer"] = writer
    new_post["created_at"] = str(datetime.now())
    new_post["view_count"] = 0
    new_post["like_count"] = 0

    posts_db.append(new_post)
    return new_post


def get_post(post_id: int):
    for post in posts_db:
        if post["id"] == post_id:
            post["view_count"] += 1
            return post
    return None


def update_post(post_id: int, update_data: PostUpdate, nickname: str):
    for post in posts_db:
        if post["id"] == post_id:
            if post["writer"] != nickname:
                return "FORBIDDEN"

            if update_data.title:
                post["title"] = update_data.title
            if update_data.content:
                post["content"] = update_data.content
            if update_data.image_url is not None:
                post["image_url"] = update_data.image_url
            return post
    return None


def delete_post(post_id: int, nickname: str):
    for i in range(len(posts_db) - 1, -1, -1):
        if posts_db[i]["id"] == post_id:
            if posts_db[i]["writer"] != nickname:
                return "FORBIDDEN"
            delete_comments_by_post_id(post_id)
            del posts_db[i]
            return True
    return False


# 댓글(Comment) 관련 함수들

def get_comments_by_post_id(post_id: int):
    result = []
    for c in comments_db:
        if c["post_id"] == post_id:
            writer_nickname = "알 수 없음"
            for u in users_db:
                if u["id"] == c["user_id"]:
                    writer_nickname = u["nickname"]
                    break

            comment_data = {
                "id": c["id"],
                "nickname": writer_nickname,
                "content": c["content"],
                "created_at": c["created_at"]
            }
            result.append(comment_data)
    return result


def delete_comments_by_post_id(post_id: int):
    for i in range(len(comments_db) - 1, -1, -1):
        if comments_db[i]["post_id"] == post_id:
            del comments_db[i]


def delete_comments_by_user_id(user_id: int):
    for i in range(len(comments_db) - 1, -1, -1):
        if comments_db[i]["user_id"] == user_id:
            del comments_db[i]
