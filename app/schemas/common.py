# ============================================
# app/schemas/common.py - 공통 스키마
# ============================================
# 여러 곳에서 공통으로 사용되는 스키마들을 정의합니다.
# ============================================

from typing import TypeVar, Generic, Optional, Any, List
from pydantic import BaseModel
from datetime import datetime


# 제네릭 타입 변수 (다양한 타입의 데이터를 담을 수 있음)
DataType = TypeVar("DataType")


class BaseResponse(BaseModel, Generic[DataType]):
    """
    API 응답 기본 형식
    
    모든 API 응답은 이 형식을 따릅니다.
    
    [응답 형식]
    {
        "success": true,
        "data": { ... },
        "message": "성공 메시지"
    }
    
    [신입 개발자를 위한 팁]
    - Generic[DataType]: 다양한 타입의 data를 담을 수 있음
    - Optional: None이 될 수 있음을 의미
    """
    success: bool = True
    data: Optional[DataType] = None
    message: Optional[str] = None
    
    class Config:
        # ORM 모델을 스키마로 변환할 때 사용
        from_attributes = True


class ErrorDetail(BaseModel):
    """에러 상세 정보"""
    field: Optional[str] = None   # 에러가 발생한 필드명
    reason: Optional[str] = None  # 에러 이유


class ErrorResponse(BaseModel):
    """
    에러 응답 형식
    
    [응답 형식]
    {
        "success": false,
        "error": {
            "code": "ERROR_CODE",
            "message": "에러 메시지",
            "details": { ... }
        },
        "timestamp": "2024-01-01T00:00:00Z"
    }
    """
    success: bool = False
    error: dict
    timestamp: datetime = None
    
    def __init__(self, **data):
        if 'timestamp' not in data or data['timestamp'] is None:
            data['timestamp'] = datetime.utcnow()
        super().__init__(**data)


class PaginationInfo(BaseModel):
    """페이지네이션 정보"""
    current_page: int              # 현재 페이지
    total_pages: int               # 전체 페이지 수
    total_count: int               # 전체 아이템 수
    has_next: bool                 # 다음 페이지 존재 여부
    has_prev: bool                 # 이전 페이지 존재 여부


class PaginatedResponse(BaseModel, Generic[DataType]):
    """
    페이지네이션이 포함된 응답 형식
    
    리스트 조회 API에서 사용합니다.
    """
    success: bool = True
    data: List[DataType] = []
    pagination: Optional[PaginationInfo] = None
    message: Optional[str] = None


# CommonResponse는 BaseResponse의 별칭 (호환성을 위해)
CommonResponse = BaseResponse
