# ============================================
# app/schemas/route.py - 경로 관련 스키마
# ============================================
# 경로 생성, 옵션, 저장 관련 요청/응답 스키마를 정의합니다.
# ============================================

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================
# 공통 스키마
# ============================================

class CoordinateSchema(BaseModel):
    """좌표 스키마"""
    lat: float = Field(..., description="위도")
    lng: float = Field(..., description="경도")


# API 호환을 위한 alias
RoutePointSchema = CoordinateSchema


class LocationSchema(BaseModel):
    """위치 정보 스키마"""
    latitude: float = Field(..., description="위도")
    longitude: float = Field(..., description="경도")
    address: Optional[str] = Field(None, description="주소")


class ShapeInfoSchema(BaseModel):
    """도형 정보 스키마"""
    id: str
    name: str
    icon_name: str
    category: str
    is_custom: bool = False


class CustomPathSchema(BaseModel):
    """커스텀 경로 스키마 (직접 그리기)"""
    svg_path: Optional[str] = Field(None, description="SVG URL 데이터")
    estimated_distance: Optional[float] = Field(None, description="예상 거리 (km)")


class RoutePreferencesSchema(BaseModel):
    """경로 생성 선호도 스키마"""
    # 러닝 설정
    condition: Optional[str] = Field(None, description="컨디션 (recovery/fat-burn/challenge)")
    
    # 산책 설정
    intensity: Optional[str] = Field(None, description="강도 (light/moderate/brisk)")
    duration: Optional[int] = Field(None, description="목표 시간 (분)")
    
    # 공통 설정
    safety_mode: bool = Field(False, description="안전 우선 모드")


# ============================================
# 요청 스키마
# ============================================

class SaveCustomDrawingRequest(BaseModel):
    """
    커스텀 그림 저장 요청 스키마 (직접 그리기)
    """
    name: str = Field(..., description="경로 이름")
    svg_path: str = Field(..., description="SVG Path 데이터")
    location: LocationSchema = Field(..., description="시작 위치")
    estimated_distance: Optional[float] = Field(None, description="예상 거리 (km)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "내가 그린 하트",
                "svg_path": "M 100 100 L 150 150 L 200 100",
                "location": {
                    "latitude": 37.5665,
                    "longitude": 126.9780,
                    "address": "서울특별시 중구"
                },
                "estimated_distance": 3.5
            }
        }


class SaveCustomDrawingResponse(BaseModel):
    """커스텀 그림 저장 응답 스키마"""
    route_id: str = Field(..., description="생성된 경로 ID")
    name: str = Field(..., description="경로 이름")
    svg_path: str = Field(..., description="저장된 SVG Path")
    estimated_distance: Optional[float] = None
    created_at: datetime


class SaveCustomDrawingResponseWrapper(BaseModel):
    """커스텀 그림 저장 응답 래퍼"""
    success: bool = True
    data: SaveCustomDrawingResponse
    message: str = "커스텀 경로가 저장되었습니다"


class RouteGenerateRequest(BaseModel):
    """
    경로 생성 요청 스키마
    
    [신입 개발자를 위한 팁]
    - type: 'preset' (프리셋 도형), 'custom' (직접 그리기), 'none' (도형 그리기 아님)
    - mode: 'running' (러닝), 'walking' (산책), 'none' (도형 그리기)
    """
    type: Optional[str] = Field(None, description="경로 타입 (preset/custom/none)")
    mode: Optional[str] = Field(None, description="운동 모드 (running/walking/none)")
    
    # 프리셋 도형 정보
    shape_id: Optional[str] = Field(None, description="도형 ID")
    shape_name: Optional[str] = Field(None, description="도형 이름")
    
    # 커스텀 경로 정보
    svg_path: Optional[CustomPathSchema] = Field(None, description="커스텀 경로 데이터")
    
    # 위치 정보
    location: LocationSchema = Field(..., description="시작 위치")
    
    # 선호도 설정
    preferences: Optional[RoutePreferencesSchema] = Field(None, description="경로 선호도")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "preset",
                "mode": "running",
                "shape_id": "heart",
                "shape_name": "하트",
                "location": {
                    "latitude": 37.5665,
                    "longitude": 126.9780,
                    "address": "서울특별시 중구 세종대로"
                },
                "preferences": {
                    "condition": "fat-burn",
                    "safety_mode": True
                }
            }
        }


# ============================================
# 응답 스키마
# ============================================

class RouteGenerateTaskResponse(BaseModel):
    """경로 생성 작업 응답 스키마"""
    task_id: str = Field(..., description="작업 ID (UUID)")
    estimated_time: int = Field(..., description="예상 생성 시간 (초)")
    status: str = Field("processing", description="상태")
    created_at: Optional[datetime] = None


# API 호환을 위한 alias
class RouteGenerateResponse(BaseModel):
    """경로 생성 응답 스키마 (API 호환용)"""
    task_id: str = Field(..., description="작업 ID")
    status: str = Field("pending", description="상태")
    estimated_time: int = Field(5, description="예상 생성 시간 (초)")


class RouteGenerateResponseWrapper(BaseModel):
    """경로 생성 응답 래퍼"""
    success: bool = True
    data: RouteGenerateResponse
    message: str = "경로 생성을 시작했습니다"


class RouteTaskStatusResponse(BaseModel):
    """경로 생성 상태 조회 응답 스키마"""
    task_id: str
    status: str = Field(..., description="상태 (processing/completed/failed)")
    progress: int = Field(0, description="진행률 (0-100)")
    current_step: Optional[str] = Field(None, description="현재 단계")
    estimated_remaining: Optional[int] = Field(None, description="예상 남은 시간 (초)")
    route_id: Optional[str] = Field(None, description="생성된 경로 ID (완료 시)")
    error: Optional[Dict[str, str]] = Field(None, description="에러 정보 (실패 시)")


class RouteTaskStatusResponseWrapper(BaseModel):
    """경로 생성 상태 응답 래퍼"""
    success: bool = True
    data: RouteTaskStatusResponse


class RouteScoresSchema(BaseModel):
    """경로 옵션 점수 스키마"""
    safety: int = Field(0, description="안전도 (0-100)")
    elevation: int = Field(0, description="고도차 (m)")
    lighting: int = Field(0, description="조명 점수 (0-100)")


class RouteOptionSchema(BaseModel):
    """경로 옵션 스키마"""
    id: str = Field(..., description="옵션 ID")
    option_number: int = Field(..., description="옵션 번호 (1-3)")
    name: str = Field(..., description="옵션 이름")
    distance: float = Field(..., description="거리 (km)")
    estimated_time: int = Field(..., description="예상 시간 (분)")
    difficulty: str = Field(..., description="난이도 (쉬움/보통/도전)")
    tag: Optional[str] = Field(None, description="태그 (추천/BEST)")
    coordinates: List[CoordinateSchema] = Field(..., description="경로 좌표 배열")
    scores: RouteScoresSchema = Field(..., description="경로 점수")


class RouteOptionsResponse(BaseModel):
    """경로 옵션 조회 응답 스키마"""
    route_id: str
    shape_info: Optional[ShapeInfoSchema] = None
    options: List[RouteOptionSchema]


class RouteOptionsResponseWrapper(BaseModel):
    """경로 옵션 응답 래퍼"""
    success: bool = True
    data: RouteOptionsResponse
    message: str = "경로 옵션 조회 성공"


# ============================================
# 장소 스키마
# ============================================

class PlaceSchema(BaseModel):
    """장소 스키마"""
    id: str
    name: str
    category: str
    address: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    location: CoordinateSchema


class PlaceCategorySchema(BaseModel):
    """장소 카테고리 스키마"""
    id: str  # cafe, convenience, park, photo
    name: str  # 카페, 편의점, 공원, 포토존
    icon: str
    color: str
    places: List[PlaceSchema]


# ============================================
# 저장된 경로 스키마
# ============================================

class SavedRouteSchema(BaseModel):
    """저장된 경로 스키마"""
    id: str
    route_id: str
    route_name: str
    distance: float
    safety_score: int
    shape_id: Optional[str] = None
    shape_name: Optional[str] = None
    icon_name: Optional[str] = None
    is_custom: bool = False
    saved_at: datetime
    
    class Config:
        from_attributes = True


class SaveRouteRequest(BaseModel):
    """경로 저장 요청 스키마"""
    route_id: str = Field(..., description="저장할 경로 ID")


# API 호환을 위한 alias
RouteSaveRequest = SaveRouteRequest


class SaveRouteResponse(BaseModel):
    """경로 저장 응답 스키마"""
    saved_route_id: str
    route_id: str
    saved_at: datetime


# API 호환을 위한 alias
RouteSaveResponse = SaveRouteResponse


class SaveRouteResponseWrapper(BaseModel):
    """경로 저장 응답 래퍼"""
    success: bool = True
    data: SaveRouteResponse
    message: str = "경로가 저장되었습니다"


# ============================================
# 경로 상세 스키마
# ============================================

class RouteDetailResponse(BaseModel):
    """경로 상세 응답 스키마"""
    id: str
    name: str
    type: Optional[str] = None
    mode: Optional[str] = None
    start_latitude: float
    start_longitude: float
    svg_path: Optional[str] = None
    condition: Optional[str] = None
    intensity: Optional[str] = None
    target_duration: Optional[int] = None
    safety_mode: bool = False
    status: str
    shape_info: Optional[ShapeInfoSchema] = None
    options: List[RouteOptionSchema] = []
    created_at: datetime
    updated_at: datetime


class RouteDetailResponseWrapper(BaseModel):
    """경로 상세 응답 래퍼"""
    success: bool = True
    data: RouteDetailResponse
