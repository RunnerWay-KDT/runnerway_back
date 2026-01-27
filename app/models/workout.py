# ============================================
# app/models/workout.py - 운동 관련 데이터베이스 모델
# ============================================
# 이 파일은 운동 기록, 추적, 성취와 관련된 모든 테이블을 정의합니다.
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
    - 운동 시작 시 'active', 일시정지 시 'paused', 완료 시 'completed'
    - Soft Delete: deleted_at이 있으면 삭제된 기록
    """
    __tablename__ = "workouts"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # 경로 정보
    route_id = Column(String(36), ForeignKey("routes.id"), nullable=True)
    route_option_id = Column(String(36), ForeignKey("route_options.id"), nullable=True)
    route_name = Column(String(100), nullable=False)    # 경로 이름 (스냅샷)
    
    # 운동 타입 및 상태
    type = Column(String(20), nullable=False)           # running / walking
    status = Column(String(20), nullable=False, default="active")  # active/paused/completed
    
    # ========== 시간 정보 ==========
    started_at = Column(DateTime, nullable=False)       # 운동 시작 시간
    completed_at = Column(DateTime, nullable=True)      # 운동 완료 시간
    
    # ========== 위치 정보 ==========
    start_latitude = Column(DECIMAL(10, 7), nullable=False)   # 시작 위도
    start_longitude = Column(DECIMAL(10, 7), nullable=False)  # 시작 경도
    end_latitude = Column(DECIMAL(10, 7), nullable=True)      # 종료 위도
    end_longitude = Column(DECIMAL(10, 7), nullable=True)     # 종료 경도
    
    # ========== 운동 통계 ==========
    distance = Column(DECIMAL(5, 2), nullable=True)     # 총 거리 (km)
    duration = Column(Integer, nullable=True)            # 총 시간 (초)
    
    avg_pace = Column(String(20), nullable=True)        # 평균 페이스 (6'50")
    max_pace = Column(String(20), nullable=True)        # 최고 페이스
    min_pace = Column(String(20), nullable=True)        # 최저 페이스
    
    calories = Column(Integer, nullable=True)           # 소모 칼로리 (kcal)
    
    # 심박수 (웨어러블 연동 시)
    heart_rate_avg = Column(Integer, nullable=True)     # 평균 심박수
    heart_rate_max = Column(Integer, nullable=True)     # 최대 심박수
    
    # 고도
    elevation_gain = Column(Integer, nullable=True)     # 상승 고도 (m)
    elevation_loss = Column(Integer, nullable=True)     # 하강 고도 (m)
    
    # ========== 경로 완성도 ==========
    route_completion = Column(DECIMAL(5, 2), nullable=True)  # 경로 완주율 (%)
    shape_accuracy = Column(DECIMAL(5, 2), nullable=True)    # 도형 정확도 (%)
    
    # 실제 이동 경로 [{lat, lng, timestamp}]
    actual_path = Column(JSON, nullable=True)
    
    # ========== 도형 정보 (스냅샷) ==========
    shape_id = Column(String(50), nullable=True)        # 도형 ID
    shape_name = Column(String(50), nullable=True)      # 도형 이름
    shape_icon = Column(String(50), nullable=True)      # 도형 아이콘
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)        # 삭제일 (Soft Delete)
    
    # ========== 관계 정의 ==========
    splits = relationship("WorkoutSplit", back_populates="workout", lazy="select")
    tracks = relationship("WorkoutTrack", back_populates="workout", lazy="select")
    achievements = relationship("WorkoutAchievement", back_populates="workout", lazy="select")
    
    def __repr__(self):
        return f"<Workout(id={self.id}, type={self.type}, status={self.status})>"


class WorkoutSplit(Base):
    """
    운동 구간 기록 테이블 (workout_splits)
    
    km 단위로 구간별 페이스와 시간을 기록합니다.
    예: 1km - 6'30", 2km - 6'45" 등
    """
    __tablename__ = "workout_splits"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workout_id = Column(String(36), ForeignKey("workouts.id"), nullable=False)
    
    km = Column(Integer, nullable=False)                # km 구간 (1, 2, 3...)
    pace = Column(String(20), nullable=False)           # 해당 구간 페이스
    duration = Column(Integer, nullable=False)          # 해당 구간 소요 시간 (초)
    
    # 관계 정의
    workout = relationship("Workout", back_populates="splits")


class WorkoutTrack(Base):
    """
    운동 실시간 추적 테이블 (workout_tracks)
    
    운동 중 10초마다 위치와 상태를 기록합니다.
    실시간 추적 데이터를 저장하여 이동 경로를 재현할 수 있습니다.
    
    [신입 개발자를 위한 팁]
    - 프론트엔드에서 10초마다 POST /workouts/{id}/track 호출
    - GPS 좌표와 함께 현재 거리, 시간, 페이스 등을 전송
    """
    __tablename__ = "workout_tracks"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workout_id = Column(String(36), ForeignKey("workouts.id"), nullable=False)
    
    timestamp = Column(DateTime, nullable=False)        # 기록 시점
    
    # 위치 정보
    latitude = Column(DECIMAL(10, 7), nullable=False)   # 위도
    longitude = Column(DECIMAL(10, 7), nullable=False)  # 경도
    accuracy = Column(DECIMAL(5, 2), nullable=True)     # GPS 정확도 (m)
    
    # 누적 통계
    distance = Column(DECIMAL(5, 2), nullable=True)     # 누적 거리 (km)
    duration = Column(Integer, nullable=True)           # 누적 시간 (초)
    current_pace = Column(String(20), nullable=True)    # 현재 페이스
    heart_rate = Column(Integer, nullable=True)         # 심박수
    
    # 관계 정의
    workout = relationship("Workout", back_populates="tracks")


class WorkoutAchievement(Base):
    """
    운동 성취 테이블 (workout_achievements)
    
    운동 완료 시 달성한 성취를 기록합니다.
    예: 개인 최고 기록, 연속 운동, 마일스톤 달성 등
    """
    __tablename__ = "workout_achievements"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    workout_id = Column(String(36), ForeignKey("workouts.id"), nullable=False)
    
    # 성취 타입: personal_best / streak / milestone
    type = Column(String(30), nullable=False)
    title = Column(String(100), nullable=False)         # 성취 제목
    description = Column(String(255), nullable=True)    # 성취 설명
    icon = Column(String(50), nullable=True)            # 아이콘
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # 관계 정의
    workout = relationship("Workout", back_populates="achievements")
