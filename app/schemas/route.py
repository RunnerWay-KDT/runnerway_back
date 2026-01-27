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


class LocationSchema(BaseModel):
    """위치 정보 스키마"""
    latitude: float = Field(..., description="위도")
    longitude: float = Field(..., description="경도")
    address: Optional[str] = Field(None, description="주소")


class WaypointSchema(BaseModel):
    """경유지 스키마"""
    id: str
    name: str
    category: str  # cafe, convenience, park, photo
    location: CoordinateSchema


class ShapeInfoSchema(BaseModel):
    """도형 정보 스키마"""
    shape_id: str
    shape_name: str
    icon_name: str
    is_custom: bool = False


class CustomPathSchema(BaseModel):
    """커스텀 경로 스키마 (직접 그리기)"""
    svg_path: Optional[str] = Field(None, description="SVG Path 데이터")
    points: Optional[List[Dict[str, float]]] = Field(None, description="좌표 배열 [{x, y}]")
    estimated_distance: Optional[float] = Field(None, description="예상 거리 (km)")


class RoutePreferencesSchema(BaseModel):
    """경로 생성 선호도 스키마"""
    # 러닝 설정
    condition: Optional[str] = Field(None, description="컨디션 (recovery/fat-burn/challenge)")
    
    # 산책 설정
    intensity: Optional[str] = Field(None, description="강도 (light/moderate/brisk)")
    duration: Optional[int] = Field(None, description="목표 시간 (분)")
    
    # 공통 설정
    safety_mode: bool = Field(True, description="안전 우선 모드")
    avoid_hills: bool = Field(False, description="언덕 회피")
    waypoints: Optional[List[WaypointSchema]] = Field(None, description="경유지 목록")


# ============================================
# 요청 스키마
# ============================================

class RouteGenerateRequest(BaseModel):
    """
    경로 생성 요청 스키마
    
    [신입 개발자를 위한 팁]
    - type: 'preset' (프리셋 도형) 또는 'custom' (직접 그리기)
    - mode: 'running' (러닝) 또는 'walking' (산책)
    - preset인 경우 shape_id 필수
    - custom인 경우 custom_path 필수
    """
    type: str = Field(..., description="경로 타입 (preset/custom)")
    mode: str = Field(..., description="운동 모드 (running/walking)")
    
    # 프리셋 도형 정보
    shape_id: Optional[str] = Field(None, description="도형 ID (heart/star/coffee/smile/dog/cat)")
    shape_name: Optional[str] = Field(None, description="도형 이름")
    
    # 커스텀 경로 정보
    custom_path: Optional[CustomPathSchema] = Field(None, description="커스텀 경로 데이터")
    
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
    created_at: datetime


class RouteGenerateResponseWrapper(BaseModel):
    """경로 생성 응답 래퍼"""
    success: bool = True
    data: RouteGenerateTaskResponse
    message: str = "경로 생성을 시작했습니다"


class RouteTaskStatusResponse(BaseModel):
    """
    경로 생성 상태 조회 응답 스키마
    
    2초마다 폴링하여 생성 진행 상황을 확인합니다.
    """
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
    sidewalk: int = Field(0, description="인도 비율 (0-100)")
    convenience: int = Field(0, description="주변 편의시설 수")


class RouteFeatureSchema(BaseModel):
    """경로 특성 스키마"""
    type: str  # flat, uphill, lighting, sidewalk
    description: str


class RouteOptionSchema(BaseModel):
    """
    경로 옵션 스키마
    
    하나의 경로에 대해 3가지 옵션이 제공됩니다.
    """
    id: int = Field(..., description="옵션 번호 (1-3)")
    name: str = Field(..., description="옵션 이름")
    distance: float = Field(..., description="거리 (km)")
    estimated_time: int = Field(..., description="예상 시간 (분)")
    difficulty: str = Field(..., description="난이도 (쉬움/보통/도전)")
    tag: Optional[str] = Field(None, description="태그 (추천/BEST)")
    coordinates: List[CoordinateSchema] = Field(..., description="경로 좌표 배열")
    scores: RouteScoresSchema = Field(..., description="경로 점수")
    features: Optional[List[RouteFeatureSchema]] = Field(None, description="경로 특성")


class NearbyPlaceSchema(BaseModel):
    """주변 장소 스키마"""
    id: str
    name: str
    category: str  # 카페, 편의점, 공원, 화장실, 음수대
    distance: float  # meters
    rating: Optional[float] = None
    reviews: Optional[int] = None
    is_open: Optional[bool] = None
    location: CoordinateSchema


class RouteOptionsResponse(BaseModel):
    """
    경로 옵션 조회 응답 스키마
    
    GET /api/v1/routes/{routeId}/options 응답에 사용됩니다.
    """
    route_id: str
    shape_info: ShapeInfoSchema
    options: List[RouteOptionSchema]
    nearby_places: Optional[List[NearbyPlaceSchema]] = None


class RouteOptionsResponseWrapper(BaseModel):
    """경로 옵션 응답 래퍼"""
    success: bool = True
    data: RouteOptionsResponse
    message: str = "경로 옵션 조회 성공"


# ============================================
# 경유지 추천 스키마
# ============================================

class PlaceSchema(BaseModel):
    """장소 상세 스키마"""
    id: str
    name: str
    address: Optional[str] = None
    distance: str  # "0.3km"
    walking_time: Optional[int] = None  # minutes
    rating: Optional[float] = None
    reviews: Optional[int] = None
    estimated_time: Optional[str] = None  # "4분"
    is_open: Optional[bool] = None
    opening_hours: Optional[str] = None
    location: CoordinateSchema
    photos: Optional[List[str]] = None


class PlaceCategorySchema(BaseModel):
    """장소 카테고리 스키마"""
    id: str  # cafe, convenience, park, photo
    name: str  # 카페, 편의점, 공원, 포토존
    icon: str  # coffee, store, trees, camera
    color: str  # hex color
    places: List[PlaceSchema]


class WaypointRecommendResponse(BaseModel):
    """경유지 추천 응답 스키마"""
    location: LocationSchema
    categories: List[PlaceCategorySchema]


class WaypointRecommendResponseWrapper(BaseModel):
    """경유지 추천 응답 래퍼"""
    success: bool = True
    data: WaypointRecommendResponse
    message: str = "경유지 추천 성공"


# ============================================
# 저장된 경로 스키마
# ============================================

class SavedRouteSchema(BaseModel):
    """저장된 경로 스키마"""
    id: str
    route_id: str
    route_name: str
    distance: float  # km
    safety: int  # 0-100
    shape_id: Optional[str] = None
    shape_name: Optional[str] = None
    icon_name: Optional[str] = None
    is_custom: bool = False
    location: Optional[Dict[str, Any]] = None
    author: Optional[Dict[str, Any]] = None
    stats: Optional[Dict[str, Any]] = None
    preview: Optional[Dict[str, Any]] = None
    saved_at: datetime
    
    class Config:
        from_attributes = True


class SaveRouteRequest(BaseModel):
    """경로 저장 요청 스키마"""
    route_id: str = Field(..., description="저장할 경로 ID")
    custom_name: Optional[str] = Field(None, description="커스텀 이름")


class SaveRouteResponse(BaseModel):
    """경로 저장 응답 스키마"""
    saved_route_id: str
    route_id: str
    saved_at: datetime


class SaveRouteResponseWrapper(BaseModel):
    """경로 저장 응답 래퍼"""
    success: bool = True
    data: SaveRouteResponse
    message: str = "경로가 저장되었습니다"


# ============================================
# API에서 사용하는 추가 스키마
# ============================================

class RouteStartLocation(BaseModel):
    """시작 위치 스키마"""
    lat: float = Field(..., description="위도")
    lng: float = Field(..., description="경도")


class RouteWaypointsSchema(BaseModel):
    """경유지 스키마 (요청용)"""
    locations: List[RouteStartLocation] = []


class RouteGenerateRequest(BaseModel):
    """경로 생성 요청 스키마 (간소화 버전)"""
    start_location: RouteStartLocation = Field(..., description="시작 위치")
    distance: float = Field(..., ge=0.5, le=50, description="목표 거리 (km)")
    shape_id: int = Field(..., description="모양 템플릿 ID")
    waypoints: Optional[RouteWaypointsSchema] = Field(None, description="경유지")
    avoid_steep: bool = Field(False, description="급경사 회피")
    prefer_shaded: bool = Field(False, description="그늘길 선호")
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_location": {"lat": 37.5665, "lng": 126.9780},
                "distance": 5.0,
                "shape_id": 1,
                "avoid_steep": True,
                "prefer_shaded": False
            }
        }


class RouteGenerateResponse(BaseModel):
    """경로 생성 응답 스키마 (간소화 버전)"""
    task_id: str
    status: str
    estimated_time: int


class RouteGenerateResponseWrapper(BaseModel):
    """경로 생성 응답 래퍼"""
    success: bool = True
    data: RouteGenerateResponse
    message: str = "경로 생성이 요청되었습니다"


class RouteOptionSchema(BaseModel):
    """경로 옵션 스키마 (간소화 버전)"""
    id: int
    type: str  # balanced, safety, scenic
    distance: float
    estimated_time: int  # 분
    safety_score: int
    elevation_gain: int
    path_preview: List[Dict[str, Any]] = []


class RouteOptionsResponse(BaseModel):
    """경로 옵션 조회 응답 스키마 (간소화 버전)"""
    route_id: int
    shape: Dict[str, Any]
    options: List[RouteOptionSchema]


class RouteOptionsResponseWrapper(BaseModel):
    """경로 옵션 응답 래퍼"""
    success: bool = True
    data: RouteOptionsResponse


class RoutePointSchema(BaseModel):
    """경로 좌표 스키마"""
    lat: float
    lng: float
    elevation: Optional[float] = None


class RouteDetailResponse(BaseModel):
    """경로 상세 응답 스키마"""
    id: int
    route_id: int
    type: str
    name: str
    distance: float
    estimated_time: int
    safety_score: int
    elevation_gain: int
    path: List[RoutePointSchema] = []
    safety_features: Dict[str, Any] = {}
    amenities: Dict[str, Any] = {}


class RouteDetailResponseWrapper(BaseModel):
    """경로 상세 응답 래퍼"""
    success: bool = True
    data: RouteDetailResponse


class RouteSaveRequest(BaseModel):
    """경로 저장 요청 스키마"""
    custom_name: Optional[str] = Field(None, max_length=100, description="커스텀 이름")
    note: Optional[str] = Field(None, max_length=500, description="메모")


class RouteSaveResponse(BaseModel):
    """경로 저장 응답 스키마"""
    saved_route_id: int
    saved_at: datetime
