# ============================================
# app/services/community_service.py - 커뮤니티 서비스
# ============================================
# 게시글, 댓글, 좋아요, 팔로우 등 커뮤니티 관련 비즈니스 로직을 처리합니다.
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
    - 팔로우/언팔로우
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
        user_id: int = None,
        page: int = 1,
        limit: int = 20,
        sort: str = "latest",
        post_type: str = None,
        following_only: bool = False
    ) -> tuple[List[Post], int]:
        """
        피드 조회
        
        Args:
            user_id: 현재 사용자 ID (없으면 게스트)
            page: 페이지 번호
            limit: 페이지당 항목 수
            sort: 정렬 방식 (latest/popular/trending)
            post_type: 게시글 타입 필터
            following_only: 팔로우한 사용자만
        
        Returns:
            tuple: (게시글 목록, 전체 개수)
        """
        query = self.db.query(Post).filter(Post.deleted_at.is_(None))
        
        # 타입 필터
        if post_type and post_type != "all":
            query = query.filter(Post.type == post_type)
        
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
        user_id: int,
        content: str,
        images: List[str] = None,
        workout_id: int = None
    ) -> Post:
        """
        게시글 작성
        
        Args:
            user_id: 작성자 ID
            content: 게시글 내용
            images: 이미지 URL 배열
            workout_id: 연결할 운동 기록 ID
        
        Returns:
            Post: 생성된 게시글
        """
        # 운동 기록 연결 시 데이터 조회
        workout_data = None
        if workout_id:
            from app.models.workout import Workout
            workout = self.db.query(Workout).filter(
                Workout.id == workout_id,
                Workout.user_id == user_id,
                Workout.status == "completed"
            ).first()
            
            if not workout:
                raise ValidationException(
                    message="유효하지 않은 운동 기록입니다",
                    field="workout_id"
                )
            
            workout_data = {
                "type": workout.type,
                "distance": float(workout.distance) if workout.distance else None,
                "duration": workout.duration,
                "route_name": workout.route_name
            }
        
        post = Post(
            user_id=user_id,
            content=content,
            images=images,
            workout_id=workout_id,
            type=workout_data.get("type") if workout_data else None,
            distance=workout_data.get("distance") if workout_data else None,
            duration=workout_data.get("duration") if workout_data else None,
            route_shape=workout_data.get("route_name") if workout_data else None
        )
        
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)
        
        return post
    
    
    def get_post(self, post_id: int) -> Optional[Post]:
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
        post_id: int,
        user_id: int,
        content: str = None,
        images: List[str] = None
    ) -> Post:
        """
        게시글 수정
        
        Args:
            post_id: 게시글 ID
            user_id: 사용자 ID
            content: 수정할 내용
            images: 수정할 이미지
        
        Returns:
            Post: 수정된 게시글
        """
        post = self._get_post_with_permission(post_id, user_id)
        
        if content is not None:
            post.content = content
        if images is not None:
            post.images = images
        
        post.updated_at = datetime.utcnow()
        self.db.commit()
        
        return post
    
    
    def delete_post(self, post_id: int, user_id: int) -> bool:
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
    
    def like_post(self, post_id: int, user_id: int) -> int:
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
    
    
    def unlike_post(self, post_id: int, user_id: int) -> int:
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
    
    
    def is_liked(self, post_id: int, user_id: int) -> bool:
        """좋아요 여부 확인"""
        return self.db.query(PostLike).filter(
            PostLike.post_id == post_id,
            PostLike.user_id == user_id
        ).first() is not None
    
    
    # ============================================
    # 북마크 관련
    # ============================================
    
    def bookmark_post(self, post_id: int, user_id: int) -> bool:
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
    
    
    def unbookmark_post(self, post_id: int, user_id: int) -> bool:
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
    
    
    def is_bookmarked(self, post_id: int, user_id: int) -> bool:
        """북마크 여부 확인"""
        return self.db.query(PostBookmark).filter(
            PostBookmark.post_id == post_id,
            PostBookmark.user_id == user_id
        ).first() is not None
    
    
    def get_bookmarked_posts(
        self,
        user_id: int,
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
        post_id: int,
        user_id: int,
        content: str,
        parent_id: int = None
    ) -> Comment:
        """
        댓글 작성
        
        Args:
            post_id: 게시글 ID
            user_id: 작성자 ID
            content: 댓글 내용
            parent_id: 부모 댓글 ID (답글인 경우)
        
        Returns:
            Comment: 생성된 댓글
        """
        post = self._get_post(post_id)
        
        # 부모 댓글 확인 (답글인 경우)
        if parent_id:
            parent = self.db.query(Comment).filter(
                Comment.id == parent_id,
                Comment.deleted_at.is_(None)
            ).first()
            
            if not parent:
                raise NotFoundException(
                    resource="Comment",
                    resource_id=parent_id
                )
            
            parent.reply_count += 1
        
        comment = Comment(
            post_id=post_id,
            user_id=user_id,
            parent_id=parent_id,
            content=content
        )
        
        self.db.add(comment)
        post.comment_count += 1
        self.db.commit()
        self.db.refresh(comment)
        
        return comment
    
    
    def delete_comment(self, comment_id: int, user_id: int) -> bool:
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
        
        if comment.user_id != user_id:
            raise ForbiddenException(message="삭제 권한이 없습니다")
        
        comment.deleted_at = datetime.utcnow()
        
        # 게시글 댓글 수 감소
        post = self.db.query(Post).filter(Post.id == comment.post_id).first()
        if post and post.comment_count > 0:
            post.comment_count -= 1
        
        # 부모 댓글 답글 수 감소
        if comment.parent_id:
            parent = self.db.query(Comment).filter(
                Comment.id == comment.parent_id
            ).first()
            if parent and parent.reply_count > 0:
                parent.reply_count -= 1
        
        self.db.commit()
        
        return True
    
    
    def get_comments(
        self,
        post_id: int,
        page: int = 1,
        limit: int = 20,
        parent_id: int = None
    ) -> tuple[List[Comment], int]:
        """
        댓글 목록 조회
        
        Args:
            post_id: 게시글 ID
            page: 페이지 번호
            limit: 페이지당 항목 수
            parent_id: 부모 댓글 ID (답글 조회 시)
        
        Returns:
            tuple: (댓글 목록, 전체 개수)
        """
        query = self.db.query(Comment).filter(
            Comment.post_id == post_id,
            Comment.deleted_at.is_(None)
        )
        
        if parent_id is None:
            query = query.filter(Comment.parent_id.is_(None))
        else:
            query = query.filter(Comment.parent_id == parent_id)
        
        query = query.order_by(Comment.created_at.desc())
        
        total = query.count()
        
        offset = (page - 1) * limit
        comments = query.offset(offset).limit(limit).all()
        
        return comments, total
    
    
    # ============================================
    # 헬퍼 메서드
    # ============================================
    
    def _get_post(self, post_id: int) -> Post:
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
    
    
    def _get_post_with_permission(self, post_id: int, user_id: int) -> Post:
        """게시글 조회 + 권한 확인 (내부용)"""
        post = self._get_post(post_id)
        
        if post.user_id != user_id:
            raise ForbiddenException(message="권한이 없습니다")
        
        return post
