# ============================================
# app/schemas/workout.py - 운동 관련 스키마
# ============================================
# 운동 시작, 추적, 완료, 기록 관련 요청/응답 스키마를 정의합니다.
# ============================================

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.route import CoordinateSchema, ShapeInfoSchema


# ============================================
# 공통 스키마
# ============================================

class LocationDataSchema(BaseModel):
    """위치 데이터 스키마"""
    latitude: float
    longitude: float
    accuracy: Optional[float] = None  # GPS 정확도 (m)
    altitude: Optional[float] = None
    speed: Optional[float] = None  # m/s


class MetricsSchema(BaseModel):
    """운동 측정 데이터 스키마"""
    distance: float  # km
    duration: int  # 초
    current_pace: Optional[str] = None
    heart_rate: Optional[int] = None  # bpm


class SplitSchema(BaseModel):
    """구간 기록 스키마"""
    km: int
    time: str
    pace: str


class AchievementSchema(BaseModel):
    """성취 스키마"""
    id: str
    type: str  # personal_best, streak, milestone, first_completion
    title: str
    description: Optional[str] = None
    icon: Optional[str] = None
    points: Optional[int] = None


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
    - route_option_id: 선택한 옵션 번호 (1, 2, 3)
    - mode: 운동 모드 (running/walking)
    - started_at: 시작 시간 (클라이언트 기준)
    """
    route_id: str = Field(..., description="경로 ID")
    route_option_id: int = Field(..., ge=1, le=3, description="경로 옵션 번호 (1-3)")
    mode: str = Field(..., description="운동 모드 (running/walking)")
    start_location: LocationDataSchema = Field(..., description="시작 위치")
    preferences: Optional[Dict[str, Any]] = Field(None, description="운동 설정")
    started_at: datetime = Field(..., description="시작 시간")
    
    class Config:
        json_schema_extra = {
            "example": {
                "route_id": "route-uuid-123",
                "route_option_id": 2,
                "mode": "running",
                "start_location": {
                    "latitude": 37.5665,
                    "longitude": 126.9780,
                    "accuracy": 10.5
                },
                "preferences": {
                    "voice_guide": True,
                    "auto_lap": True
                },
                "started_at": "2024-01-15T09:00:00Z"
            }
        }


class WorkoutTrackRequest(BaseModel):
    """
    운동 추적 데이터 전송 요청 스키마
    
    10초마다 현재 위치와 측정 데이터를 전송합니다.
    """
    timestamp: datetime = Field(..., description="기록 시점")
    location: LocationDataSchema = Field(..., description="현재 위치")
    metrics: MetricsSchema = Field(..., description="측정 데이터")


class WorkoutPauseRequest(BaseModel):
    """운동 일시정지 요청 스키마"""
    timestamp: datetime = Field(..., description="일시정지 시점")
    location: Optional[LocationDataSchema] = None
    current_metrics: Optional[MetricsSchema] = None


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
    heart_rate_avg: Optional[int] = None
    heart_rate_max: Optional[int] = None


class RouteDataSchema(BaseModel):
    """실제 이동 경로 데이터 스키마"""
    actual_path: List[Dict[str, Any]]  # [{lat, lng, timestamp, elevation}]
    total_pauses: int = 0
    pause_duration: int = 0  # 초


class WorkoutCompleteRequest(BaseModel):
    """
    운동 완료 요청 스키마
    
    운동 종료 시 최종 데이터를 전송합니다.
    """
    completed_at: datetime = Field(..., description="완료 시점")
    final_metrics: FinalMetricsSchema = Field(..., description="최종 측정 데이터")
    route: RouteDataSchema = Field(..., description="실제 이동 경로")
    splits: Optional[List[SplitSchema]] = Field(None, description="구간 기록")
    
    class Config:
        json_schema_extra = {
            "example": {
                "completed_at": "2024-01-15T09:30:00Z",
                "final_metrics": {
                    "distance": 5.2,
                    "duration": 1800,
                    "average_pace": "5'46\"",
                    "calories": 350,
                    "max_pace": "5'20\"",
                    "min_pace": "6'10\""
                },
                "route": {
                    "actual_path": [
                        {"lat": 37.5665, "lng": 126.9780, "timestamp": "2024-01-15T09:00:00Z"}
                    ],
                    "total_pauses": 1,
                    "pause_duration": 120
                },
                "splits": [
                    {"km": 1, "time": "5:46", "pace": "5'46\""},
                    {"km": 2, "time": "11:30", "pace": "5'44\""}
                ]
            }
        }


class WorkoutShareRequest(BaseModel):
    """운동 결과 공유 요청 스키마"""
    platform: str = Field(..., description="공유 플랫폼 (community/external)")
    visibility: str = Field("public", description="공개 범위 (public/private)")
    caption: Optional[str] = Field(None, max_length=500, description="캡션")
    tags: Optional[List[str]] = Field(None, description="태그")


# ============================================
# 응답 스키마
# ============================================

class RouteInfoSchema(BaseModel):
    """경로 정보 스키마 (운동 시작 응답용)"""
    route_id: str
    route_name: str
    target_distance: float  # km
    estimated_time: int  # 분
    shape_info: Optional[ShapeInfoSchema] = None
    coordinates: List[CoordinateSchema]


class SessionInfoSchema(BaseModel):
    """세션 정보 스키마"""
    status: str  # active, paused, completed
    started_at: datetime
    tracking_interval: int = 10  # 초


class WorkoutStartResponse(BaseModel):
    """운동 시작 응답 스키마"""
    workout_id: str
    route_info: RouteInfoSchema
    session: SessionInfoSchema
    weather: Optional[WeatherSchema] = None


class WorkoutStartResponseWrapper(BaseModel):
    """운동 시작 응답 래퍼"""
    success: bool = True
    data: WorkoutStartResponse
    message: str = "운동이 시작되었습니다"


class TrackResponseData(BaseModel):
    """추적 응답 데이터 스키마"""
    progress: float  # 0-100
    remaining_distance: float  # km
    deviation_from_route: float  # meters
    is_off_route: bool
    next_checkpoint: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
    stats: Optional[Dict[str, Any]] = None
    alerts: Optional[List[Dict[str, str]]] = None


class WorkoutTrackResponseWrapper(BaseModel):
    """추적 응답 래퍼"""
    success: bool = True
    data: TrackResponseData


class WorkoutPauseResponse(BaseModel):
    """운동 일시정지 응답 스키마"""
    status: str = "paused"
    paused_at: datetime
    session_summary: Optional[Dict[str, Any]] = None


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


class PersonalBestSchema(BaseModel):
    """개인 최고 기록 스키마"""
    category: str  # fastest_pace, longest_distance, most_calories
    value: str


class WorkoutCompleteResponse(BaseModel):
    """운동 완료 응답 스키마"""
    workout_id: str
    completed_distance: float  # km
    completed_time: int  # 초
    average_pace: str
    calories: int
    achievements: List[AchievementSchema] = []
    route_completion: float  # 0-100
    shape_accuracy: float  # 0-100
    personal_bests: List[PersonalBestSchema] = []
    saved_at: datetime
    share_url: Optional[str] = None


class WorkoutCompleteResponseWrapper(BaseModel):
    """완료 응답 래퍼"""
    success: bool = True
    data: WorkoutCompleteResponse
    message: str = "운동이 완료되었습니다"


class WorkoutShareResponse(BaseModel):
    """운동 공유 응답 스키마"""
    post_id: Optional[str] = None
    share_url: str
    shared_at: datetime
    preview: Optional[Dict[str, str]] = None


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


class WorkoutLocationSchema(BaseModel):
    """운동 기록의 위치 스키마"""
    start_address: Optional[str] = None
    end_address: Optional[str] = None
    district: Optional[str] = None


class WorkoutStatsSchema(BaseModel):
    """운동 기록의 통계 스키마"""
    average_pace: Optional[str] = None
    max_pace: Optional[str] = None
    min_pace: Optional[str] = None
    elevation: Optional[int] = None
    heart_rate_avg: Optional[int] = None
    heart_rate_max: Optional[int] = None


class WorkoutSummarySchema(BaseModel):
    """운동 기록 요약 스키마 (목록 조회용)"""
    id: str
    route_name: str
    type: str  # running/walking
    distance: float  # km
    duration: int  # 초
    pace: Optional[str] = None
    calories: Optional[int] = None
    route_data: Optional[WorkoutRouteDataSchema] = None
    stats: Optional[WorkoutStatsSchema] = None
    location: Optional[WorkoutLocationSchema] = None
    completed_at: datetime
    
    class Config:
        from_attributes = True


class WorkoutDetailSchema(WorkoutSummarySchema):
    """운동 기록 상세 스키마"""
    coordinates: Optional[List[Dict[str, Any]]] = None
    splits: Optional[List[SplitSchema]] = None
    achievements: Optional[List[AchievementSchema]] = None
    weather: Optional[WeatherSchema] = None
    created_at: datetime


class WorkoutListResponse(BaseModel):
    """운동 기록 목록 응답 스키마"""
    workouts: List[WorkoutSummarySchema]
    pagination: Dict[str, Any]


class WorkoutListResponseWrapper(BaseModel):
    """운동 기록 목록 응답 래퍼"""
    success: bool = True
    data: WorkoutListResponse
    message: str = "운동 기록 조회 성공"


# ============================================
# API에서 사용하는 추가 스키마
# ============================================

class WorkoutCoordinateSchema(BaseModel):
    """운동 트래킹 좌표 스키마"""
    lat: float
    lng: float
    altitude: Optional[float] = None
    speed: Optional[float] = None
    timestamp: Optional[datetime] = None


class WorkoutStartRequest(BaseModel):
    """운동 시작 요청 스키마 (간소화 버전)"""
    type: str = Field(..., description="운동 타입 (running/walking)")
    route_id: Optional[int] = Field(None, description="선택한 경로 ID")
    option_id: Optional[int] = Field(None, description="선택한 경로 옵션 ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "running",
                "route_id": 1,
                "option_id": 1
            }
        }


class WorkoutStartResponse(BaseModel):
    """운동 시작 응답 스키마 (간소화 버전)"""
    workout_id: int
    status: str
    started_at: datetime
    route_info: Optional[Dict[str, Any]] = None


class WorkoutStartResponseWrapper(BaseModel):
    """운동 시작 응답 래퍼"""
    success: bool = True
    data: WorkoutStartResponse
    message: str = "운동이 시작되었습니다"


class WorkoutTrackRequest(BaseModel):
    """운동 트래킹 요청 스키마 (간소화 버전)"""
    coordinates: Optional[List[WorkoutCoordinateSchema]] = None
    current_distance: Optional[float] = None  # km
    current_duration: Optional[int] = None  # 초


class WorkoutTrackResponse(BaseModel):
    """운동 트래킹 응답 스키마"""
    workout_id: int
    distance: float
    duration: int
    avg_pace: Optional[float] = None
    calories: int
    is_off_route: bool = False


class WorkoutTrackResponseWrapper(BaseModel):
    """트래킹 응답 래퍼"""
    success: bool = True
    data: WorkoutTrackResponse


class WorkoutPathPointSchema(BaseModel):
    """운동 경로 좌표 스키마"""
    lat: float
    lng: float


class WorkoutCompleteRequest(BaseModel):
    """운동 완료 요청 스키마 (간소화 버전)"""
    final_distance: Optional[float] = None
    final_duration: Optional[int] = None
    final_path: Optional[List[WorkoutPathPointSchema]] = None


class WorkoutSplitSchema(BaseModel):
    """구간 기록 스키마"""
    km: int
    time: int  # 초
    pace: Optional[float] = None


class WorkoutCompleteResponse(BaseModel):
    """운동 완료 응답 스키마 (간소화 버전)"""
    workout_id: int
    summary: Dict[str, Any]
    splits: List[WorkoutSplitSchema] = []
    achievements: List["AchievementSchema"] = []
    completed_at: datetime


class WorkoutCompleteResponseWrapper(BaseModel):
    """완료 응답 래퍼"""
    success: bool = True
    data: WorkoutCompleteResponse
    message: str = "운동이 완료되었습니다"


class WorkoutDetailResponse(BaseModel):
    """운동 상세 응답 스키마"""
    id: int
    type: str
    status: str
    distance: float
    duration: int
    avg_pace: Optional[float] = None
    calories: int
    route_info: Optional[Dict[str, Any]] = None
    path: List[Dict[str, Any]] = []
    splits: List[WorkoutSplitSchema] = []
    started_at: datetime
    completed_at: Optional[datetime] = None


class WorkoutDetailResponseWrapper(BaseModel):
    """운동 상세 응답 래퍼"""
    success: bool = True
    data: WorkoutDetailResponse


class WorkoutDeleteResponse(BaseModel):
    """운동 삭제 응답 스키마"""
    success: bool = True
    message: str = "운동이 삭제되었습니다"
