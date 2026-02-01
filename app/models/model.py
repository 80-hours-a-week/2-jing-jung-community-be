from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.sql import func
from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nickname = Column(String(10), nullable=False)
    email = Column(String(255), nullable=False)
    image_url = Column(String(255), nullable=False)
    password = Column(String(255), nullable=False)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True)
    deleted_at = Column(TIMESTAMP, nullable=True)


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    title = Column(String(26), nullable=False)
    image_url = Column(String(255), nullable=False)
    contents = Column(Text)

    views_count = Column(Integer, default=0)
    likes_count = Column(Integer, default=0)
    comments_count = Column("comments_count", Integer, default=0)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True)
    deleted_at = Column(TIMESTAMP, nullable=True)


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    content = Column(String(300), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True)
    deleted_at = Column(TIMESTAMP, nullable=True)


class Likes(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    post_id = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True)
    deleted_at = Column(TIMESTAMP, nullable=True)


class Views(Base):
    __tablename__ = "views"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    post_id = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True)
    deleted_at = Column(TIMESTAMP, nullable=True)


class SessionData(Base):
    __tablename__ = "sessions"

    session_id = Column(String(128), primary_key=True)
    expires = Column(Integer, nullable=False)
    data = Column(Text, nullable=True)