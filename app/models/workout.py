# ============================================
# app/models/workout.py - 운동 관련 데이터베이스 모델
# ============================================
# 이 파일은 운동 기록, 추적과 관련된 모든 테이블을 정의합니다.
# ============================================

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, Text, DateTime,
    ForeignKey, DECIMAL, JSON
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def generate_uuid() -> str:
    """UUID를 생성하는 헬퍼 함수"""
    return str(uuid.uuid4())


class Workout(Base):
    """
    운동 테이블 (workouts)
    
    사용자의 운동 세션 정보를 저장합니다.
    운동 시작부터 완료까지의 모든 데이터를 기록합니다.
    
    [신입 개발자를 위한 팁]
    - status 상태 변화: active → paused → active → completed
    - type: 'preset' / 'custom' / null (도형그리기 아님)
    - mode: 'running' / 'walking' / null (도형그리기)
    """
    __tablename__ = "workouts"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID, workout_id로 사용')
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment='사용자 ID')
    
    # 경로 정보
    route_id = Column(String(36), ForeignKey("routes.id"), nullable=True, comment='경로 ID')
    route_option_id = Column(String(36), ForeignKey("route_options.id"), nullable=True, comment='선택한 경로 옵션 ID')
    route_name = Column(String(100), nullable=False, comment='경로 이름 (스냅샷)')
    
    # 운동 타입 및 상태
    type = Column(String(20), nullable=True, comment='preset / custom / null은 도형그리기 아님')
    mode = Column(String(20), nullable=True, comment='running / walking / null은 도형그리기임')
    status = Column(String(20), nullable=False, default="active", comment='active/paused/completed')
    
    # ========== 시간 정보 ==========
    started_at = Column(DateTime, nullable=False, comment='운동 시작 시간')
    completed_at = Column(DateTime, nullable=True, comment='운동 완료 시간')
    
    # ========== 위치 정보 ==========
    start_latitude = Column(DECIMAL(10, 7), nullable=False)
    start_longitude = Column(DECIMAL(10, 7), nullable=False)
    end_latitude = Column(DECIMAL(10, 7), nullable=True)
    end_longitude = Column(DECIMAL(10, 7), nullable=True)
    
    # ========== 운동 통계 ==========
    distance = Column(DECIMAL(5, 2), nullable=True, comment='총 거리 (km)')
    duration = Column(Integer, nullable=True, comment='총 시간 (초)')
    
    avg_pace = Column(String(20), nullable=True, comment='평균 페이스')
    max_pace = Column(String(20), nullable=True, comment='최고 페이스')
    min_pace = Column(String(20), nullable=True, comment='최저 페이스')
    
    calories = Column(Integer, nullable=True, comment='소모 칼로리 (kcal)')
    
    # 고도
    elevation_gain = Column(Integer, nullable=True, comment='상승 고도의 누적합')
    elevation_loss = Column(Integer, nullable=True, comment='하강 고도의 누적합')
    
    # ========== 경로 완성도 ==========
    route_completion = Column(DECIMAL(5, 2), nullable=True, comment='경로 완주율 (%)')
    
    # 실제 이동 경로 [{lat, lng, timestamp}]
    actual_path = Column(JSON, nullable=True, comment='[{lat, lng, timestamp}] 배열')
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True, comment='Soft Delete')
    
    # ========== 관계 정의 ==========
    splits = relationship("WorkoutSplit", back_populates="workout", lazy="select")
    
    def __repr__(self):
        return f"<Workout(id={self.id}, type={self.type}, status={self.status})>"


class WorkoutSplit(Base):
    """
    운동 구간 기록 테이블 (workout_splits)
    
    km 단위로 구간별 페이스와 시간을 기록합니다.
    예: 1km - 6'30", 2km - 6'45" 등
    """
    __tablename__ = "workout_splits"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID')
    workout_id = Column(String(36), ForeignKey("workouts.id"), nullable=False, comment='운동 ID')
    
    km = Column(Integer, nullable=False, comment='km 구간 (1, 2, 3...)')
    pace = Column(String(20), nullable=False, comment='해당 구간 페이스')
    duration = Column(Integer, nullable=False, comment='해당 구간 소요 시간 (초)')
    
    # 관계 정의
    workout = relationship("Workout", back_populates="splits")
