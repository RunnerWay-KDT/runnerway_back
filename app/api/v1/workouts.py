# ============================================
# app/api/v1/workouts.py - 운동 API 라우터
# ============================================
# 운동 세션 시작, 완료, 기록 조회 등
# workouts 테이블 + workout_splits 테이블에 저장합니다.
# ============================================

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models.user import User, UserStats
from app.models.workout import Workout, WorkoutSplit
from app.schemas.workout import (
    WorkoutStartRequest, WorkoutStartResponse, WorkoutStartResponseWrapper,
    WorkoutCompleteRequest, WorkoutCompleteResponse, WorkoutCompleteResponseWrapper,
    WorkoutDetailSchema, WorkoutDetailResponseWrapper,
    WorkoutSummarySchema, SplitSchema,
)
from app.schemas.common import CommonResponse
from app.services.workout_service import WorkoutService
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
    workouts 테이블에 새 레코드를 INSERT 합니다.
    
    **필수:** route_name, start_location, started_at
    **선택:** route_id, route_option_id, type, mode
    """
)
def start_workout(
    request: WorkoutStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """운동 시작 엔드포인트"""
    service = WorkoutService(db)
    
    workout = service.start_workout(
        user_id=current_user.id,
        route_name=request.route_name,
        start_latitude=request.start_location.latitude,
        start_longitude=request.start_location.longitude,
        started_at=request.started_at,
        route_id=request.route_id,
        route_option_id=request.route_option_id,
        workout_type=request.type,
        mode=request.mode,
    )
    
    return WorkoutStartResponseWrapper(
        success=True,
        data=WorkoutStartResponse(
            workout_id=workout.id,
            status="active",
            started_at=workout.started_at,
        ),
        message="운동이 시작되었습니다"
    )


# ============================================
# 운동 완료
# ============================================
@router.post(
    "/{workout_id}/complete",
    response_model=WorkoutCompleteResponseWrapper,
    summary="운동 완료",
    description="""
    운동을 완료하고 결과를 workouts + workout_splits 테이블에 저장합니다.
    
    **저장되는 데이터:**
    - workouts: distance, duration, avg_pace, calories, actual_path, 등
    - workout_splits: km별 구간 기록 (pace, duration)
    """
)
def complete_workout(
    workout_id: str = Path(..., description="운동 UUID"),
    request: WorkoutCompleteRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """운동 완료 엔드포인트"""
    service = WorkoutService(db)
    
    # splits를 dict 리스트로 변환
    splits_data = None
    if request and request.splits:
        splits_data = [
            {"km": s.km, "pace": s.pace, "duration": s.duration}
            for s in request.splits
        ]
    
    # actual_path 변환
    actual_path_data = []
    if request and request.route and request.route.actual_path:
        actual_path_data = request.route.actual_path
    
    # 종료 위치
    end_lat = None
    end_lng = None
    if request and request.end_location:
        end_lat = request.end_location.latitude
        end_lng = request.end_location.longitude
    
    workout = service.complete_workout(
        workout_id=workout_id,
        user_id=current_user.id,
        completed_at=request.completed_at if request else datetime.utcnow(),
        distance=request.final_metrics.distance if request else 0,
        duration=request.final_metrics.duration if request else 0,
        avg_pace=request.final_metrics.average_pace if request else "0'00\"",
        calories=request.final_metrics.calories if request else 0,
        actual_path=actual_path_data,
        splits=splits_data,
        end_latitude=end_lat,
        end_longitude=end_lng,
        max_pace=request.final_metrics.max_pace if request and request.final_metrics else None,
        min_pace=request.final_metrics.min_pace if request and request.final_metrics else None,
        elevation_gain=request.elevation_gain if request else None,
        elevation_loss=request.elevation_loss if request else None,
        route_completion=request.route_completion if request else None,
    )
    
    # route_options.coordinates에서 계획 경로 가져오기
    planned_path = service.get_planned_path(workout)
    
    return WorkoutCompleteResponseWrapper(
        success=True,
        data=WorkoutCompleteResponse(
            workout_id=workout.id,
            completed_distance=float(workout.distance) if workout.distance else 0,
            completed_time=workout.duration or 0,
            average_pace=workout.avg_pace or "0'00\"",
            calories=workout.calories or 0,
            route_completion=float(workout.route_completion) if workout.route_completion else None,
            planned_path=planned_path,
            actual_path=workout.actual_path,
            saved_at=workout.completed_at or datetime.utcnow(),
        ),
        message="운동이 완료되었습니다"
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
    workout_id: str = Path(..., description="운동 UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """운동 일시정지 엔드포인트"""
    service = WorkoutService(db)
    workout = service.pause_workout(workout_id, current_user.id)
    
    return CommonResponse(
        success=True,
        message="운동이 일시정지되었습니다",
        data={"status": "paused"}
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
    workout_id: str = Path(..., description="운동 UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """운동 재개 엔드포인트"""
    service = WorkoutService(db)
    workout = service.resume_workout(workout_id, current_user.id)
    
    return CommonResponse(
        success=True,
        message="운동이 재개되었습니다",
        data={"status": "active"}
    )


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
    workout_id: str = Path(..., description="운동 UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """운동 취소 엔드포인트"""
    service = WorkoutService(db)
    service.cancel_workout(workout_id, current_user.id)
    
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
    description="운동 기록의 상세 정보 + 구간 기록을 조회합니다."
)
def get_workout_detail(
    workout_id: str = Path(..., description="운동 UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """운동 상세 조회 엔드포인트"""
    service = WorkoutService(db)
    
    workout = service.get_workout(workout_id, current_user.id)
    splits = service.get_workout_splits(workout_id)
    planned_path = service.get_planned_path(workout)
    
    split_list = [
        SplitSchema(km=s.km, pace=s.pace, duration=s.duration)
        for s in splits
    ]
    
    return WorkoutDetailResponseWrapper(
        success=True,
        data=WorkoutDetailSchema(
            id=workout.id,
            route_name=workout.route_name,
            type=workout.type,
            mode=workout.mode,
            distance=float(workout.distance) if workout.distance else None,
            duration=workout.duration,
            avg_pace=workout.avg_pace,
            calories=workout.calories,
            route_completion=float(workout.route_completion) if workout.route_completion else None,
            started_at=workout.started_at,
            completed_at=workout.completed_at,
            planned_path=planned_path,
            actual_path=workout.actual_path,
            splits=split_list,
            start_latitude=float(workout.start_latitude),
            start_longitude=float(workout.start_longitude),
            end_latitude=float(workout.end_latitude) if workout.end_latitude else None,
            end_longitude=float(workout.end_longitude) if workout.end_longitude else None,
            created_at=workout.created_at,
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
    service = WorkoutService(db)
    active_workout = service.get_active_workout(current_user.id)
    
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
            "mode": active_workout.mode,
            "route_name": active_workout.route_name,
            "started_at": active_workout.started_at.isoformat(),
            "distance": float(active_workout.distance) if active_workout.distance else 0,
            "duration": active_workout.duration or 0
        },
        "message": "진행 중인 운동이 있습니다"
    }
