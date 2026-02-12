# ============================================
# app/services/community_service.py - 커뮤니티 서비스
# ============================================
# 게시글, 댓글, 좋아요 등 커뮤니티 관련 비즈니스 로직을 처리합니다.
# ============================================

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.models.user import User
from app.models.community import Post, PostLike, PostBookmark, Comment, CommentLike
from app.core.exceptions import NotFoundException, ValidationException, ForbiddenException


class CommunityService:
    """
    커뮤니티 서비스 클래스
    
    [신입 개발자를 위한 설명]
    커뮤니티 관련 모든 비즈니스 로직을 담당합니다.
    - 게시글 CRUD
    - 댓글 CRUD
    - 좋아요/북마크
    - 피드 조회
    """
    
    def __init__(self, db: Session):
        """
        CommunityService 초기화
        
        Args:
            db: 데이터베이스 세션
        """
        self.db = db
    
    
    # ============================================
    # 피드 관련
    # ============================================
    
    def get_feed(
        self,
        user_id: str = None,
        page: int = 1,
        limit: int = 20,
        sort: str = "latest"
    ) -> tuple[List[Post], int]:
        """
        피드 조회
        
        Args:
            user_id: 현재 사용자 ID (없으면 게스트)
            page: 페이지 번호
            limit: 페이지당 항목 수
            sort: 정렬 방식 (latest/popular/trending)
        
        Returns:
            tuple: (게시글 목록, 전체 개수)
        """
        query = self.db.query(Post).filter(
            Post.deleted_at.is_(None),
            Post.visibility == "public"
        )
        
        # 정렬
        if sort == "popular":
            query = query.order_by(Post.like_count.desc(), Post.created_at.desc())
        elif sort == "trending":
            yesterday = datetime.utcnow() - timedelta(days=1)
            query = query.filter(Post.created_at >= yesterday).order_by(
                Post.like_count.desc()
            )
        else:
            query = query.order_by(Post.created_at.desc())
        
        total = query.count()
        
        offset = (page - 1) * limit
        posts = query.options(joinedload(Post.author)).offset(offset).limit(limit).all()
        
        return posts, total
    
    
    # ============================================
    # 게시글 관련
    # ============================================
    
    def create_post(
        self,
        user_id: str,
        route_name: str,
        distance: float,
        duration: int,
        workout_id: str = None,
        shape_id: str = None,
        shape_name: str = None,
        shape_icon: str = None,
        pace: str = None,
        calories: int = None,
        caption: str = None,
        visibility: str = "public",
        location: str = None
    ) -> Post:
        """
        게시글 작성
        
        Args:
            user_id: 작성자 ID
            route_name: 경로 이름
            distance: 거리 (km)
            duration: 시간 (초)
            workout_id: 연결할 운동 기록 ID
            shape_id: 도형 ID
            shape_name: 도형 이름
            shape_icon: 도형 아이콘
            pace: 평균 페이스
            calories: 칼로리
            caption: 캡션
            visibility: 공개 범위
            location: 위치
        
        Returns:
            Post: 생성된 게시글
        """
        # 운동 기록 연결 시 유효성 검증
        if workout_id:
            from app.models.workout import Workout
            workout = self.db.query(Workout).filter(
                Workout.id == workout_id,
                Workout.user_id == user_id,
                Workout.deleted_at.is_(None)
            ).first()
            
            if not workout:
                raise ValidationException(
                    message="유효하지 않은 운동 기록입니다",
                    field="workout_id"
                )
            
            # 이미 공유된 운동인지 확인
            existing_post = self.db.query(Post).filter(
                Post.workout_id == workout_id,
                Post.deleted_at.is_(None)
            ).first()
            if existing_post:
                raise ValidationException(
                    message="이미 공유된 운동 기록입니다",
                    field="workout_id"
                )
        
        post = Post(
            author_id=user_id,
            workout_id=workout_id,
            route_name=route_name,
            shape_id=shape_id,
            shape_name=shape_name,
            shape_icon=shape_icon,
            distance=distance,
            duration=duration,
            pace=pace,
            calories=calories,
            caption=caption,
            visibility=visibility,
            location=location
        )
        
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        
        return post
    
    
    def get_post(self, post_id: str) -> Optional[Post]:
        """
        게시글 상세 조회
        
        Args:
            post_id: 게시글 ID
        
        Returns:
            Optional[Post]: 게시글 (없으면 None)
        """
        return self.db.query(Post).filter(
            Post.id == post_id,
            Post.deleted_at.is_(None)
        ).first()
    
    
    def update_post(
        self,
        post_id: str,
        user_id: str,
        caption: str = None,
        visibility: str = None
    ) -> Post:
        """
        게시글 수정
        
        Args:
            post_id: 게시글 ID
            user_id: 사용자 ID
            caption: 수정할 캡션
            visibility: 수정할 공개 범위
        
        Returns:
            Post: 수정된 게시글
        """
        post = self._get_post_with_permission(post_id, user_id)
        
        if caption is not None:
            post.caption = caption
        if visibility is not None:
            post.visibility = visibility
        
        post.updated_at = datetime.utcnow()
        self.db.commit()
        
        return post
    
    
    def delete_post(self, post_id: str, user_id: str) -> bool:
        """
        게시글 삭제 (Soft Delete)
        
        Args:
            post_id: 게시글 ID
            user_id: 사용자 ID
        
        Returns:
            bool: 삭제 성공 여부
        """
        post = self._get_post_with_permission(post_id, user_id)
        post.deleted_at = datetime.utcnow()
        self.db.commit()
        
        return True
    
    
    # ============================================
    # 좋아요 관련
    # ============================================
    
    def like_post(self, post_id: str, user_id: str) -> int:
        """
        게시글 좋아요
        
        Args:
            post_id: 게시글 ID
            user_id: 사용자 ID
        
        Returns:
            int: 좋아요 수
        """
        post = self._get_post(post_id)
        
        existing = self.db.query(PostLike).filter(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id
        ).first()
        
        if existing:
            raise ValidationException(
                message="이미 좋아요한 게시글입니다",
                field="post_id"
            )
        
        like = PostLike(post_id=post_id, user_id=user_id)
        self.db.add(like)
        
        post.like_count += 1
        self.db.commit()
        
        return post.like_count
    
    
    def unlike_post(self, post_id: str, user_id: str) -> int:
        """
        게시글 좋아요 취소
        
        Args:
            post_id: 게시글 ID
            user_id: 사용자 ID
        
        Returns:
            int: 좋아요 수
        """
        like = self.db.query(PostLike).filter(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id
        ).first()
        
        if not like:
            raise NotFoundException(
                resource="PostLike",
                resource_id=post_id
            )
        
        self.db.delete(like)
        
        post = self._get_post(post_id)
        if post.like_count > 0:
            post.like_count -= 1
        
        self.db.commit()
        
        return post.like_count
    
    
    def is_liked(self, post_id: str, user_id: str) -> bool:
        """좋아요 여부 확인"""
        return self.db.query(PostLike).filter(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id
        ).first() is not None
    
    
    # ============================================
    # 북마크 관련
    # ============================================
    
    def bookmark_post(self, post_id: str, user_id: str) -> bool:
        """
        게시글 북마크
        
        Args:
            post_id: 게시글 ID
            user_id: 사용자 ID
        
        Returns:
            bool: 북마크 성공 여부
        """
        post = self._get_post(post_id)
        
        existing = self.db.query(PostBookmark).filter(
            PostBookmark.post_id == post_id,
            PostBookmark.user_id == user_id
        ).first()
        
        if existing:
            raise ValidationException(
                message="이미 북마크한 게시글입니다",
                field="post_id"
            )
        
        bookmark = PostBookmark(post_id=post_id, user_id=user_id)
        self.db.add(bookmark)
        
        post.bookmark_count += 1
        self.db.commit()
        
        return True
    
    
    def unbookmark_post(self, post_id: str, user_id: str) -> bool:
        """게시글 북마크 취소"""
        bookmark = self.db.query(PostBookmark).filter(
            PostBookmark.post_id == post_id,
            PostBookmark.user_id == user_id
        ).first()
        
        if not bookmark:
            raise NotFoundException(
                resource="PostBookmark",
                resource_id=post_id
            )
        
        self.db.delete(bookmark)
        
        post = self._get_post(post_id)
        if post.bookmark_count > 0:
            post.bookmark_count -= 1
        
        self.db.commit()
        
        return True
    
    
    def is_bookmarked(self, post_id: str, user_id: str) -> bool:
        """북마크 여부 확인"""
        return self.db.query(PostBookmark).filter(
            PostBookmark.post_id == post_id,
            PostBookmark.user_id == user_id
        ).first() is not None
    
    
    def get_bookmarked_posts(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20
    ) -> tuple[List[Post], int]:
        """북마크한 게시글 목록 조회"""
        query = self.db.query(PostBookmark).filter(
            PostBookmark.user_id == user_id
        ).order_by(PostBookmark.created_at.desc())
        
        total = query.count()
        
        offset = (page - 1) * limit
        bookmarks = query.offset(offset).limit(limit).all()
        
        posts = []
        for bookmark in bookmarks:
            if bookmark.post and not bookmark.post.deleted_at:
                posts.append(bookmark.post)
        
        return posts, total
    
    
    # ============================================
    # 댓글 관련
    # ============================================
    
    def create_comment(
        self,
        post_id: str,
        user_id: str,
        content: str
    ) -> Comment:
        """
        댓글 작성
        
        Args:
            post_id: 게시글 ID
            user_id: 작성자 ID
            content: 댓글 내용
        
        Returns:
            Comment: 생성된 댓글
        """
        post = self._get_post(post_id)
        
        comment = Comment(
            post_id=post_id,
            author_id=user_id,
            content=content
        )
        
        self.db.add(comment)
        post.comment_count = (post.comment_count or 0) + 1
        self.db.commit()
        self.db.refresh(comment)
        
        return comment
    
    
    def delete_comment(self, comment_id: str, user_id: str) -> bool:
        """
        댓글 삭제
        
        Args:
            comment_id: 댓글 ID
            user_id: 사용자 ID
        
        Returns:
            bool: 삭제 성공 여부
        """
        comment = self.db.query(Comment).filter(
            Comment.id == comment_id,
            Comment.deleted_at.is_(None)
        ).first()
        
        if not comment:
            raise NotFoundException(
                resource="Comment",
                resource_id=comment_id
            )
        
        if comment.author_id != user_id:
            raise ForbiddenException(message="삭제 권한이 없습니다")
        
        comment.deleted_at = datetime.utcnow()
        
        # 게시글 댓글 수 감소
        post = self.db.query(Post).filter(Post.id == comment.post_id).first()
        if post and post.comment_count and post.comment_count > 0:
            post.comment_count -= 1
        
        self.db.commit()
        
        return True
    
    
    def get_comments(
        self,
        post_id: str,
        page: int = 1,
        limit: int = 20
    ) -> tuple[List[Comment], int]:
        """
        댓글 목록 조회
        
        Args:
            post_id: 게시글 ID
            page: 페이지 번호
            limit: 페이지당 항목 수
        
        Returns:
            tuple: (댓글 목록, 전체 개수)
        """
        query = self.db.query(Comment).filter(
            Comment.post_id == post_id,
            Comment.deleted_at.is_(None)
        )
        
        query = query.order_by(Comment.created_at.desc())
        
        total = query.count()
        
        offset = (page - 1) * limit
        comments = query.offset(offset).limit(limit).all()
        
        return comments, total
    
    
    # ============================================
    # 헬퍼 메서드
    # ============================================
    
    def _get_post(self, post_id: str) -> Post:
        """게시글 조회 (내부용)"""
        post = self.db.query(Post).filter(
            Post.id == post_id,
            Post.deleted_at.is_(None)
        ).first()
        
        if not post:
            raise NotFoundException(
                resource="Post",
                resource_id=post_id
            )
        
        return post
    
    
    def _get_post_with_permission(self, post_id: str, user_id: str) -> Post:
        """게시글 조회 + 권한 확인 (내부용)"""
        post = self._get_post(post_id)
        
        if post.author_id != user_id:
            raise ForbiddenException(message="권한이 없습니다")
        
        return post
