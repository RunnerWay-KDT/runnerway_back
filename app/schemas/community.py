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

class PostUserSchema(BaseModel):
    """게시물 작성자 스키마"""
    id: str
    name: str
    avatar_url: Optional[str] = None


class PostRouteSchema(BaseModel):
    """게시물 경로 정보 스키마"""
    shape_id: Optional[str] = None
    shape_name: Optional[str] = None
    shape_icon: Optional[str] = None
    distance: float  # km
    duration: int  # 초
    pace: Optional[str] = None
    calories: Optional[int] = None
    location: Optional[str] = None


class PostStatsSchema(BaseModel):
    """게시물 통계 스키마"""
    likes: int = 0
    comments: int = 0
    bookmarks: int = 0


class PostInteractionsSchema(BaseModel):
    """게시물 상호작용 스키마 (현재 사용자 기준)"""
    is_liked: bool = False
    is_bookmarked: bool = False


# ============================================
# 게시물 스키마
# ============================================

class PostSchema(BaseModel):
    """게시물 스키마 (피드용)"""
    id: Any
    author: Dict[str, Any]
    route_name: str = ""
    shape_id: Optional[str] = None
    shape_name: Optional[str] = None
    shape_icon: Optional[str] = None
    distance: float = 0
    duration: int = 0
    pace: Optional[str] = None
    calories: Optional[int] = None
    location: Optional[str] = None
    caption: Optional[str] = None
    like_count: int = 0
    comment_count: int = 0
    bookmark_count: int = 0
    is_liked: bool = False
    is_bookmarked: bool = False
    actual_path: Optional[Any] = None
    start_latitude: Optional[float] = None
    start_longitude: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class PostDetailSchema(PostSchema):
    """게시물 상세 스키마"""
    workout_id: Optional[str] = None
    updated_at: Optional[datetime] = None


# ============================================
# 댓글 스키마
# ============================================

class CommentUserSchema(BaseModel):
    """댓글 작성자 스키마"""
    id: str
    name: str
    avatar_url: Optional[str] = None


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
    is_author: bool = False
    
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


class PostCreateRequest(BaseModel):
    """게시물 작성 요청 스키마 (운동 공유)"""
    workout_id: Optional[str] = Field(None, description="공유할 운동 ID")
    route_name: str = Field(..., min_length=1, max_length=100, description="경로 이름")
    shape_id: Optional[str] = Field(None, description="도형 ID")
    shape_name: Optional[str] = Field(None, description="도형 이름")
    shape_icon: Optional[str] = Field(None, description="도형 아이콘")
    distance: float = Field(..., description="거리 (km)")
    duration: int = Field(..., description="시간 (초)")
    pace: Optional[str] = Field(None, description="평균 페이스")
    calories: Optional[int] = Field(None, description="칼로리")
    caption: Optional[str] = Field(None, max_length=500, description="캡션")
    visibility: str = Field("public", description="공개 범위 (public/private)")
    location: Optional[str] = Field(None, description="위치")


class PostUpdateRequest(BaseModel):
    """게시물 수정 요청 스키마"""
    caption: Optional[str] = Field(None, max_length=500, description="캡션")
    visibility: Optional[str] = Field(None, description="공개 범위 (public/private)")


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
    """피드 응답 스키마"""
    posts: List[PostSchema]
    pagination: Any  # PaginationInfo 또는 Dict


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


class PostCreateResponse(BaseModel):
    """게시물 작성 응답 스키마"""
    post_id: str
    created_at: datetime


class PostCreateResponseWrapper(BaseModel):
    """게시물 작성 응답 래퍼"""
    success: bool = True
    data: PostCreateResponse
    message: str = "게시물이 작성되었습니다"


class PostDeleteResponse(BaseModel):
    """게시물 삭제 응답 스키마"""
    success: bool = True
    message: str = "게시물이 삭제되었습니다"
