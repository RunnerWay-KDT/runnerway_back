# ============================================
# app/services/workout_service.py - 운동 서비스
# ============================================
# 운동 시작, 트래킹, 완료, 기록 조회 등 운동 관련 비즈니스 로직을 처리합니다.
# workouts 테이블, workout_splits 테이블에 맞춰 구현되었습니다.
# ============================================

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user import User, UserStats
from app.models.workout import Workout, WorkoutSplit
from app.models.route import RouteOption
from app.core.exceptions import NotFoundException, ValidationException


class WorkoutService:
    """
    운동 서비스 클래스
    
    workouts 테이블 컬럼:
      id, user_id, route_id, route_option_id, route_name,
      type (preset/custom/null), mode (running/walking/null),
      status (active/paused/completed),
      started_at, completed_at,
      start_latitude, start_longitude, end_latitude, end_longitude,
      distance, duration, avg_pace, max_pace, min_pace,
      calories, elevation_gain, elevation_loss, route_completion,
      actual_path (JSON: [{lat, lng, timestamp}]),
      created_at, updated_at, deleted_at
    
    workout_splits 테이블 컬럼:
      id, workout_id, km, pace, duration
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # ============================================
    # 운동 세션 관리
    # ============================================
    
    def start_workout(
        self,
        user_id: str,
        route_name: str,
        start_latitude: float,
        start_longitude: float,
        started_at: datetime,
        route_id: str = None,
        route_option_id: str = None,
        workout_type: str = None,
        mode: str = None,
    ) -> Workout:
        """
        운동 세션 시작 → workouts 테이블에 INSERT
        
        Args:
            user_id: 사용자 UUID
            route_name: 경로 이름 (스냅샷)
            start_latitude: 시작점 위도
            start_longitude: 시작점 경도
            started_at: 시작 시간 (클라이언트 전달)
            route_id: 경로 ID (선택)
            route_option_id: 경로 옵션 ID (선택)
            workout_type: preset / custom / None
            mode: running / walking / None
        
        Returns:
            Workout: 생성된 운동 세션
        """
        # 이미 진행 중인 운동 확인
        active = self.db.query(Workout).filter(
            Workout.user_id == user_id,
            Workout.status.in_(["active", "paused"]),
            Workout.deleted_at.is_(None)
        ).first()
        
        if active:
            raise ValidationException(
                message="이미 진행 중인 운동이 있습니다",
                field="workout"
            )
        
        workout = Workout(
            user_id=user_id,
            route_id=route_id,
            route_option_id=route_option_id,
            route_name=route_name,
            type=workout_type,
            mode=mode,
            status="active",
            started_at=started_at,
            start_latitude=start_latitude,
            start_longitude=start_longitude,
        )
        
        self.db.add(workout)
        self.db.commit()
        self.db.refresh(workout)
        
        return workout
    
    
    def complete_workout(
        self,
        workout_id: str,
        user_id: str,
        completed_at: datetime,
        distance: float,
        duration: int,
        avg_pace: str,
        calories: int,
        actual_path: List[Dict[str, Any]],
        splits: List[Dict[str, Any]] = None,
        end_latitude: float = None,
        end_longitude: float = None,
        max_pace: str = None,
        min_pace: str = None,
        elevation_gain: int = None,
        elevation_loss: int = None,
        route_completion: float = None,
    ) -> Workout:
        """
        운동 완료 → workouts 테이블 UPDATE + workout_splits 테이블 INSERT
        
        Args:
            workout_id: 운동 UUID
            user_id: 사용자 UUID
            completed_at: 완료 시간
            distance: 총 거리 (km)
            duration: 총 시간 (초)
            avg_pace: 평균 페이스 (예: "6'30\"")
            calories: 소모 칼로리 (kcal)
            actual_path: [{lat, lng, timestamp}] 배열
            splits: [{km, pace, duration}] 배열
            end_latitude: 종료 위도
            end_longitude: 종료 경도
            max_pace: 최고 페이스
            min_pace: 최저 페이스
            elevation_gain: 상승 고도 누적합
            elevation_loss: 하강 고도 누적합
            route_completion: 경로 완주율 (%)
        """
        workout = self._get_workout(workout_id, user_id)
        
        if workout.status not in ["active", "paused"]:
            raise ValidationException(
                message="진행 중인 운동만 완료할 수 있습니다",
                field="status"
            )
        
        # ---- workouts 테이블 업데이트 ----
        workout.status = "completed"
        workout.completed_at = completed_at
        workout.distance = distance
        workout.duration = duration
        workout.avg_pace = avg_pace
        workout.max_pace = max_pace
        workout.min_pace = min_pace
        workout.calories = calories
        workout.elevation_gain = elevation_gain
        workout.elevation_loss = elevation_loss
        workout.route_completion = route_completion
        workout.actual_path = actual_path
        
        if end_latitude is not None:
            workout.end_latitude = end_latitude
        if end_longitude is not None:
            workout.end_longitude = end_longitude
        
        # ---- workout_splits 테이블에 구간 기록 저장 ----
        if splits:
            for split_data in splits:
                split = WorkoutSplit(
                    workout_id=workout.id,
                    km=split_data["km"],
                    pace=split_data["pace"],
                    duration=split_data["duration"],
                )
                self.db.add(split)
        
        # ---- 사용자 통계 업데이트 ----
        self._update_user_stats(user_id, workout)
        
        self.db.commit()
        self.db.refresh(workout)
        
        return workout
    
    
    def pause_workout(self, workout_id: str, user_id: str) -> Workout:
        """운동 일시정지"""
        workout = self._get_workout(workout_id, user_id)
        
        if workout.status != "active":
            raise ValidationException(
                message="진행 중인 운동만 일시정지할 수 있습니다",
                field="status"
            )
        
        workout.status = "paused"
        self.db.commit()
        
        return workout
    
    
    def resume_workout(self, workout_id: str, user_id: str) -> Workout:
        """운동 재개"""
        workout = self._get_workout(workout_id, user_id)
        
        if workout.status != "paused":
            raise ValidationException(
                message="일시정지된 운동만 재개할 수 있습니다",
                field="status"
            )
        
        workout.status = "active"
        self.db.commit()
        
        return workout
    
    
    def cancel_workout(self, workout_id: str, user_id: str) -> bool:
        """운동 취소 (Soft Delete)"""
        workout = self._get_workout(workout_id, user_id)
        
        if workout.status == "completed":
            raise ValidationException(
                message="완료된 운동은 취소할 수 없습니다",
                field="status"
            )
        
        workout.deleted_at = datetime.utcnow()
        self.db.commit()
        
        return True
    
    
    # ============================================
    # 운동 기록 조회
    # ============================================
    
    def get_workout(self, workout_id: str, user_id: str) -> Optional[Workout]:
        """운동 상세 조회"""
        return self._get_workout(workout_id, user_id)
    
    
    def get_workout_list(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        workout_type: str = None,
        sort: str = "date_desc"
    ) -> tuple:
        """운동 기록 목록 조회"""
        query = self.db.query(Workout).filter(
            Workout.user_id == user_id,
            Workout.status == "completed",
            Workout.deleted_at.is_(None)
        )
        
        if workout_type:
            query = query.filter(Workout.type == workout_type)
        
        if sort == "distance_desc":
            query = query.order_by(Workout.distance.desc())
        elif sort == "calories_desc":
            query = query.order_by(Workout.calories.desc())
        else:
            query = query.order_by(Workout.completed_at.desc())
        
        total = query.count()
        offset = (page - 1) * limit
        workouts = query.offset(offset).limit(limit).all()
        
        return workouts, total
    
    
    def get_active_workout(self, user_id: str) -> Optional[Workout]:
        """현재 진행 중인 운동 조회"""
        return self.db.query(Workout).filter(
            Workout.user_id == user_id,
            Workout.status.in_(["active", "paused"]),
            Workout.deleted_at.is_(None)
        ).first()
    
    
    def get_workout_splits(self, workout_id: str) -> List[WorkoutSplit]:
        """운동 구간 기록 조회 (workout_splits 테이블)"""
        return self.db.query(WorkoutSplit).filter(
            WorkoutSplit.workout_id == workout_id
        ).order_by(WorkoutSplit.km).all()
    
    
    def get_planned_path(self, workout: Workout) -> Optional[List[Dict[str, Any]]]:
        """
        운동에 연결된 경로 옵션의 계획 경로(coordinates) 조회
        
        workouts.route_option_id → route_options.coordinates
        """
        if not workout.route_option_id:
            return None
        
        route_option = self.db.query(RouteOption).filter(
            RouteOption.id == workout.route_option_id
        ).first()
        
        if not route_option or not route_option.coordinates:
            return None
        
        return route_option.coordinates
    
    
    # ============================================
    # 헬퍼 메서드
    # ============================================
    
    def _get_workout(self, workout_id: str, user_id: str) -> Workout:
        """운동 조회 (내부용)"""
        workout = self.db.query(Workout).filter(
            Workout.id == workout_id,
            Workout.user_id == user_id,
            Workout.deleted_at.is_(None)
        ).first()
        
        if not workout:
            raise NotFoundException(
                resource="Workout",
                resource_id=workout_id
            )
        
        return workout
    
    
    def _calculate_calories(self, mode: str, duration: int) -> int:
        """
        칼로리 계산
        칼로리 = MET × 체중(kg) × 시간(hour)
        - 달리기 MET: 약 10
        - 걷기 MET: 약 3.5
        """
        if not duration:
            return 0
        
        met = 10 if mode == "running" else 3.5
        weight = 70  # TODO: 실제 사용자 체중 사용
        hours = duration / 3600
        
        return int(met * weight * hours)
    
    
    def _update_user_stats(self, user_id: str, workout: Workout):
        """사용자 통계 업데이트 (user_stats 테이블)"""
        stats = self.db.query(UserStats).filter(
            UserStats.user_id == user_id
        ).first()
        
        if stats:
            stats.total_distance = float(stats.total_distance or 0) + (float(workout.distance) if workout.distance else 0)
            stats.total_workouts = (stats.total_workouts or 0) + 1
            if workout.status == "completed":
                stats.completed_routes = (stats.completed_routes or 0) + 1
        else:
            stats = UserStats(
                user_id=user_id,
                total_distance=float(workout.distance) if workout.distance else 0,
                total_workouts=1,
                completed_routes=1 if workout.status == "completed" else 0
            )
            self.db.add(stats)
