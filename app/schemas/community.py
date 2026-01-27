# ============================================
# app/schemas/community.py - 커뮤니티 관련 스키마
# ============================================
# 피드, 게시물, 좋아요, 댓글 관련 요청/응답 스키마를 정의합니다.
# ============================================

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================
# 공통 스키마
# ============================================

class UserBadgeSchema(BaseModel):
    """사용자 배지 스키마 (간단)"""
    icon: str
    name: str


class PostUserSchema(BaseModel):
    """게시물 작성자 스키마"""
    id: str
    name: str
    avatar: Optional[str] = None
    badges: Optional[List[UserBadgeSchema]] = None
    stats: Optional[Dict[str, Any]] = None


class PostRouteSchema(BaseModel):
    """게시물 경로 정보 스키마"""
    shape_id: Optional[str] = None
    shape_name: Optional[str] = None
    icon_name: Optional[str] = None
    distance: str  # "5.2km"
    duration: str  # "30분"
    pace: Optional[str] = None
    calories: Optional[int] = None
    location: Optional[str] = None  # "한강공원"
    route_data: Optional[Dict[str, Any]] = None


class PostStatsSchema(BaseModel):
    """게시물 통계 스키마"""
    likes: int = 0
    comments: int = 0
    bookmarks: int = 0
    views: Optional[int] = None


class PostInteractionsSchema(BaseModel):
    """게시물 상호작용 스키마 (현재 사용자 기준)"""
    is_liked: bool = False
    is_bookmarked: bool = False
    has_commented: Optional[bool] = None


class PostPreviewSchema(BaseModel):
    """게시물 미리보기 스키마"""
    image_url: Optional[str] = None
    map_thumbnail: Optional[str] = None


# ============================================
# 게시물 스키마
# ============================================

class PostSchema(BaseModel):
    """
    게시물 스키마
    
    커뮤니티 피드에서 사용하는 게시물 정보입니다.
    """
    id: str
    user: PostUserSchema
    route: PostRouteSchema
    caption: Optional[str] = None
    stats: PostStatsSchema
    interactions: PostInteractionsSchema
    preview: Optional[PostPreviewSchema] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class PostDetailSchema(PostSchema):
    """게시물 상세 스키마"""
    achievements: Optional[List[Dict[str, str]]] = None


# ============================================
# 댓글 스키마
# ============================================

class CommentUserSchema(BaseModel):
    """댓글 작성자 스키마"""
    id: str
    name: str
    avatar: Optional[str] = None
    badges: Optional[List[UserBadgeSchema]] = None


class CommentSchema(BaseModel):
    """댓글 스키마"""
    id: str
    user: CommentUserSchema
    content: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    likes: int = 0
    is_liked: bool = False
    is_edited: bool = False
    is_author: bool = False  # 내 댓글인지 여부
    
    class Config:
        from_attributes = True


# ============================================
# 요청 스키마
# ============================================

class CommentCreateRequest(BaseModel):
    """댓글 작성 요청 스키마"""
    content: str = Field(..., min_length=1, max_length=500, description="댓글 내용")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "멋진 경로네요! 저도 도전해볼게요 💪"
            }
        }


class CommentUpdateRequest(BaseModel):
    """댓글 수정 요청 스키마"""
    content: str = Field(..., min_length=1, max_length=500, description="수정할 내용")


# ============================================
# 응답 스키마
# ============================================

class PaginationSchema(BaseModel):
    """페이지네이션 스키마"""
    current_page: int = 1
    total_pages: int = 1
    total_count: Optional[int] = None
    has_next: bool = False
    has_prev: bool = False
    next_cursor: Optional[str] = None


class FeedResponse(BaseModel):
    """
    피드 응답 스키마
    
    GET /api/v1/community/feed 응답에 사용됩니다.
    """
    posts: List[PostSchema]
    pagination: PaginationSchema


class FeedResponseWrapper(BaseModel):
    """피드 응답 래퍼"""
    success: bool = True
    data: FeedResponse
    message: str = "피드 조회 성공"


class PostDetailResponseWrapper(BaseModel):
    """게시물 상세 응답 래퍼"""
    success: bool = True
    data: PostDetailSchema


class LikeResponse(BaseModel):
    """좋아요 응답 스키마"""
    is_liked: bool
    like_count: int
    liked_at: Optional[datetime] = None


class LikeResponseWrapper(BaseModel):
    """좋아요 응답 래퍼"""
    success: bool = True
    data: LikeResponse
    message: str


class BookmarkResponse(BaseModel):
    """북마크 응답 스키마"""
    is_bookmarked: bool
    bookmarked_at: Optional[datetime] = None


class BookmarkResponseWrapper(BaseModel):
    """북마크 응답 래퍼"""
    success: bool = True
    data: BookmarkResponse
    message: str


class CommentListResponse(BaseModel):
    """댓글 목록 응답 스키마"""
    comments: List[CommentSchema]
    pagination: PaginationSchema


class CommentListResponseWrapper(BaseModel):
    """댓글 목록 응답 래퍼"""
    success: bool = True
    data: CommentListResponse
    message: str = "댓글 조회 성공"


class CommentCreateResponse(BaseModel):
    """댓글 작성 응답 스키마"""
    comment_id: str
    user: CommentUserSchema
    content: str
    created_at: datetime
    likes: int = 0


class CommentCreateResponseWrapper(BaseModel):
    """댓글 작성 응답 래퍼"""
    success: bool = True
    data: CommentCreateResponse
    message: str = "댓글이 작성되었습니다"


class CommentUpdateResponse(BaseModel):
    """댓글 수정 응답 스키마"""
    comment_id: str
    content: str
    updated_at: datetime
    is_edited: bool = True


class CommentUpdateResponseWrapper(BaseModel):
    """댓글 수정 응답 래퍼"""
    success: bool = True
    data: CommentUpdateResponse
    message: str = "댓글이 수정되었습니다"


class CommentDeleteResponse(BaseModel):
    """댓글 삭제 응답 스키마"""
    success: bool = True
    message: str = "댓글이 삭제되었습니다"


# ============================================
# API에서 사용하는 추가 스키마
# ============================================

class AuthorSchema(BaseModel):
    """작성자 정보 스키마"""
    id: int
    name: str
    avatar: Optional[str] = None


class WorkoutDataSchema(BaseModel):
    """운동 데이터 스키마 (게시물용)"""
    type: Optional[str] = None  # running/walking
    distance: Optional[float] = None  # km
    duration: Optional[int] = None  # 초
    route_shape: Optional[str] = None


class PostSchema(BaseModel):
    """게시물 스키마 (간소화 버전)"""
    id: int
    author: AuthorSchema
    content: str
    images: List[str] = []
    workout_data: Optional[WorkoutDataSchema] = None
    like_count: int = 0
    comment_count: int = 0
    bookmark_count: int = 0
    is_liked: bool = False
    is_bookmarked: bool = False
    created_at: datetime
    
    class Config:
        from_attributes = True


class PostDetailSchema(PostSchema):
    """게시물 상세 스키마"""
    updated_at: Optional[datetime] = None


class PostCreateRequest(BaseModel):
    """게시물 작성 요청 스키마"""
    content: str = Field(..., min_length=1, max_length=2000, description="게시물 내용")
    images: Optional[List[str]] = Field(None, max_length=5, description="이미지 URL 배열 (최대 5개)")
    workout_id: Optional[int] = Field(None, description="연결할 운동 기록 ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "오늘 한강에서 5km 러닝 완주! 💪",
                "images": ["https://example.com/image1.jpg"],
                "workout_id": 123
            }
        }


class PostUpdateRequest(BaseModel):
    """게시물 수정 요청 스키마"""
    content: Optional[str] = Field(None, min_length=1, max_length=2000)
    images: Optional[List[str]] = Field(None, max_length=5)


class CommentCreateRequest(BaseModel):
    """댓글 작성 요청 스키마"""
    content: str = Field(..., min_length=1, max_length=500, description="댓글 내용")
    parent_id: Optional[int] = Field(None, description="부모 댓글 ID (답글인 경우)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "멋진 기록이네요! 저도 도전해볼게요 💪"
            }
        }


class FeedResponse(BaseModel):
    """피드 응답 스키마"""
    posts: List[PostSchema]
    pagination: "PaginationInfo"


class FeedResponseWrapper(BaseModel):
    """피드 응답 래퍼"""
    success: bool = True
    data: FeedResponse


# 순환 참조 해결을 위한 import
from app.schemas.common import PaginationInfo
FeedResponse.model_rebuild()
