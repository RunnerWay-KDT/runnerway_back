# ============================================
# app/schemas/workout.py - 운동 관련 스키마
# ============================================
# workouts 테이블, workout_splits 테이블에 맞춘 요청/응답 스키마
# ============================================

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================
# 공통 스키마
# ============================================

class LocationDataSchema(BaseModel):
    """위치 데이터 스키마"""
    latitude: float
    longitude: float
    accuracy: Optional[float] = None


class SplitSchema(BaseModel):
    """
    구간 기록 스키마 (workout_splits 테이블과 1:1)
    - km: km 구간 (1, 2, 3...)
    - pace: 해당 구간 페이스 (예: "6'30\"")
    - duration: 해당 구간 소요 시간 (초)
    """
    km: int
    pace: str
    duration: int  # 초


# API 호환을 위한 alias
WorkoutSplitSchema = SplitSchema


class FinalMetricsSchema(BaseModel):
    """최종 운동 측정 데이터 스키마"""
    distance: float  # km → workouts.distance
    duration: int  # 초 → workouts.duration
    average_pace: str  # 예: "6'30\"" → workouts.avg_pace
    calories: int  # kcal → workouts.calories
    max_pace: Optional[str] = None  # → workouts.max_pace
    min_pace: Optional[str] = None  # → workouts.min_pace


class RouteDataSchema(BaseModel):
    """실제 이동 경로 데이터 스키마"""
    actual_path: List[Dict[str, Any]]  # [{lat, lng, timestamp}] → workouts.actual_path


# ============================================
# 요청 스키마
# ============================================

class WorkoutStartRequest(BaseModel):
    """
    운동 시작 요청 스키마
    → workouts 테이블에 INSERT
    
    필수: route_name, start_location, started_at
    선택: route_id, route_option_id, type, mode
    """
    route_id: Optional[str] = Field(None, description="경로 ID (routes.id)")
    route_option_id: Optional[str] = Field(None, description="경로 옵션 ID (route_options.id)")
    route_name: str = Field(..., description="경로 이름 (스냅샷)")
    type: Optional[str] = Field(None, description="preset / custom / null")
    mode: Optional[str] = Field(None, description="running / walking / null")
    start_location: LocationDataSchema = Field(..., description="시작 위치 → start_latitude, start_longitude")
    started_at: datetime = Field(..., description="시작 시간 → started_at")
    
    class Config:
        json_schema_extra = {
            "example": {
                "route_id": "route-uuid-123",
                "route_option_id": "option-uuid-456",
                "route_name": "하트 경로",
                "type": "preset",
                "mode": "running",
                "start_location": {
                    "latitude": 37.5665,
                    "longitude": 126.9780
                },
                "started_at": "2024-01-15T09:00:00Z"
            }
        }


class WorkoutCompleteRequest(BaseModel):
    """
    운동 완료 요청 스키마
    → workouts 테이블 UPDATE + workout_splits 테이블 INSERT
    """
    completed_at: datetime = Field(..., description="완료 시점 → workouts.completed_at")
    final_metrics: FinalMetricsSchema = Field(..., description="최종 측정 데이터")
    route: RouteDataSchema = Field(..., description="실제 이동 경로 → workouts.actual_path")
    splits: Optional[List[SplitSchema]] = Field(None, description="구간 기록 → workout_splits")
    end_location: Optional[LocationDataSchema] = Field(None, description="종료 위치 → end_latitude, end_longitude")
    elevation_gain: Optional[int] = Field(None, description="상승 고도 → workouts.elevation_gain")
    elevation_loss: Optional[int] = Field(None, description="하강 고도 → workouts.elevation_loss")
    route_completion: Optional[float] = Field(None, description="경로 완주율 (%) → workouts.route_completion")


# ============================================
# 응답 스키마
# ============================================

class WorkoutStartResponse(BaseModel):
    """운동 시작 응답 스키마"""
    workout_id: str  # workouts.id (UUID)
    status: str = "active"
    started_at: datetime


class WorkoutStartResponseWrapper(BaseModel):
    """운동 시작 응답 래퍼"""
    success: bool = True
    data: WorkoutStartResponse
    message: str = "운동이 시작되었습니다"


class WorkoutCompleteResponse(BaseModel):
    """운동 완료 응답 스키마"""
    workout_id: str
    completed_distance: float  # km
    completed_time: int  # 초
    average_pace: str
    calories: int
    route_completion: Optional[float] = None  # 0-100
    planned_path: Optional[List[Dict[str, Any]]] = None  # route_options.coordinates
    actual_path: Optional[List[Dict[str, Any]]] = None  # workouts.actual_path
    saved_at: datetime


class WorkoutCompleteResponseWrapper(BaseModel):
    """완료 응답 래퍼"""
    success: bool = True
    data: WorkoutCompleteResponse
    message: str = "운동이 완료되었습니다"


# ============================================
# 운동 기록 조회 스키마
# ============================================

class WorkoutSummarySchema(BaseModel):
    """운동 기록 요약 스키마 (목록 조회용)"""
    id: str
    route_id: Optional[str] = None
    route_option_id: Optional[str] = None
    route_name: str
    type: Optional[str] = None
    mode: Optional[str] = None
    distance: Optional[float] = None
    duration: Optional[int] = None
    avg_pace: Optional[str] = None
    calories: Optional[int] = None
    route_completion: Optional[float] = None
    is_bookmarked: bool = False
    svg_path: Optional[str] = None
    shape_id: Optional[str] = None      # 프리셋 도형 식별자 (예: 'heart', 'star')
    icon_name: Optional[str] = None      # 프리셋 도형 아이콘 이름
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class WorkoutDetailSchema(WorkoutSummarySchema):
    """운동 기록 상세 스키마"""
    planned_path: Optional[List[Dict[str, Any]]] = None  # route_options.coordinates
    actual_path: Optional[List[Dict[str, Any]]] = None
    splits: Optional[List[SplitSchema]] = None
    start_latitude: float
    start_longitude: float
    end_latitude: Optional[float] = None
    end_longitude: Optional[float] = None
    created_at: datetime


class WorkoutDetailResponseWrapper(BaseModel):
    """운동 상세 응답 래퍼"""
    success: bool = True
    data: WorkoutDetailSchema


class WorkoutListResponse(BaseModel):
    """운동 기록 목록 응답 스키마"""
    workouts: List[WorkoutSummarySchema]
    pagination: Dict[str, Any]


class WorkoutListResponseWrapper(BaseModel):
    """운동 기록 목록 응답 래퍼"""
    success: bool = True
    data: WorkoutListResponse
    message: str = "운동 기록 조회 성공"


class WorkoutDeleteResponse(BaseModel):
    """운동 삭제 응답 스키마"""
    success: bool = True
    message: str = "운동이 삭제되었습니다"
