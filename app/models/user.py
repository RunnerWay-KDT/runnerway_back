# ============================================
# app/models/user.py - 사용자 관련 데이터베이스 모델
# ============================================
# 이 파일은 사용자와 관련된 모든 테이블을 정의합니다.
# ============================================

import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Boolean, Integer, Text, DateTime,
    ForeignKey, DECIMAL, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def generate_uuid() -> str:
    """UUID를 생성하는 헬퍼 함수"""
    return str(uuid.uuid4())


class User(Base):
    """
    사용자 테이블 (users)
    
    앱의 모든 사용자 정보를 저장합니다.
    이메일/비밀번호 로그인을 사용합니다.
    
    [신입 개발자를 위한 팁]
    - __tablename__: 실제 데이터베이스 테이블 이름
    - Column: 테이블의 컬럼(필드)을 정의
    - relationship: 다른 테이블과의 관계를 정의 (JOIN용)
    """
    __tablename__ = "users"
    
    # ========== 기본 필드 ==========
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID, 사용자 고유 식별자')
    email = Column(String(255), unique=True, nullable=False, index=True, comment='이메일 (로그인 ID)')
    password_hash = Column(String(255), nullable=True, comment='해시된 비밀번호')
    name = Column(String(100), nullable=False, comment='사용자 이름 (최소 2자)')
    avatar_url = Column(String(500), nullable=True, comment='프로필 이미지 URL')
    
    # ========== 시간 관련 필드 ==========
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment='가입일')
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment='마지막 수정일')
    deleted_at = Column(DateTime, nullable=True, comment='탈퇴일 (Soft Delete)')
    
    # ========== 관계 정의 ==========
    stats = relationship("UserStats", back_populates="user", uselist=False, lazy="joined")
    settings = relationship("UserSettings", back_populates="user", uselist=False, lazy="joined")
    refresh_tokens = relationship("RefreshToken", back_populates="user", lazy="select")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, name={self.name})>"


class UserStats(Base):
    """
    사용자 통계 테이블 (user_stats)
    
    사용자의 운동 통계를 저장합니다.
    사용자당 하나의 통계 레코드만 존재합니다 (1:1 관계).
    """
    __tablename__ = "user_stats"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID')
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False, comment='사용자 ID')
    
    # 통계 필드들 (기본값 0)
    total_distance = Column(DECIMAL(10, 2), default=0, comment='총 운동 거리 (km)')
    total_workouts = Column(Integer, default=0, comment='총 운동 횟수')
    completed_routes = Column(Integer, default=0, comment='완료한 경로 수')
    
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 사용자와의 관계
    user = relationship("User", back_populates="stats")
    
    def __repr__(self):
        return f"<UserStats(user_id={self.user_id}, total_distance={self.total_distance})>"


class UserSettings(Base):
    """
    사용자 설정 테이블 (user_settings)
    
    앱 설정, 알림 설정, 안전 설정 등을 저장합니다.
    """
    __tablename__ = "user_settings"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID')
    user_id = Column(String(36), ForeignKey("users.id"), unique=True, nullable=False, comment='사용자 ID')
    
    # ========== 앱 설정 ==========
    dark_mode = Column(Boolean, default=True, comment='다크 모드')
    language = Column(String(10), default="ko", comment='언어 설정')
    
    # ========== 알림 설정 ==========
    push_enabled = Column(Boolean, default=True, comment='푸시 알림 활성화')
    workout_reminder = Column(Boolean, default=True, comment='운동 시작 알림')
    goal_achievement = Column(Boolean, default=True, comment='목표 달성 알림')
    community_activity = Column(Boolean, default=False, comment='커뮤니티 활동 알림')
    
    # ========== 운동 설정 ==========
    auto_lap = Column(Boolean, default=False, comment='자동 랩')
    
    # ========== 안전 설정 ==========
    night_safety_mode = Column(Boolean, default=True, comment='야간 안전 모드')
    auto_night_mode = Column(Boolean, default=True, comment='자동 야간 모드')
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 사용자와의 관계
    user = relationship("User", back_populates="settings")


class RefreshToken(Base):
    """
    리프레시 토큰 테이블 (refresh_tokens)
    
    JWT 인증에서 액세스 토큰 갱신에 사용되는 리프레시 토큰을 저장합니다.
    """
    __tablename__ = "refresh_tokens"
    
    id = Column(String(36), primary_key=True, default=generate_uuid, comment='UUID')
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, comment='사용자 ID')
    
    token = Column(String(500), unique=True, nullable=False, comment='리프레시 토큰')
    expires_at = Column(DateTime, nullable=False, comment='만료 시간')
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True, comment='폐기 시간')
    
    # 사용자와의 관계
    user = relationship("User", back_populates="refresh_tokens")
    
    @property
    def is_valid(self) -> bool:
        """토큰이 유효한지 확인 (만료되지 않고 폐기되지 않음)"""
        now = datetime.utcnow()
        return self.expires_at > now and self.revoked_at is None
