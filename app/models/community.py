# ============================================
# app/models/community.py - 커뮤니티 관련 데이터베이스 모델
# ============================================
# 이 파일은 게시물, 좋아요, 댓글 등 커뮤니티 기능 테이블을 정의합니다.
# ============================================

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, Text, DateTime,
    ForeignKey, DECIMAL, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def generate_uuid() -> str:
    """UUID를 생성하는 헬퍼 함수"""
    return str(uuid.uuid4())


class Post(Base):
    """
    게시물 테이블 (posts)
    
    운동 결과를 공유한 게시물을 저장합니다.
    운동 완료 후 커뮤니티에 공유하면 이 테이블에 저장됩니다.
    
    [신입 개발자를 위한 팁]
    - workout_id와 1:1 관계 (한 운동당 하나의 게시물만 가능)
    - like_count, comment_count, bookmark_count는 캐시 값 (성능 최적화)
    """
    __tablename__ = "posts"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID, post_id로 사용')
    author_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment='작성자 ID')
    
    # 공유된 운동 ID (1:1 관계, 중복 공유 방지)
    workout_id = Column(String(36), ForeignKey("workouts.id"), unique=True, nullable=True, comment='공유된 운동 ID')
    
    # ========== 경로/운동 정보 (스냅샷) ==========
    route_name = Column(String(100), nullable=False)
    shape_id = Column(String(50), nullable=True)
    shape_name = Column(String(50), nullable=True)
    shape_icon = Column(String(50), nullable=True)
    
    # 운동 통계
    distance = Column(DECIMAL(5, 2), nullable=False)
    duration = Column(Integer, nullable=False)
    pace = Column(String(20), nullable=True)
    calories = Column(Integer, nullable=True)
    
    location = Column(String(100), nullable=True, comment='위치 (여의도 한강공원)')
    
    # ========== 게시물 내용 ==========
    caption = Column(Text, nullable=True, comment='캡션 (선택적)')
    visibility = Column(String(20), nullable=False, default="public", comment='public/private')
    
    # ========== 통계 (캐시) ==========
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    bookmark_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True, comment='Soft Delete')
    
    # ========== 관계 정의 ==========
    author = relationship("User", foreign_keys=[author_id], lazy="select")
    likes = relationship("PostLike", back_populates="post", lazy="select")
    bookmarks = relationship("PostBookmark", back_populates="post", lazy="select")
    comments = relationship("Comment", back_populates="post", lazy="select")
    
    def __repr__(self):
        return f"<Post(id={self.id}, route_name={self.route_name})>"


class PostLike(Base):
    """
    게시물 좋아요 테이블 (post_likes)
    
    어떤 사용자가 어떤 게시물에 좋아요를 눌렀는지 기록합니다.
    """
    __tablename__ = "post_likes"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID')
    post_id = Column(String(36), ForeignKey("posts.id"), nullable=False, comment='게시물 ID')
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment='좋아요한 사용자 ID')
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 복합 유니크 제약조건 (같은 게시물에 중복 좋아요 불가)
    __table_args__ = (
        UniqueConstraint('post_id', 'user_id', name='unique_post_like'),
    )
    
    # 관계 정의
    post = relationship("Post", back_populates="likes")


class PostBookmark(Base):
    """
    게시물 북마크 테이블 (post_bookmarks)
    
    어떤 사용자가 어떤 게시물을 북마크했는지 기록합니다.
    """
    __tablename__ = "post_bookmarks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID')
    post_id = Column(String(36), ForeignKey("posts.id"), nullable=False, comment='게시물 ID')
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment='북마크한 사용자 ID')
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 복합 유니크 제약조건
    __table_args__ = (
        UniqueConstraint('post_id', 'user_id', name='unique_post_bookmark'),
    )
    
    # 관계 정의
    post = relationship("Post", back_populates="bookmarks")


class Comment(Base):
    """
    댓글 테이블 (comments)
    
    게시물에 달린 댓글을 저장합니다.
    """
    __tablename__ = "comments"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID, comment_id로 사용')
    post_id = Column(String(36), ForeignKey("posts.id"), nullable=False, comment='게시물 ID')
    author_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment='작성자 ID')
    
    content = Column(String(500), nullable=False, comment='댓글 내용 (최대 500자)')
    like_count = Column(Integer, default=0, comment='좋아요 수 (캐시)')
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True, comment='Soft Delete')
    
    # 관계 정의
    author = relationship("User", foreign_keys=[author_id], lazy="select")
    post = relationship("Post", back_populates="comments")
    likes = relationship("CommentLike", back_populates="comment", lazy="select")


class CommentLike(Base):
    """
    댓글 좋아요 테이블 (comment_likes)
    """
    __tablename__ = "comment_likes"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID')
    comment_id = Column(String(36), ForeignKey("comments.id"), nullable=False, comment='댓글 ID')
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment='좋아요한 사용자 ID')
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 복합 유니크 제약조건
    __table_args__ = (
        UniqueConstraint('comment_id', 'user_id', name='unique_comment_like'),
    )
    
    # 관계 정의
    comment = relationship("Comment", back_populates="likes")
