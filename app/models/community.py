# ============================================
# app/models/community.py - 커뮤니티 관련 데이터베이스 모델
# ============================================
# 이 파일은 게시물, 좋아요, 댓글, 팔로우 등 커뮤니티 기능 테이블을 정의합니다.
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
    - 실제 카운트는 관련 테이블을 COUNT하면 되지만, 매번 COUNT하면 느림
    """
    __tablename__ = "posts"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    author_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # 공유된 운동 ID (1:1 관계, 중복 공유 방지)
    workout_id = Column(String(36), ForeignKey("workouts.id"), unique=True, nullable=True)
    
    # ========== 경로/운동 정보 (스냅샷) ==========
    # 스냅샷: 원본이 변경되어도 게시물의 정보는 유지됨
    route_name = Column(String(100), nullable=False)    # 경로 이름
    shape_id = Column(String(50), nullable=True)        # 도형 ID
    shape_name = Column(String(50), nullable=True)      # 도형 이름
    shape_icon = Column(String(50), nullable=True)      # 도형 아이콘
    
    # 운동 통계
    distance = Column(DECIMAL(5, 2), nullable=False)    # 거리 (km)
    duration = Column(Integer, nullable=False)          # 소요 시간 (초)
    pace = Column(String(20), nullable=True)            # 페이스
    calories = Column(Integer, nullable=True)           # 칼로리
    
    location = Column(String(100), nullable=True)       # 위치 (여의도 한강공원)
    
    # ========== 게시물 내용 ==========
    caption = Column(Text, nullable=True)               # 캡션 (선택적)
    visibility = Column(String(20), nullable=False, default="public")  # public/private
    
    # ========== 통계 (캐시) ==========
    like_count = Column(Integer, default=0)             # 좋아요 수
    comment_count = Column(Integer, default=0)          # 댓글 수
    bookmark_count = Column(Integer, default=0)         # 북마크 수
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)        # 삭제일 (Soft Delete)
    
    # ========== 관계 정의 ==========
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
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    post_id = Column(String(36), ForeignKey("posts.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
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
    북마크한 게시물은 저장된 경로 목록에서 볼 수 있습니다.
    """
    __tablename__ = "post_bookmarks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    post_id = Column(String(36), ForeignKey("posts.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
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
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    post_id = Column(String(36), ForeignKey("posts.id"), nullable=False)
    author_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    content = Column(String(500), nullable=False)       # 댓글 내용 (최대 500자)
    like_count = Column(Integer, default=0)             # 좋아요 수 (캐시)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)        # 삭제일 (Soft Delete)
    
    # 관계 정의
    post = relationship("Post", back_populates="comments")
    likes = relationship("CommentLike", back_populates="comment", lazy="select")


class CommentLike(Base):
    """
    댓글 좋아요 테이블 (comment_likes)
    """
    __tablename__ = "comment_likes"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    comment_id = Column(String(36), ForeignKey("comments.id"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 복합 유니크 제약조건
    __table_args__ = (
        UniqueConstraint('comment_id', 'user_id', name='unique_comment_like'),
    )
    
    # 관계 정의
    comment = relationship("Comment", back_populates="likes")


class Follow(Base):
    """
    팔로우 테이블 (follows)
    
    사용자 간의 팔로우 관계를 저장합니다.
    
    [신입 개발자를 위한 팁]
    - follower_id: 팔로우하는 사람 (나)
    - following_id: 팔로우 받는 사람 (상대방)
    - 예: A가 B를 팔로우 → follower_id=A, following_id=B
    """
    __tablename__ = "follows"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    follower_id = Column(String(36), ForeignKey("users.id"), nullable=False)   # 팔로우하는 사람
    following_id = Column(String(36), ForeignKey("users.id"), nullable=False)  # 팔로우 받는 사람
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 복합 유니크 제약조건 (중복 팔로우 불가)
    __table_args__ = (
        UniqueConstraint('follower_id', 'following_id', name='unique_follow'),
    )
