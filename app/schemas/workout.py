# ============================================
# app/schemas/workout.py - 운동 관련 스키마
# ============================================
# 운동 시작, 추적, 완료, 기록 관련 요청/응답 스키마를 정의합니다.
# ============================================

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.route import CoordinateSchema


# ============================================
# 공통 스키마
# ============================================

class LocationDataSchema(BaseModel):
    """위치 데이터 스키마"""
    latitude: float
    longitude: float
    accuracy: Optional[float] = None


class MetricsSchema(BaseModel):
    """운동 측정 데이터 스키마"""
    distance: float  # km
    duration: int  # 초
    current_pace: Optional[str] = None


class SplitSchema(BaseModel):
    """구간 기록 스키마"""
    km: int
    pace: str
    duration: int  # 초


# API 호환을 위한 alias
WorkoutSplitSchema = SplitSchema


class WeatherSchema(BaseModel):
    """날씨 정보 스키마"""
    temperature: Optional[float] = None
    condition: Optional[str] = None
    humidity: Optional[float] = None


# ============================================
# 요청 스키마
# ============================================

class WorkoutStartRequest(BaseModel):
    """
    운동 시작 요청 스키마
    
    [신입 개발자를 위한 팁]
    - route_id: 선택한 경로 ID
    - route_option_id: 선택한 옵션 ID
    - type: preset / custom / null (도형 그리기 아님)
    - mode: running / walking / null (도형 그리기)
    """
    route_id: Optional[str] = Field(None, description="경로 ID")
    route_option_id: Optional[str] = Field(None, description="경로 옵션 ID")
    route_name: str = Field(..., description="경로 이름")
    type: Optional[str] = Field(None, description="운동 타입 (preset/custom/null)")
    mode: Optional[str] = Field(None, description="운동 모드 (running/walking/null)")
    start_location: LocationDataSchema = Field(..., description="시작 위치")
    started_at: datetime = Field(..., description="시작 시간")
    
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


class WorkoutTrackRequest(BaseModel):
    """운동 추적 데이터 전송 요청 스키마"""
    timestamp: datetime = Field(..., description="기록 시점")
    location: LocationDataSchema = Field(..., description="현재 위치")
    metrics: MetricsSchema = Field(..., description="측정 데이터")


class WorkoutPauseRequest(BaseModel):
    """운동 일시정지 요청 스키마"""
    timestamp: datetime = Field(..., description="일시정지 시점")
    location: Optional[LocationDataSchema] = None


class WorkoutResumeRequest(BaseModel):
    """운동 재개 요청 스키마"""
    timestamp: datetime = Field(..., description="재개 시점")
    location: Optional[LocationDataSchema] = None


class FinalMetricsSchema(BaseModel):
    """최종 운동 측정 데이터 스키마"""
    distance: float  # km
    duration: int  # 초
    average_pace: str
    calories: int
    max_pace: Optional[str] = None
    min_pace: Optional[str] = None


class RouteDataSchema(BaseModel):
    """실제 이동 경로 데이터 스키마"""
    actual_path: List[Dict[str, Any]]  # [{lat, lng, timestamp}]
    total_pauses: int = 0
    pause_duration: int = 0  # 초


class WorkoutCompleteRequest(BaseModel):
    """운동 완료 요청 스키마"""
    completed_at: datetime = Field(..., description="완료 시점")
    final_metrics: FinalMetricsSchema = Field(..., description="최종 측정 데이터")
    route: RouteDataSchema = Field(..., description="실제 이동 경로")
    splits: Optional[List[SplitSchema]] = Field(None, description="구간 기록")
    end_location: Optional[LocationDataSchema] = Field(None, description="종료 위치")
    elevation_gain: Optional[int] = Field(None, description="상승 고도")
    elevation_loss: Optional[int] = Field(None, description="하강 고도")
    route_completion: Optional[float] = Field(None, description="경로 완주율 (%)")


class WorkoutShareRequest(BaseModel):
    """운동 결과 공유 요청 스키마"""
    visibility: str = Field("public", description="공개 범위 (public/private)")
    caption: Optional[str] = Field(None, max_length=500, description="캡션")
    location: Optional[str] = Field(None, description="위치 (여의도 한강공원)")


# ============================================
# 응답 스키마
# ============================================

class RouteInfoSchema(BaseModel):
    """경로 정보 스키마 (운동 시작 응답용)"""
    route_id: Optional[str] = None
    route_name: str
    target_distance: Optional[float] = None  # km
    estimated_time: Optional[int] = None  # 분
    coordinates: Optional[List[CoordinateSchema]] = None


class SessionInfoSchema(BaseModel):
    """세션 정보 스키마"""
    status: str  # active, paused, completed
    started_at: datetime


class WorkoutStartResponse(BaseModel):
    """운동 시작 응답 스키마"""
    workout_id: str
    route_info: RouteInfoSchema
    session: SessionInfoSchema


class WorkoutStartResponseWrapper(BaseModel):
    """운동 시작 응답 래퍼"""
    success: bool = True
    data: WorkoutStartResponse
    message: str = "운동이 시작되었습니다"


class TrackResponseData(BaseModel):
    """추적 응답 데이터 스키마"""
    progress: float  # 0-100
    remaining_distance: float  # km
    is_off_route: bool


class WorkoutTrackResponse(BaseModel):
    """운동 트래킹 응답 스키마"""
    workout_id: int
    distance: float
    duration: int
    avg_pace: Optional[float] = None
    calories: int
    is_off_route: bool = False


class WorkoutTrackResponseWrapper(BaseModel):
    """추적 응답 래퍼"""
    success: bool = True
    data: WorkoutTrackResponse


class WorkoutPauseResponse(BaseModel):
    """운동 일시정지 응답 스키마"""
    status: str = "paused"
    paused_at: datetime


class WorkoutPauseResponseWrapper(BaseModel):
    """일시정지 응답 래퍼"""
    success: bool = True
    data: WorkoutPauseResponse
    message: str = "운동이 일시정지되었습니다"


class WorkoutResumeResponse(BaseModel):
    """운동 재개 응답 스키마"""
    status: str = "active"
    resumed_at: datetime
    pause_duration: int  # 초


class WorkoutResumeResponseWrapper(BaseModel):
    """재개 응답 래퍼"""
    success: bool = True
    data: WorkoutResumeResponse
    message: str = "운동이 재개되었습니다"


class WorkoutCompleteResponse(BaseModel):
    """운동 완료 응답 스키마"""
    workout_id: str
    completed_distance: float  # km
    completed_time: int  # 초
    average_pace: str
    calories: int
    route_completion: Optional[float] = None  # 0-100
    saved_at: datetime


class WorkoutCompleteResponseWrapper(BaseModel):
    """완료 응답 래퍼"""
    success: bool = True
    data: WorkoutCompleteResponse
    message: str = "운동이 완료되었습니다"


class WorkoutShareResponse(BaseModel):
    """운동 공유 응답 스키마"""
    post_id: str
    shared_at: datetime


class WorkoutShareResponseWrapper(BaseModel):
    """공유 응답 래퍼"""
    success: bool = True
    data: WorkoutShareResponse
    message: str = "운동 결과가 공유되었습니다"


# ============================================
# 운동 기록 조회 스키마
# ============================================

class WorkoutRouteDataSchema(BaseModel):
    """운동 기록의 경로 데이터 스키마"""
    shape_id: Optional[str] = None
    shape_name: Optional[str] = None
    icon_name: Optional[str] = None
    is_custom: bool = False


class WorkoutStatsSchema(BaseModel):
    """운동 기록의 통계 스키마"""
    avg_pace: Optional[str] = None
    max_pace: Optional[str] = None
    min_pace: Optional[str] = None
    elevation_gain: Optional[int] = None
    elevation_loss: Optional[int] = None


class WorkoutSummarySchema(BaseModel):
    """운동 기록 요약 스키마 (목록 조회용)"""
    id: str
    route_name: str
    type: Optional[str] = None  # preset/custom/null
    mode: Optional[str] = None  # running/walking/null
    distance: Optional[float] = None  # km
    duration: Optional[int] = None  # 초
    avg_pace: Optional[str] = None
    calories: Optional[int] = None
    route_data: Optional[WorkoutRouteDataSchema] = None
    stats: Optional[WorkoutStatsSchema] = None
    route_completion: Optional[float] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class WorkoutDetailSchema(WorkoutSummarySchema):
    """운동 기록 상세 스키마"""
    actual_path: Optional[List[Dict[str, Any]]] = None
    splits: Optional[List[SplitSchema]] = None
    start_latitude: float
    start_longitude: float
    end_latitude: Optional[float] = None
    end_longitude: Optional[float] = None
    created_at: datetime


class WorkoutDetailResponse(BaseModel):
    """운동 상세 응답 스키마 (API 응답용)"""
    id: int
    type: Optional[str] = None
    status: str
    distance: float
    duration: int
    avg_pace: Optional[float] = None
    calories: int
    route_info: Optional[Dict[str, Any]] = None
    path: Optional[List[Dict[str, Any]]] = None
    splits: Optional[List[Any]] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class WorkoutListResponse(BaseModel):
    """운동 기록 목록 응답 스키마"""
    workouts: List[WorkoutSummarySchema]
    pagination: Dict[str, Any]


class WorkoutListResponseWrapper(BaseModel):
    """운동 기록 목록 응답 래퍼"""
    success: bool = True
    data: WorkoutListResponse
    message: str = "운동 기록 조회 성공"


class WorkoutDetailResponseWrapper(BaseModel):
    """운동 상세 응답 래퍼"""
    success: bool = True
    data: WorkoutDetailSchema


class WorkoutDeleteResponse(BaseModel):
    """운동 삭제 응답 스키마"""
    success: bool = True
    message: str = "운동이 삭제되었습니다"
