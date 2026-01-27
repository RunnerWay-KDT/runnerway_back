# ============================================
# app/services/workout_service.py - 운동 서비스
# ============================================
# 운동 시작, 트래킹, 완료, 기록 조회 등 운동 관련 비즈니스 로직을 처리합니다.
# ============================================

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user import User, UserStats
from app.models.workout import Workout, WorkoutTrack, WorkoutSplit, WorkoutAchievement
from app.models.route import RouteOption
from app.core.exceptions import NotFoundException, ValidationException


class WorkoutService:
    """
    운동 서비스 클래스
    
    [신입 개발자를 위한 설명]
    운동 관련 모든 비즈니스 로직을 담당합니다.
    - 운동 세션 시작/일시정지/재개/완료
    - 실시간 트래킹 데이터 저장
    - 운동 통계 계산
    - 업적 확인
    """
    
    def __init__(self, db: Session):
        """
        WorkoutService 초기화
        
        Args:
            db: 데이터베이스 세션
        """
        self.db = db
    
    
    # ============================================
    # 운동 세션 관리
    # ============================================
    
    def start_workout(
        self,
        user_id: int,
        workout_type: str,
        route_id: int = None,
        option_id: int = None
    ) -> Workout:
        """
        운동 세션 시작
        
        Args:
            user_id: 사용자 ID
            workout_type: 운동 타입 (running/walking)
            route_id: 선택한 경로 ID
            option_id: 선택한 경로 옵션 ID
        
        Returns:
            Workout: 생성된 운동 세션
        
        Raises:
            ValidationException: 이미 진행 중인 운동이 있는 경우
        """
        # 이미 진행 중인 운동 확인
        active = self.db.query(Workout).filter(
            Workout.user_id == user_id,
            Workout.status == "active"
        ).first()
        
        if active:
            raise ValidationException(
                message="이미 진행 중인 운동이 있습니다",
                field="workout"
            )
        
        # 경로 옵션 정보 조회
        route_name = None
        shape_id = None
        shape_name = None
        shape_icon = None
        
        if option_id:
            option = self.db.query(RouteOption).filter(
                RouteOption.id == option_id
            ).first()
            
            if option and option.route:
                route_name = option.route.name
                if option.route.shape:
                    shape_id = option.route.shape.id
                    shape_name = option.route.shape.name
                    shape_icon = option.route.shape.icon_name
        
        # 운동 세션 생성
        workout = Workout(
            user_id=user_id,
            type=workout_type,
            route_id=route_id,
            route_option_id=option_id,
            route_name=route_name,
            shape_id=shape_id,
            shape_name=shape_name,
            shape_icon=shape_icon,
            status="active",
            started_at=datetime.utcnow()
        )
        
        self.db.add(workout)
        self.db.commit()
        self.db.refresh(workout)
        
        return workout
    
    
    def pause_workout(self, workout_id: int, user_id: int) -> Workout:
        """
        운동 일시정지
        
        Args:
            workout_id: 운동 ID
            user_id: 사용자 ID
        
        Returns:
            Workout: 업데이트된 운동 세션
        
        Raises:
            NotFoundException: 운동을 찾을 수 없는 경우
            ValidationException: 진행 중인 운동이 아닌 경우
        """
        workout = self._get_workout(workout_id, user_id)
        
        if workout.status != "active":
            raise ValidationException(
                message="진행 중인 운동만 일시정지할 수 있습니다",
                field="status"
            )
        
        workout.status = "paused"
        workout.paused_at = datetime.utcnow()
        self.db.commit()
        
        return workout
    
    
    def resume_workout(self, workout_id: int, user_id: int) -> Workout:
        """
        운동 재개
        
        Args:
            workout_id: 운동 ID
            user_id: 사용자 ID
        
        Returns:
            Workout: 업데이트된 운동 세션
        """
        workout = self._get_workout(workout_id, user_id)
        
        if workout.status != "paused":
            raise ValidationException(
                message="일시정지된 운동만 재개할 수 있습니다",
                field="status"
            )
        
        # 일시정지 시간 계산
        if workout.paused_at:
            pause_duration = int((datetime.utcnow() - workout.paused_at).total_seconds())
            workout.total_pause_time = (workout.total_pause_time or 0) + pause_duration
        
        workout.status = "active"
        workout.paused_at = None
        self.db.commit()
        
        return workout
    
    
    def complete_workout(
        self,
        workout_id: int,
        user_id: int,
        final_distance: float = None,
        final_duration: int = None,
        final_path: List[Dict] = None
    ) -> tuple[Workout, List]:
        """
        운동 완료
        
        Args:
            workout_id: 운동 ID
            user_id: 사용자 ID
            final_distance: 최종 거리 (km)
            final_duration: 최종 시간 (초)
            final_path: 최종 이동 경로
        
        Returns:
            tuple: (완료된 운동, 달성한 업적 목록)
        """
        workout = self._get_workout(workout_id, user_id)
        
        if workout.status not in ["active", "paused"]:
            raise ValidationException(
                message="진행 중인 운동만 완료할 수 있습니다",
                field="status"
            )
        
        # 최종 데이터 업데이트
        if final_distance:
            workout.distance = final_distance
        if final_duration:
            workout.duration = final_duration
        if final_path:
            workout.path_data = {"coordinates": final_path}
        
        # 페이스 계산
        if workout.distance and float(workout.distance) > 0 and workout.duration:
            workout.avg_pace = (workout.duration / 60) / float(workout.distance)
        
        # 칼로리 계산
        workout.calories = self._calculate_calories(
            workout.type,
            workout.duration
        )
        
        # 완료 처리
        workout.status = "completed"
        workout.completed_at = datetime.utcnow()
        
        # 사용자 통계 업데이트
        self._update_user_stats(user_id, workout)
        
        self.db.commit()
        
        # 업적 확인
        achievements = self._check_achievements(user_id, workout)
        
        return workout, achievements
    
    
    def cancel_workout(self, workout_id: int, user_id: int) -> bool:
        """
        운동 취소
        
        Args:
            workout_id: 운동 ID
            user_id: 사용자 ID
        
        Returns:
            bool: 취소 성공 여부
        """
        workout = self._get_workout(workout_id, user_id)
        
        if workout.status == "completed":
            raise ValidationException(
                message="완료된 운동은 취소할 수 없습니다",
                field="status"
            )
        
        workout.status = "cancelled"
        workout.deleted_at = datetime.utcnow()
        self.db.commit()
        
        return True
    
    
    # ============================================
    # 트래킹 데이터 관리
    # ============================================
    
    def save_track_data(
        self,
        workout_id: int,
        coordinates: List[Dict],
        current_distance: float = None,
        current_duration: int = None
    ) -> Dict[str, Any]:
        """
        트래킹 데이터 저장
        
        Args:
            workout_id: 운동 ID
            coordinates: 좌표 배열
            current_distance: 현재 거리
            current_duration: 현재 시간
        
        Returns:
            Dict: 현재 운동 상태
        """
        workout = self.db.query(Workout).filter(
            Workout.id == workout_id
        ).first()
        
        if not workout:
            raise NotFoundException(
                resource="Workout",
                resource_id=workout_id
            )
        
        # 좌표 데이터 저장
        for coord in coordinates:
            track = WorkoutTrack(
                workout_id=workout_id,
                latitude=coord.get("lat"),
                longitude=coord.get("lng"),
                altitude=coord.get("altitude"),
                speed=coord.get("speed"),
                timestamp=coord.get("timestamp", datetime.utcnow())
            )
            self.db.add(track)
        
        # 현재 상태 업데이트
        if current_distance:
            workout.distance = current_distance
        if current_duration:
            workout.duration = current_duration
        
        self.db.commit()
        
        # 페이스 계산
        avg_pace = None
        if workout.distance and float(workout.distance) > 0 and workout.duration:
            avg_pace = (workout.duration / 60) / float(workout.distance)
        
        # 칼로리 계산
        calories = self._calculate_calories(workout.type, workout.duration)
        
        return {
            "distance": float(workout.distance) if workout.distance else 0,
            "duration": workout.duration or 0,
            "avg_pace": round(avg_pace, 2) if avg_pace else None,
            "calories": calories,
            "is_off_route": False  # TODO: 경로 이탈 감지 구현
        }
    
    
    # ============================================
    # 운동 기록 조회
    # ============================================
    
    def get_workout(self, workout_id: int, user_id: int) -> Optional[Workout]:
        """
        운동 상세 조회
        
        Args:
            workout_id: 운동 ID
            user_id: 사용자 ID
        
        Returns:
            Optional[Workout]: 운동 정보
        """
        return self._get_workout(workout_id, user_id)
    
    
    def get_workout_list(
        self,
        user_id: int,
        page: int = 1,
        limit: int = 20,
        workout_type: str = None,
        sort: str = "date_desc"
    ) -> tuple[List[Workout], int]:
        """
        운동 기록 목록 조회
        
        Args:
            user_id: 사용자 ID
            page: 페이지 번호
            limit: 페이지당 항목 수
            workout_type: 운동 타입 필터
            sort: 정렬 방식
        
        Returns:
            tuple: (운동 목록, 전체 개수)
        """
        query = self.db.query(Workout).filter(
            Workout.user_id == user_id,
            Workout.status == "completed",
            Workout.deleted_at.is_(None)
        )
        
        # 타입 필터
        if workout_type:
            query = query.filter(Workout.type == workout_type)
        
        # 정렬
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
    
    
    def get_active_workout(self, user_id: int) -> Optional[Workout]:
        """
        현재 진행 중인 운동 조회
        
        Args:
            user_id: 사용자 ID
        
        Returns:
            Optional[Workout]: 진행 중인 운동 (없으면 None)
        """
        return self.db.query(Workout).filter(
            Workout.user_id == user_id,
            Workout.status.in_(["active", "paused"])
        ).first()
    
    
    def get_workout_tracks(self, workout_id: int) -> List[WorkoutTrack]:
        """
        운동 트래킹 데이터 조회
        
        Args:
            workout_id: 운동 ID
        
        Returns:
            List[WorkoutTrack]: 트래킹 데이터 목록
        """
        return self.db.query(WorkoutTrack).filter(
            WorkoutTrack.workout_id == workout_id
        ).order_by(WorkoutTrack.timestamp).all()
    
    
    def get_workout_splits(self, workout_id: int) -> List[WorkoutSplit]:
        """
        운동 구간 기록 조회
        
        Args:
            workout_id: 운동 ID
        
        Returns:
            List[WorkoutSplit]: 구간 기록 목록
        """
        return self.db.query(WorkoutSplit).filter(
            WorkoutSplit.workout_id == workout_id
        ).order_by(WorkoutSplit.km_mark).all()
    
    
    # ============================================
    # 헬퍼 메서드
    # ============================================
    
    def _get_workout(self, workout_id: int, user_id: int) -> Workout:
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
    
    
    def _calculate_calories(self, workout_type: str, duration: int) -> int:
        """
        칼로리 계산
        
        [공식]
        칼로리 = MET × 체중(kg) × 시간(hour)
        - 달리기 MET: 약 10
        - 걷기 MET: 약 3.5
        """
        if not duration:
            return 0
        
        met = 10 if workout_type == "running" else 3.5
        weight = 70  # TODO: 실제 사용자 체중 사용
        hours = duration / 3600
        
        return int(met * weight * hours)
    
    
    def _update_user_stats(self, user_id: int, workout: Workout):
        """사용자 통계 업데이트"""
        stats = self.db.query(UserStats).filter(
            UserStats.user_id == user_id
        ).first()
        
        if stats:
            stats.total_distance += float(workout.distance) if workout.distance else 0
            stats.total_workouts += 1
            stats.total_calories += workout.calories or 0
            stats.total_duration += workout.duration or 0
        else:
            stats = UserStats(
                user_id=user_id,
                total_distance=float(workout.distance) if workout.distance else 0,
                total_workouts=1,
                total_calories=workout.calories or 0,
                total_duration=workout.duration or 0
            )
            self.db.add(stats)
    
    
    def _check_achievements(self, user_id: int, workout: Workout) -> List[Dict]:
        """
        업적 확인
        
        [TODO: 실제 업적 로직 구현]
        """
        achievements = []
        
        # 첫 운동 완료 체크
        total = self.db.query(func.count(Workout.id)).filter(
            Workout.user_id == user_id,
            Workout.status == "completed"
        ).scalar()
        
        if total == 1:
            achievements.append({
                "id": "first_workout",
                "name": "첫 걸음",
                "description": "첫 번째 운동을 완료했습니다!",
                "icon": "🏃",
                "unlocked_at": datetime.utcnow().isoformat()
            })
        
        return achievements
