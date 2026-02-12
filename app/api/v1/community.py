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
from app.models.workout import Workout
from app.models.route import SavedRoute, RouteOption
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
    
    # 기본 쿼리 - 삭제되지 않은 공개 게시글
    query = db.query(Post).filter(
        Post.deleted_at.is_(None),
        Post.visibility == "public"
    )
    
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
        
        # 연결된 workout에서 actual_path, 시작 좌표 조회
        actual_path = None
        start_lat = None
        start_lng = None
        if post.workout_id:
            workout = db.query(Workout).filter(
                Workout.id == post.workout_id
            ).first()
            if workout:
                actual_path = workout.actual_path
                start_lat = float(workout.start_latitude) if workout.start_latitude else None
                start_lng = float(workout.start_longitude) if workout.start_longitude else None
        
        post_data = {
            "id": post.id,
            "author": {
                "id": post.author.id if post.author else None,
                "name": post.author.name if post.author else "알 수 없음",
                "avatar_url": post.author.avatar_url if post.author else None
            },
            "route_name": post.route_name,
            "shape_id": post.shape_id,
            "shape_name": post.shape_name,
            "shape_icon": post.shape_icon,
            "distance": float(post.distance) if post.distance else 0,
            "duration": post.duration or 0,
            "pace": post.pace,
            "calories": post.calories,
            "location": post.location,
            "caption": post.caption,
            "like_count": post.like_count or 0,
            "comment_count": post.comment_count or 0,
            "bookmark_count": post.bookmark_count or 0,
            "is_liked": is_liked,
            "is_bookmarked": is_bookmarked,
            "actual_path": actual_path,
            "start_latitude": start_lat,
            "start_longitude": start_lng,
            "created_at": post.created_at.isoformat()
        }
        post_list.append(post_data)
    
    # 페이지네이션 정보
    total_pages = (total_count + limit - 1) // limit
    
    return {
        "success": True,
        "data": {
            "posts": post_list,
            "pagination": {
                "current_page": page,
                "total_pages": total_pages,
                "total_count": total_count,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        },
        "message": "피드 조회 성공"
    }


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
    
    # 운동 기록 연결 시 해당 운동 유효성 검증
    if request.workout_id:
        from app.models.workout import Workout
        workout = db.query(Workout).filter(
            Workout.id == request.workout_id,
            Workout.user_id == current_user.id,
            Workout.deleted_at.is_(None)
        ).first()
        
        if not workout:
            raise ValidationException(
                message="유효하지 않은 운동 기록입니다",
                field="workout_id"
            )
        
        # 이미 공유된 운동인지 확인
        existing_post = db.query(Post).filter(
            Post.workout_id == request.workout_id,
            Post.deleted_at.is_(None)
        ).first()
        if existing_post:
            raise ValidationException(
                message="이미 공유된 운동 기록입니다",
                field="workout_id"
            )
    
    # 게시글 생성
    post = Post(
        author_id=current_user.id,
        workout_id=request.workout_id,
        route_name=request.route_name,
        shape_id=request.shape_id,
        shape_name=request.shape_name,
        shape_icon=request.shape_icon,
        distance=request.distance,
        duration=request.duration,
        pace=request.pace,
        calories=request.calories,
        caption=request.caption,
        visibility=request.visibility,
        location=request.location,
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
    post_id: str = Path(..., description="게시글 ID"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """게시글 상세 조회 엔드포인트"""
    
    post = db.query(Post).options(
        joinedload(Post.author)
    ).filter(
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
    
    # 댓글 조회
    comments = db.query(Comment).options(
        joinedload(Comment.author)
    ).filter(
        Comment.post_id == post_id,
        Comment.deleted_at.is_(None)
    ).order_by(Comment.created_at.desc()).limit(20).all()
    
    comment_list = []
    for comment in comments:
        is_comment_liked = False
        if current_user:
            is_comment_liked = db.query(CommentLike).filter(
                CommentLike.comment_id == comment.id,
                CommentLike.user_id == current_user.id
            ).first() is not None
        
        comment_list.append({
            "id": comment.id,
            "author": {
                "id": comment.author.id if comment.author else None,
                "name": comment.author.name if comment.author else "알 수 없음",
                "avatar_url": comment.author.avatar_url if comment.author else None
            },
            "content": comment.content,
            "like_count": comment.like_count or 0,
            "is_liked": is_comment_liked,
            "created_at": comment.created_at.isoformat()
        })
    
    # 연결된 workout에서 actual_path, 시작 좌표 조회
    actual_path = None
    start_lat = None
    start_lng = None
    if post.workout_id:
        workout = db.query(Workout).filter(
            Workout.id == post.workout_id
        ).first()
        if workout:
            actual_path = workout.actual_path
            start_lat = float(workout.start_latitude) if workout.start_latitude else None
            start_lng = float(workout.start_longitude) if workout.start_longitude else None
    
    return {
        "success": True,
        "data": {
            "post": {
                "id": post.id,
                "author": {
                    "id": post.author.id if post.author else None,
                    "name": post.author.name if post.author else "알 수 없음",
                    "avatar_url": post.author.avatar_url if post.author else None
                },
                "route_name": post.route_name,
                "shape_id": post.shape_id,
                "shape_name": post.shape_name,
                "shape_icon": post.shape_icon,
                "distance": float(post.distance) if post.distance else 0,
                "duration": post.duration or 0,
                "pace": post.pace,
                "calories": post.calories,
                "location": post.location,
                "caption": post.caption,
                "like_count": post.like_count or 0,
                "comment_count": post.comment_count or 0,
                "bookmark_count": post.bookmark_count or 0,
                "is_liked": is_liked,
                "is_bookmarked": is_bookmarked,
                "actual_path": actual_path,
                "start_latitude": start_lat,
                "start_longitude": start_lng,
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
    post_id: str = Path(..., description="게시글 ID"),
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
    if post.author_id != current_user.id:
        raise ForbiddenException(message="수정 권한이 없습니다")
    
    # 수정
    if request:
        if request.caption is not None:
            post.caption = request.caption
        if request.visibility is not None:
            post.visibility = request.visibility
    
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
    post_id: str = Path(..., description="게시글 ID"),
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
    if post.author_id != current_user.id:
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
    post_id: str = Path(..., description="게시글 ID"),
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
    post_id: str = Path(..., description="게시글 ID"),
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
    post_id: str = Path(..., description="게시글 ID"),
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
    
    # saved_routes에도 경로 저장
    route_id = None
    route_option_id = None
    
    if post.workout_id:
        workout = db.query(Workout).filter(Workout.id == post.workout_id).first()
        if workout:
            # workout에서 직접 route_id가 있는 경우
            if workout.route_id:
                route_id = workout.route_id
                route_option_id = workout.route_option_id
            # route_option_id만 있는 경우, route_option에서 route_id 찾기
            elif workout.route_option_id:
                route_option = db.query(RouteOption).filter(
                    RouteOption.id == workout.route_option_id
                ).first()
                if route_option:
                    route_id = route_option.route_id
                    route_option_id = workout.route_option_id
    
    # route_id가 있으면 saved_routes에 저장
    if route_id:
        # 이미 저장된 경로인지 확인
        existing_saved = db.query(SavedRoute).filter(
            SavedRoute.user_id == current_user.id,
            SavedRoute.route_id == route_id
        ).first()
        
        if not existing_saved:
            saved_route = SavedRoute(
                user_id=current_user.id,
                route_id=route_id,
                route_option_id=route_option_id
            )
            db.add(saved_route)
    
    db.commit()
    
    return CommonResponse(
        success=True,
        message="북마크되었습니다" + (" (경로도 저장되었습니다)" if route_id else "")
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
    post_id: str = Path(..., description="게시글 ID"),
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
    
    # saved_routes에서도 삭제
    route_id = None
    if post and post.workout_id:
        workout = db.query(Workout).filter(Workout.id == post.workout_id).first()
        if workout:
            if workout.route_id:
                route_id = workout.route_id
            elif workout.route_option_id:
                route_option = db.query(RouteOption).filter(
                    RouteOption.id == workout.route_option_id
                ).first()
                if route_option:
                    route_id = route_option.route_id
    
    if route_id:
        saved_route = db.query(SavedRoute).filter(
            SavedRoute.user_id == current_user.id,
            SavedRoute.route_id == route_id
        ).first()
        if saved_route:
            db.delete(saved_route)
    
    db.commit()
    
    return CommonResponse(
        success=True,
        message="북마크가 취소되었습니다" + (" (저장된 경로도 삭제되었습니다)" if route_id else "")
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
    post_id: str = Path(..., description="게시글 ID"),
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
    
    # 댓글 생성
    comment = Comment(
        post_id=post_id,
        author_id=current_user.id,
        content=request.content
    )
    
    db.add(comment)
    post.comment_count = (post.comment_count or 0) + 1
    db.commit()
    db.refresh(comment)
    
    return CommonResponse(
        success=True,
        message="댓글이 작성되었습니다",
        data={
            "comment_id": comment.id,
            "author": {
                "id": current_user.id,
                "name": current_user.name,
                "avatar_url": current_user.avatar_url
            },
            "content": comment.content,
            "created_at": comment.created_at.isoformat()
        }
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
    comment_id: str = Path(..., description="댓글 ID"),
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
    if comment.author_id != current_user.id:
        raise ForbiddenException(message="삭제 권한이 없습니다")
    
    # Soft Delete
    comment.deleted_at = datetime.utcnow()
    
    # 게시글 댓글 수 감소
    post = db.query(Post).filter(Post.id == comment.post_id).first()
    if post and post.comment_count and post.comment_count > 0:
        post.comment_count -= 1
    
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
    comment_id: str = Path(..., description="댓글 ID"),
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
                    "id": post.author.id if post.author else None,
                    "name": post.author.name if post.author else "알 수 없음",
                    "avatar_url": post.author.avatar_url if post.author else None
                },
                "route_name": post.route_name,
                "shape_icon": post.shape_icon,
                "distance": float(post.distance) if post.distance else 0,
                "duration": post.duration or 0,
                "like_count": post.like_count or 0,
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
