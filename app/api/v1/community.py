# ============================================
# app/api/v1/community.py - 커뮤니티 API 라우터
# ============================================
# 게시글, 댓글, 좋아요, 북마크 등
# 커뮤니티 관련 API를 제공합니다.
# ============================================

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from datetime import datetime

from app.db.database import get_db
from app.api.deps import get_current_user, get_current_user_optional
from app.models.user import User
from app.models.community import Post, PostLike, PostBookmark, Comment, CommentLike
from app.schemas.community import (
    PostCreateRequest, PostUpdateRequest,
    PostSchema, PostDetailSchema,
    CommentCreateRequest, CommentSchema,
    FeedResponse, FeedResponseWrapper
)
from app.schemas.common import CommonResponse, PaginationInfo
from app.core.exceptions import NotFoundException, ValidationException, ForbiddenException


router = APIRouter(prefix="/community", tags=["Community"])


# ============================================
# 피드 조회 (메인)
# ============================================
@router.get(
    "/feed",
    response_model=FeedResponseWrapper,
    summary="커뮤니티 피드 조회",
    description="""
    커뮤니티 피드를 조회합니다.
    
    **정렬 옵션:**
    - latest: 최신순 (기본값)
    - popular: 인기순 (좋아요 수)
    - trending: 트렌딩 (최근 24시간 인기)
    
    **필터:**
    - type: running/walking/all
    """
)
def get_feed(
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
    sort: str = Query("latest", description="정렬 방식 (latest/popular/trending)"),
    type: Optional[str] = Query(None, description="운동 타입 필터"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """피드 조회 엔드포인트"""
    
    # 기본 쿼리 - 삭제되지 않은 게시글
    query = db.query(Post).filter(
        Post.deleted_at.is_(None)
    )
    
    # 타입 필터
    if type and type != "all":
        query = query.filter(Post.type == type)
    
    # 정렬
    if sort == "popular":
        query = query.order_by(Post.like_count.desc(), Post.created_at.desc())
    elif sort == "trending":
        # 최근 24시간 내 좋아요 많은 순
        from datetime import timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        query = query.filter(Post.created_at >= yesterday).order_by(
            Post.like_count.desc()
        )
    else:  # latest
        query = query.order_by(Post.created_at.desc())
    
    # 전체 개수
    total_count = query.count()
    
    # 페이지네이션
    offset = (page - 1) * limit
    posts = query.options(
        joinedload(Post.author)
    ).offset(offset).limit(limit).all()
    
    # 응답 데이터 변환
    post_list = []
    for post in posts:
        # 현재 사용자의 좋아요/북마크 여부
        is_liked = False
        is_bookmarked = False
        
        if current_user:
            is_liked = db.query(PostLike).filter(
                PostLike.post_id == post.id,
                PostLike.user_id == current_user.id
            ).first() is not None
            
            is_bookmarked = db.query(PostBookmark).filter(
                PostBookmark.post_id == post.id,
                PostBookmark.user_id == current_user.id
            ).first() is not None
        
        post_list.append(PostSchema(
            id=post.id,
            author={
                "id": post.author.id,
                "name": post.author.name,
                "avatar_url": post.author.avatar_url
            },
            content=post.content,
            images=post.images or [],
            workout_data={
                "type": post.type,
                "distance": float(post.distance) if post.distance else None,
                "duration": post.duration,
                "route_shape": post.route_shape
            } if post.type else None,
            like_count=post.like_count,
            comment_count=post.comment_count,
            bookmark_count=post.bookmark_count,
            is_liked=is_liked,
            is_bookmarked=is_bookmarked,
            created_at=post.created_at
        ))
    
    # 페이지네이션 정보
    total_pages = (total_count + limit - 1) // limit
    
    return FeedResponseWrapper(
        success=True,
        data=FeedResponse(
            posts=post_list,
            pagination=PaginationInfo(
                current_page=page,
                total_pages=total_pages,
                total_count=total_count,
                has_next=page < total_pages,
                has_prev=page > 1
            )
        )
    )


# ============================================
# 게시글 작성
# ============================================
@router.post(
    "/posts",
    response_model=CommonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="게시글 작성",
    description="""
    새로운 게시글을 작성합니다.
    
    **필수:**
    - content: 게시글 내용 (최소 1자)
    
    **선택:**
    - images: 이미지 URL 배열 (최대 5개)
    - workout_id: 연결할 운동 기록 ID
    """
)
def create_post(
    request: PostCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """게시글 작성 엔드포인트"""
    
    # 운동 기록 연결 시 해당 운동 조회
    workout_data = None
    if request.workout_id:
        from app.models.workout import Workout
        workout = db.query(Workout).filter(
            Workout.id == request.workout_id,
            Workout.user_id == current_user.id,
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
            "route_shape": workout.shape_name
        }
    
    # 게시글 생성
    post = Post(
        user_id=current_user.id,
        content=request.content,
        images=request.images,
        workout_id=request.workout_id,
        type=workout_data.get("type") if workout_data else None,
        distance=workout_data.get("distance") if workout_data else None,
        duration=workout_data.get("duration") if workout_data else None,
        route_shape=workout_data.get("route_shape") if workout_data else None
    )
    
    db.add(post)
    db.commit()
    db.refresh(post)
    
    return CommonResponse(
        success=True,
        message="게시글이 작성되었습니다",
        data={"post_id": post.id}
    )


# ============================================
# 게시글 상세 조회
# ============================================
@router.get(
    "/posts/{post_id}",
    summary="게시글 상세 조회",
    description="게시글의 상세 정보와 댓글을 조회합니다."
)
def get_post_detail(
    post_id: int = Path(..., description="게시글 ID"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """게시글 상세 조회 엔드포인트"""
    
    post = db.query(Post).filter(
        Post.id == post_id,
        Post.deleted_at.is_(None)
    ).first()
    
    if not post:
        raise NotFoundException(
            resource="Post",
            resource_id=post_id
        )
    
    # 좋아요/북마크 여부
    is_liked = False
    is_bookmarked = False
    
    if current_user:
        is_liked = db.query(PostLike).filter(
            PostLike.post_id == post_id,
            PostLike.user_id == current_user.id
        ).first() is not None
        
        is_bookmarked = db.query(PostBookmark).filter(
            PostBookmark.post_id == post_id,
            PostBookmark.user_id == current_user.id
        ).first() is not None
    
    # 댓글 조회 (상위 10개)
    comments = db.query(Comment).filter(
        Comment.post_id == post_id,
        Comment.parent_id.is_(None),  # 최상위 댓글만
        Comment.deleted_at.is_(None)
    ).order_by(Comment.created_at.desc()).limit(10).all()
    
    comment_list = []
    for comment in comments:
        # 답글 조회
        replies = db.query(Comment).filter(
            Comment.parent_id == comment.id,
            Comment.deleted_at.is_(None)
        ).order_by(Comment.created_at).limit(3).all()
        
        reply_list = []
        for reply in replies:
            reply_list.append({
                "id": reply.id,
                "author": {
                    "id": reply.author.id,
                    "name": reply.author.name,
                    "avatar_url": reply.author.avatar_url
                },
                "content": reply.content,
                "like_count": reply.like_count,
                "created_at": reply.created_at.isoformat()
            })
        
        comment_list.append({
            "id": comment.id,
            "author": {
                "id": comment.author.id,
                "name": comment.author.name,
                "avatar_url": comment.author.avatar_url
            },
            "content": comment.content,
            "like_count": comment.like_count,
            "reply_count": comment.reply_count,
            "replies": reply_list,
            "created_at": comment.created_at.isoformat()
        })
    
    return {
        "success": True,
        "data": {
            "post": {
                "id": post.id,
                "author": {
                    "id": post.author.id,
                    "name": post.author.name,
                    "avatar_url": post.author.avatar_url
                },
                "content": post.content,
                "images": post.images or [],
                "workout_data": {
                    "type": post.type,
                    "distance": float(post.distance) if post.distance else None,
                    "duration": post.duration,
                    "route_shape": post.route_shape
                } if post.type else None,
                "like_count": post.like_count,
                "comment_count": post.comment_count,
                "bookmark_count": post.bookmark_count,
                "is_liked": is_liked,
                "is_bookmarked": is_bookmarked,
                "created_at": post.created_at.isoformat()
            },
            "comments": comment_list
        }
    }


# ============================================
# 게시글 수정
# ============================================
@router.patch(
    "/posts/{post_id}",
    response_model=CommonResponse,
    summary="게시글 수정",
    description="작성한 게시글을 수정합니다."
)
def update_post(
    post_id: int = Path(..., description="게시글 ID"),
    request: PostUpdateRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """게시글 수정 엔드포인트"""
    
    post = db.query(Post).filter(
        Post.id == post_id,
        Post.deleted_at.is_(None)
    ).first()
    
    if not post:
        raise NotFoundException(
            resource="Post",
            resource_id=post_id
        )
    
    # 작성자 확인
    if post.user_id != current_user.id:
        raise ForbiddenException(message="수정 권한이 없습니다")
    
    # 수정
    if request:
        if request.content is not None:
            post.content = request.content
        if request.images is not None:
            post.images = request.images
    
    post.updated_at = datetime.utcnow()
    db.commit()
    
    return CommonResponse(
        success=True,
        message="게시글이 수정되었습니다"
    )


# ============================================
# 게시글 삭제
# ============================================
@router.delete(
    "/posts/{post_id}",
    response_model=CommonResponse,
    summary="게시글 삭제",
    description="작성한 게시글을 삭제합니다."
)
def delete_post(
    post_id: int = Path(..., description="게시글 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """게시글 삭제 엔드포인트"""
    
    post = db.query(Post).filter(
        Post.id == post_id,
        Post.deleted_at.is_(None)
    ).first()
    
    if not post:
        raise NotFoundException(
            resource="Post",
            resource_id=post_id
        )
    
    # 작성자 확인
    if post.user_id != current_user.id:
        raise ForbiddenException(message="삭제 권한이 없습니다")
    
    # Soft Delete
    post.deleted_at = datetime.utcnow()
    db.commit()
    
    return CommonResponse(
        success=True,
        message="게시글이 삭제되었습니다"
    )


# ============================================
# 게시글 좋아요
# ============================================
@router.post(
    "/posts/{post_id}/like",
    response_model=CommonResponse,
    summary="게시글 좋아요",
    description="게시글에 좋아요를 누릅니다."
)
def like_post(
    post_id: int = Path(..., description="게시글 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """게시글 좋아요 엔드포인트"""
    
    post = db.query(Post).filter(
        Post.id == post_id,
        Post.deleted_at.is_(None)
    ).first()
    
    if not post:
        raise NotFoundException(
            resource="Post",
            resource_id=post_id
        )
    
    # 이미 좋아요했는지 확인
    existing_like = db.query(PostLike).filter(
        PostLike.post_id == post_id,
        PostLike.user_id == current_user.id
    ).first()
    
    if existing_like:
        raise ValidationException(
            message="이미 좋아요한 게시글입니다",
            field="post_id"
        )
    
    # 좋아요 추가
    like = PostLike(
        post_id=post_id,
        user_id=current_user.id
    )
    db.add(like)
    
    # 카운트 증가
    post.like_count += 1
    db.commit()
    
    return CommonResponse(
        success=True,
        message="좋아요를 눌렀습니다",
        data={"like_count": post.like_count}
    )


# ============================================
# 게시글 좋아요 취소
# ============================================
@router.delete(
    "/posts/{post_id}/like",
    response_model=CommonResponse,
    summary="게시글 좋아요 취소",
    description="게시글 좋아요를 취소합니다."
)
def unlike_post(
    post_id: int = Path(..., description="게시글 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """게시글 좋아요 취소 엔드포인트"""
    
    like = db.query(PostLike).filter(
        PostLike.post_id == post_id,
        PostLike.user_id == current_user.id
    ).first()
    
    if not like:
        raise NotFoundException(
            resource="PostLike",
            resource_id=post_id
        )
    
    # 좋아요 삭제
    db.delete(like)
    
    # 카운트 감소
    post = db.query(Post).filter(Post.id == post_id).first()
    if post and post.like_count > 0:
        post.like_count -= 1
    
    db.commit()
    
    return CommonResponse(
        success=True,
        message="좋아요가 취소되었습니다",
        data={"like_count": post.like_count if post else 0}
    )


# ============================================
# 게시글 북마크
# ============================================
@router.post(
    "/posts/{post_id}/bookmark",
    response_model=CommonResponse,
    summary="게시글 북마크",
    description="게시글을 북마크합니다."
)
def bookmark_post(
    post_id: int = Path(..., description="게시글 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """게시글 북마크 엔드포인트"""
    
    post = db.query(Post).filter(
        Post.id == post_id,
        Post.deleted_at.is_(None)
    ).first()
    
    if not post:
        raise NotFoundException(
            resource="Post",
            resource_id=post_id
        )
    
    # 이미 북마크했는지 확인
    existing = db.query(PostBookmark).filter(
        PostBookmark.post_id == post_id,
        PostBookmark.user_id == current_user.id
    ).first()
    
    if existing:
        raise ValidationException(
            message="이미 북마크한 게시글입니다",
            field="post_id"
        )
    
    # 북마크 추가
    bookmark = PostBookmark(
        post_id=post_id,
        user_id=current_user.id
    )
    db.add(bookmark)
    post.bookmark_count += 1
    db.commit()
    
    return CommonResponse(
        success=True,
        message="북마크되었습니다"
    )


# ============================================
# 게시글 북마크 취소
# ============================================
@router.delete(
    "/posts/{post_id}/bookmark",
    response_model=CommonResponse,
    summary="게시글 북마크 취소",
    description="게시글 북마크를 취소합니다."
)
def unbookmark_post(
    post_id: int = Path(..., description="게시글 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """게시글 북마크 취소 엔드포인트"""
    
    bookmark = db.query(PostBookmark).filter(
        PostBookmark.post_id == post_id,
        PostBookmark.user_id == current_user.id
    ).first()
    
    if not bookmark:
        raise NotFoundException(
            resource="PostBookmark",
            resource_id=post_id
        )
    
    db.delete(bookmark)
    
    post = db.query(Post).filter(Post.id == post_id).first()
    if post and post.bookmark_count > 0:
        post.bookmark_count -= 1
    
    db.commit()
    
    return CommonResponse(
        success=True,
        message="북마크가 취소되었습니다"
    )


# ============================================
# 댓글 작성
# ============================================
@router.post(
    "/posts/{post_id}/comments",
    response_model=CommonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="댓글 작성",
    description="게시글에 댓글을 작성합니다."
)
def create_comment(
    post_id: int = Path(..., description="게시글 ID"),
    request: CommentCreateRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """댓글 작성 엔드포인트"""
    
    # 게시글 존재 확인
    post = db.query(Post).filter(
        Post.id == post_id,
        Post.deleted_at.is_(None)
    ).first()
    
    if not post:
        raise NotFoundException(
            resource="Post",
            resource_id=post_id
        )
    
    # 부모 댓글 확인 (답글인 경우)
    if request.parent_id:
        parent = db.query(Comment).filter(
            Comment.id == request.parent_id,
            Comment.deleted_at.is_(None)
        ).first()
        
        if not parent:
            raise NotFoundException(
                resource="Comment",
                resource_id=request.parent_id
            )
        
        # 부모 댓글의 답글 수 증가
        parent.reply_count += 1
    
    # 댓글 생성
    comment = Comment(
        post_id=post_id,
        user_id=current_user.id,
        parent_id=request.parent_id,
        content=request.content
    )
    
    db.add(comment)
    post.comment_count += 1
    db.commit()
    db.refresh(comment)
    
    return CommonResponse(
        success=True,
        message="댓글이 작성되었습니다",
        data={"comment_id": comment.id}
    )


# ============================================
# 댓글 삭제
# ============================================
@router.delete(
    "/comments/{comment_id}",
    response_model=CommonResponse,
    summary="댓글 삭제",
    description="작성한 댓글을 삭제합니다."
)
def delete_comment(
    comment_id: int = Path(..., description="댓글 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """댓글 삭제 엔드포인트"""
    
    comment = db.query(Comment).filter(
        Comment.id == comment_id,
        Comment.deleted_at.is_(None)
    ).first()
    
    if not comment:
        raise NotFoundException(
            resource="Comment",
            resource_id=comment_id
        )
    
    # 작성자 확인
    if comment.user_id != current_user.id:
        raise ForbiddenException(message="삭제 권한이 없습니다")
    
    # Soft Delete
    comment.deleted_at = datetime.utcnow()
    
    # 게시글 댓글 수 감소
    post = db.query(Post).filter(Post.id == comment.post_id).first()
    if post and post.comment_count > 0:
        post.comment_count -= 1
    
    # 부모 댓글 답글 수 감소
    if comment.parent_id:
        parent = db.query(Comment).filter(Comment.id == comment.parent_id).first()
        if parent and parent.reply_count > 0:
            parent.reply_count -= 1
    
    db.commit()
    
    return CommonResponse(
        success=True,
        message="댓글이 삭제되었습니다"
    )


# ============================================
# 댓글 좋아요
# ============================================
@router.post(
    "/comments/{comment_id}/like",
    response_model=CommonResponse,
    summary="댓글 좋아요",
    description="댓글에 좋아요를 누릅니다."
)
def like_comment(
    comment_id: int = Path(..., description="댓글 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """댓글 좋아요 엔드포인트"""
    
    comment = db.query(Comment).filter(
        Comment.id == comment_id,
        Comment.deleted_at.is_(None)
    ).first()
    
    if not comment:
        raise NotFoundException(
            resource="Comment",
            resource_id=comment_id
        )
    
    # 이미 좋아요했는지 확인
    existing = db.query(CommentLike).filter(
        CommentLike.comment_id == comment_id,
        CommentLike.user_id == current_user.id
    ).first()
    
    if existing:
        raise ValidationException(
            message="이미 좋아요한 댓글입니다",
            field="comment_id"
        )
    
    # 좋아요 추가
    like = CommentLike(
        comment_id=comment_id,
        user_id=current_user.id
    )
    db.add(like)
    comment.like_count += 1
    db.commit()
    
    return CommonResponse(
        success=True,
        message="좋아요를 눌렀습니다",
        data={"like_count": comment.like_count}
    )


# ============================================
# 내 북마크 목록
# ============================================
@router.get(
    "/bookmarks",
    summary="내 북마크 목록",
    description="북마크한 게시글 목록을 조회합니다."
)
def get_my_bookmarks(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """내 북마크 목록 조회 엔드포인트"""
    
    query = db.query(PostBookmark).filter(
        PostBookmark.user_id == current_user.id
    ).order_by(PostBookmark.created_at.desc())
    
    total_count = query.count()
    offset = (page - 1) * limit
    bookmarks = query.offset(offset).limit(limit).all()
    
    post_list = []
    for bookmark in bookmarks:
        post = bookmark.post
        if post and not post.deleted_at:
            post_list.append({
                "id": post.id,
                "author": {
                    "id": post.author.id,
                    "name": post.author.name,
                    "avatar_url": post.author.avatar_url
                },
                "content": post.content[:100] + "..." if len(post.content) > 100 else post.content,
                "images": post.images[:1] if post.images else [],
                "like_count": post.like_count,
                "bookmarked_at": bookmark.created_at.isoformat()
            })
    
    total_pages = (total_count + limit - 1) // limit
    
    return {
        "success": True,
        "data": {
            "bookmarks": post_list,
            "pagination": {
                "current_page": page,
                "total_pages": total_pages,
                "total_count": total_count
            }
        }
    }
