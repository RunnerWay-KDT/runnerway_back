# ============================================
# app/api/v1/workouts.py - 운동 API 라우터
# ============================================
# 운동 세션 시작, 실시간 트래킹, 완료, 기록 조회 등
# 운동 관련 API를 제공합니다.
# ============================================

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models.user import User, UserStats
from app.models.workout import Workout, WorkoutTrack, WorkoutSplit, WorkoutAchievement
from app.models.route import RouteOption
from app.schemas.workout import (
    WorkoutStartRequest, WorkoutStartResponse, WorkoutStartResponseWrapper,
    WorkoutTrackRequest, WorkoutTrackResponse, WorkoutTrackResponseWrapper,
    WorkoutCompleteRequest, WorkoutCompleteResponse, WorkoutCompleteResponseWrapper,
    WorkoutDetailResponse, WorkoutDetailResponseWrapper,
    WorkoutDeleteResponse,
    WorkoutSummarySchema, WorkoutSplitSchema, AchievementSchema
)
from app.schemas.common import CommonResponse
from app.core.exceptions import NotFoundException, ValidationException


router = APIRouter(prefix="/workouts", tags=["Workouts"])


# ============================================
# 운동 시작
# ============================================
@router.post(
    "/start",
    response_model=WorkoutStartResponseWrapper,
    status_code=status.HTTP_201_CREATED,
    summary="운동 시작",
    description="""
    새로운 운동 세션을 시작합니다.
    
    **필수 파라미터:**
    - type: running (달리기) 또는 walking (걷기)
    
    **선택 파라미터:**
    - route_id: 선택한 경로 ID
    - option_id: 선택한 경로 옵션 ID
    
    **응답:**
    - workout_id: 생성된 운동 세션 ID
    - 클라이언트는 이 ID로 트래킹 데이터 전송
    """
)
def start_workout(
    request: WorkoutStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """운동 시작 엔드포인트"""
    
    # 이미 진행 중인 운동이 있는지 확인
    active_workout = db.query(Workout).filter(
        Workout.user_id == current_user.id,
        Workout.status == "active"
    ).first()
    
    if active_workout:
        raise ValidationException(
            message="이미 진행 중인 운동이 있습니다",
            field="workout"
        )
    
    # 경로 옵션 정보 조회 (선택된 경우)
    route_option = None
    route_name = None
    shape_id = None
    shape_name = None
    shape_icon = None
    
    if request.option_id:
        route_option = db.query(RouteOption).filter(
            RouteOption.id == request.option_id
        ).first()
        
        if route_option and route_option.route:
            route_name = route_option.route.name
            if route_option.route.shape:
                shape_id = route_option.route.shape.id
                shape_name = route_option.route.shape.name
                shape_icon = route_option.route.shape.icon_name
    
    # 운동 세션 생성
    workout = Workout(
        user_id=current_user.id,
        type=request.type,
        route_id=request.route_id,
        route_option_id=request.option_id,
        route_name=route_name,
        shape_id=shape_id,
        shape_name=shape_name,
        shape_icon=shape_icon,
        status="active",
        started_at=datetime.utcnow()
    )
    
    db.add(workout)
    db.commit()
    db.refresh(workout)
    
    return WorkoutStartResponseWrapper(
        success=True,
        data=WorkoutStartResponse(
            workout_id=workout.id,
            status="active",
            started_at=workout.started_at,
            route_info={
                "name": route_name,
                "shape_id": shape_id,
                "shape_name": shape_name,
                "shape_icon": shape_icon,
                "target_distance": float(route_option.distance) if route_option else None
            } if route_option else None
        ),
        message="운동이 시작되었습니다"
    )


# ============================================
# 실시간 위치 트래킹
# ============================================
@router.post(
    "/{workout_id}/track",
    response_model=WorkoutTrackResponseWrapper,
    summary="실시간 위치 트래킹",
    description="""
    운동 중 실시간 위치 데이터를 전송합니다.
    
    **권장 전송 주기:** 3-5초마다
    
    **전송 데이터:**
    - coordinates: 좌표 배열 (최대 10개씩 배치 전송 가능)
    - current_distance: 현재까지 이동 거리
    - current_duration: 현재까지 경과 시간 (초)
    
    **응답:**
    - 현재 통계 (거리, 시간, 페이스, 칼로리)
    - 경로 이탈 여부 (경로 선택 시)
    """
)
def track_workout(
    workout_id: int = Path(..., description="운동 ID"),
    request: WorkoutTrackRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """실시간 트래킹 엔드포인트"""
    
    # 운동 세션 조회
    workout = db.query(Workout).filter(
        Workout.id == workout_id,
        Workout.user_id == current_user.id
    ).first()
    
    if not workout:
        raise NotFoundException(
            resource="Workout",
            resource_id=workout_id
        )
    
    if workout.status != "active":
        raise ValidationException(
            message="진행 중인 운동이 아닙니다",
            field="status"
        )
    
    # 좌표 데이터 저장
    if request and request.coordinates:
        for coord in request.coordinates:
            track = WorkoutTrack(
                workout_id=workout_id,
                latitude=coord.lat,
                longitude=coord.lng,
                altitude=coord.altitude,
                speed=coord.speed,
                timestamp=coord.timestamp or datetime.utcnow()
            )
            db.add(track)
    
    # 운동 현황 업데이트
    if request:
        if request.current_distance:
            workout.distance = request.current_distance
        if request.current_duration:
            workout.duration = request.current_duration
    
    db.commit()
    
    # 페이스 계산 (분/km)
    avg_pace = None
    if workout.distance and workout.distance > 0 and workout.duration:
        avg_pace = (workout.duration / 60) / float(workout.distance)  # 분/km
    
    # 칼로리 계산 (간단한 공식: MET * 체중 * 시간)
    # 달리기 MET: ~10, 걷기 MET: ~3.5
    met = 10 if workout.type == "running" else 3.5
    weight = 70  # TODO: 사용자 체중 정보 사용
    calories = int(met * weight * (workout.duration / 3600)) if workout.duration else 0
    workout.calories = calories
    
    db.commit()
    
    # 경로 이탈 여부 체크 (TODO: 실제 구현 필요)
    is_off_route = False
    
    return WorkoutTrackResponseWrapper(
        success=True,
        data=WorkoutTrackResponse(
            workout_id=workout.id,
            distance=float(workout.distance) if workout.distance else 0,
            duration=workout.duration or 0,
            avg_pace=round(avg_pace, 2) if avg_pace else None,
            calories=calories,
            is_off_route=is_off_route
        )
    )


# ============================================
# 운동 일시정지
# ============================================
@router.post(
    "/{workout_id}/pause",
    response_model=CommonResponse,
    summary="운동 일시정지",
    description="진행 중인 운동을 일시정지합니다."
)
def pause_workout(
    workout_id: int = Path(..., description="운동 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """운동 일시정지 엔드포인트"""
    
    workout = db.query(Workout).filter(
        Workout.id == workout_id,
        Workout.user_id == current_user.id
    ).first()
    
    if not workout:
        raise NotFoundException(
            resource="Workout",
            resource_id=workout_id
        )
    
    if workout.status != "active":
        raise ValidationException(
            message="진행 중인 운동만 일시정지할 수 있습니다",
            field="status"
        )
    
    workout.status = "paused"
    workout.paused_at = datetime.utcnow()
    db.commit()
    
    return CommonResponse(
        success=True,
        message="운동이 일시정지되었습니다",
        data={"paused_at": workout.paused_at.isoformat()}
    )


# ============================================
# 운동 재개
# ============================================
@router.post(
    "/{workout_id}/resume",
    response_model=CommonResponse,
    summary="운동 재개",
    description="일시정지된 운동을 재개합니다."
)
def resume_workout(
    workout_id: int = Path(..., description="운동 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """운동 재개 엔드포인트"""
    
    workout = db.query(Workout).filter(
        Workout.id == workout_id,
        Workout.user_id == current_user.id
    ).first()
    
    if not workout:
        raise NotFoundException(
            resource="Workout",
            resource_id=workout_id
        )
    
    if workout.status != "paused":
        raise ValidationException(
            message="일시정지된 운동만 재개할 수 있습니다",
            field="status"
        )
    
    # 일시정지 시간 계산하여 총 일시정지 시간에 추가
    if workout.paused_at:
        pause_duration = int((datetime.utcnow() - workout.paused_at).total_seconds())
        workout.total_pause_time = (workout.total_pause_time or 0) + pause_duration
    
    workout.status = "active"
    workout.paused_at = None
    db.commit()
    
    return CommonResponse(
        success=True,
        message="운동이 재개되었습니다",
        data={"resumed_at": datetime.utcnow().isoformat()}
    )


# ============================================
# 운동 완료
# ============================================
@router.post(
    "/{workout_id}/complete",
    response_model=WorkoutCompleteResponseWrapper,
    summary="운동 완료",
    description="""
    운동을 완료하고 결과를 저장합니다.
    
    **자동 계산:**
    - 총 거리, 시간, 칼로리
    - 평균 페이스
    - 구간별 기록 (splits)
    
    **달성 업적:**
    - 운동 완료 시 획득한 업적 반환
    """
)
def complete_workout(
    workout_id: int = Path(..., description="운동 ID"),
    request: WorkoutCompleteRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """운동 완료 엔드포인트"""
    
    workout = db.query(Workout).filter(
        Workout.id == workout_id,
        Workout.user_id == current_user.id
    ).first()
    
    if not workout:
        raise NotFoundException(
            resource="Workout",
            resource_id=workout_id
        )
    
    if workout.status not in ["active", "paused"]:
        raise ValidationException(
            message="진행 중인 운동만 완료할 수 있습니다",
            field="status"
        )
    
    # 최종 데이터 업데이트
    if request:
        if request.final_distance:
            workout.distance = request.final_distance
        if request.final_duration:
            workout.duration = request.final_duration
        if request.final_path:
            workout.path_data = {
                "coordinates": [
                    {"lat": p.lat, "lng": p.lng} for p in request.final_path
                ]
            }
    
    # 페이스 계산
    if workout.distance and float(workout.distance) > 0 and workout.duration:
        workout.avg_pace = (workout.duration / 60) / float(workout.distance)
    
    # 칼로리 계산
    met = 10 if workout.type == "running" else 3.5
    weight = 70  # TODO: 사용자 체중 정보 사용
    workout.calories = int(met * weight * (workout.duration / 3600)) if workout.duration else 0
    
    # 완료 처리
    workout.status = "completed"
    workout.completed_at = datetime.utcnow()
    
    # 사용자 통계 업데이트
    stats = current_user.stats
    if stats:
        stats.total_distance += float(workout.distance) if workout.distance else 0
        stats.total_workouts += 1
        stats.total_calories += workout.calories or 0
        stats.total_duration += workout.duration or 0
    else:
        # 통계가 없으면 생성
        stats = UserStats(
            user_id=current_user.id,
            total_distance=float(workout.distance) if workout.distance else 0,
            total_workouts=1,
            total_calories=workout.calories or 0,
            total_duration=workout.duration or 0
        )
        db.add(stats)
    
    db.commit()
    
    # 업적 확인 (TODO: 실제 업적 로직 구현)
    achievements = check_achievements(current_user.id, workout, db)
    
    # 구간 기록 조회
    splits = db.query(WorkoutSplit).filter(
        WorkoutSplit.workout_id == workout_id
    ).order_by(WorkoutSplit.km_mark).all()
    
    split_list = []
    for split in splits:
        split_list.append(WorkoutSplitSchema(
            km=split.km_mark,
            time=split.split_time,
            pace=split.pace
        ))
    
    return WorkoutCompleteResponseWrapper(
        success=True,
        data=WorkoutCompleteResponse(
            workout_id=workout.id,
            summary={
                "distance": float(workout.distance) if workout.distance else 0,
                "duration": workout.duration or 0,
                "avg_pace": round(workout.avg_pace, 2) if workout.avg_pace else None,
                "calories": workout.calories or 0,
                "type": workout.type
            },
            splits=split_list,
            achievements=achievements,
            completed_at=workout.completed_at
        ),
        message="운동이 완료되었습니다"
    )


def check_achievements(user_id: int, workout: Workout, db: Session) -> List[AchievementSchema]:
    """
    운동 완료 시 달성한 업적을 확인합니다.
    
    TODO: 실제 업적 로직 구현
    - 첫 운동 완료
    - 5km 달성
    - 10km 달성
    - 연속 7일 운동
    - 등등
    """
    achievements = []
    
    # 첫 운동 완료 체크
    total_workouts = db.query(func.count(Workout.id)).filter(
        Workout.user_id == user_id,
        Workout.status == "completed"
    ).scalar()
    
    if total_workouts == 1:
        achievements.append(AchievementSchema(
            id="first_workout",
            name="첫 걸음",
            description="첫 번째 운동을 완료했습니다!",
            icon="🏃",
            unlocked_at=datetime.utcnow()
        ))
    
    return achievements


# ============================================
# 운동 취소
# ============================================
@router.delete(
    "/{workout_id}",
    response_model=CommonResponse,
    summary="운동 취소",
    description="진행 중인 운동을 취소합니다. 완료된 운동은 취소할 수 없습니다."
)
def cancel_workout(
    workout_id: int = Path(..., description="운동 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """운동 취소 엔드포인트"""
    
    workout = db.query(Workout).filter(
        Workout.id == workout_id,
        Workout.user_id == current_user.id
    ).first()
    
    if not workout:
        raise NotFoundException(
            resource="Workout",
            resource_id=workout_id
        )
    
    if workout.status == "completed":
        raise ValidationException(
            message="완료된 운동은 취소할 수 없습니다",
            field="status"
        )
    
    workout.status = "cancelled"
    workout.deleted_at = datetime.utcnow()
    db.commit()
    
    return CommonResponse(
        success=True,
        message="운동이 취소되었습니다"
    )


# ============================================
# 운동 상세 조회
# ============================================
@router.get(
    "/{workout_id}",
    response_model=WorkoutDetailResponseWrapper,
    summary="운동 상세 조회",
    description="""
    운동 기록의 상세 정보를 조회합니다.
    
    **포함 정보:**
    - 기본 통계 (거리, 시간, 페이스, 칼로리)
    - 이동 경로 좌표
    - 구간별 기록
    - 경로 정보 (선택한 경우)
    """
)
def get_workout_detail(
    workout_id: int = Path(..., description="운동 ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """운동 상세 조회 엔드포인트"""
    
    workout = db.query(Workout).filter(
        Workout.id == workout_id,
        Workout.user_id == current_user.id,
        Workout.deleted_at.is_(None)
    ).first()
    
    if not workout:
        raise NotFoundException(
            resource="Workout",
            resource_id=workout_id
        )
    
    # 이동 경로 조회
    tracks = db.query(WorkoutTrack).filter(
        WorkoutTrack.workout_id == workout_id
    ).order_by(WorkoutTrack.timestamp).all()
    
    path_coordinates = []
    for track in tracks:
        path_coordinates.append({
            "lat": track.latitude,
            "lng": track.longitude,
            "timestamp": track.timestamp.isoformat()
        })
    
    # 구간 기록 조회
    splits = db.query(WorkoutSplit).filter(
        WorkoutSplit.workout_id == workout_id
    ).order_by(WorkoutSplit.km_mark).all()
    
    split_list = []
    for split in splits:
        split_list.append(WorkoutSplitSchema(
            km=split.km_mark,
            time=split.split_time,
            pace=split.pace
        ))
    
    return WorkoutDetailResponseWrapper(
        success=True,
        data=WorkoutDetailResponse(
            id=workout.id,
            type=workout.type,
            status=workout.status,
            distance=float(workout.distance) if workout.distance else 0,
            duration=workout.duration or 0,
            avg_pace=round(workout.avg_pace, 2) if workout.avg_pace else None,
            calories=workout.calories or 0,
            route_info={
                "name": workout.route_name,
                "shape_id": workout.shape_id,
                "shape_name": workout.shape_name,
                "shape_icon": workout.shape_icon
            } if workout.route_name else None,
            path=path_coordinates,
            splits=split_list,
            started_at=workout.started_at,
            completed_at=workout.completed_at
        )
    )


# ============================================
# 현재 진행 중인 운동 조회
# ============================================
@router.get(
    "/current/status",
    summary="현재 운동 상태 조회",
    description="현재 진행 중인 운동이 있는지 확인합니다."
)
def get_current_workout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """현재 운동 상태 조회 엔드포인트"""
    
    active_workout = db.query(Workout).filter(
        Workout.user_id == current_user.id,
        Workout.status.in_(["active", "paused"])
    ).first()
    
    if not active_workout:
        return {
            "success": True,
            "data": {"has_active_workout": False},
            "message": "진행 중인 운동이 없습니다"
        }
    
    return {
        "success": True,
        "data": {
            "has_active_workout": True,
            "workout_id": active_workout.id,
            "status": active_workout.status,
            "type": active_workout.type,
            "started_at": active_workout.started_at.isoformat(),
            "distance": float(active_workout.distance) if active_workout.distance else 0,
            "duration": active_workout.duration or 0
        },
        "message": "진행 중인 운동이 있습니다"
    }
